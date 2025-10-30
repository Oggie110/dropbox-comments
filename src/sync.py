from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from .config import Config, load_config
from .gmail_client import GmailCommentFetcher, DropboxCommentEmail
from .matcher import SongMatcher, normalize_title
from .sheets_client import SheetsClient, SongRow
from .state_store import FileRowBinding, StateStore
from . import LOG_DIR, LOG_FILE


COMMENT_LOG_HEADER = [
    "Logged At",
    "Dropbox File Name",
    "Dropbox File Path",
    "Dropbox File ID",
    "Email Message ID",
    "Commenter",
    "Comment Created",
    "Matched Song Title",
    "Matched Sheet Row",
    "Match Score",
    "Comment Text",
]


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
        force=True,
    )


def ensure_comment_headers(header: List[str], sheets_client: SheetsClient, config: Config) -> None:
    if len(header) <= config.sheet_last_update_column or header[config.sheet_last_update_column] != "Last Update":
        sheets_client.ensure_header_value(config.sheet_last_update_column, "Last Update")


def ensure_comment_log(sheets_client: SheetsClient) -> None:
    sheets_client.ensure_comment_log_sheet(COMMENT_LOG_HEADER)


def build_row_indexes(rows: Iterable[SongRow]) -> Tuple[Dict[int, SongRow], Dict[str, List[SongRow]]]:
    rows_by_number: Dict[int, SongRow] = {}
    rows_by_normalized: Dict[str, List[SongRow]] = {}
    for row in rows:
        rows_by_number[row.row_number] = row
        norm = normalize_title(row.title) if row.title else ""
        if norm:
            rows_by_normalized.setdefault(norm, []).append(row)
    return rows_by_number, rows_by_normalized


def ensure_timezone(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def format_comment_for_sheet(comment: DropboxCommentEmail) -> str:
    created = ensure_timezone(comment.commented_date).astimezone()
    header_parts = [
        created.strftime("%Y-%m-%d %H:%M"),
        comment.commenter_name or "Unknown",
    ]
    header_line = " • ".join(header_parts)
    text = (comment.comment_text or "").strip()
    if text:
        return f"{header_line}\n{text}"
    return header_line


def find_row_for_file(
    comment: DropboxCommentEmail,
    state_bindings: Dict[str, FileRowBinding],
    rows_by_number: Dict[int, SongRow],
    rows_by_normalized: Dict[str, List[SongRow]],
    matcher: SongMatcher,
) -> Tuple[Optional[SongRow], float]:
    # Use file_name as the key since we don't have file_id from emails
    binding = state_bindings.get(comment.file_name)
    binding_score = 1.0
    if binding:
        normalized_binding = normalize_title(binding.title)
        existing_row = rows_by_number.get(binding.row_number)
        if existing_row and normalize_title(existing_row.title) == normalized_binding:
            return existing_row, binding_score
        candidates = rows_by_normalized.get(normalized_binding, [])
        if candidates:
            chosen = candidates[0]
            state_bindings[comment.file_name] = FileRowBinding(
                row_number=chosen.row_number, title=chosen.title
            )
            return chosen, binding_score

    match = matcher.match(comment.file_name)
    if match:
        row = rows_by_number.get(match.row_number)
        if row:
            state_bindings[comment.file_name] = FileRowBinding(
                row_number=row.row_number, title=row.title
            )
            return row, match.score

    return None, 0.0


def build_log_row(
    comment: DropboxCommentEmail,
    matched_row: Optional[SongRow],
    score: float,
) -> List[str]:
    now_local = datetime.now(timezone.utc).astimezone()
    commenter = comment.commenter_name or ""

    match_title = matched_row.title if matched_row else ""
    match_row = str(matched_row.row_number) if matched_row else ""

    return [
        now_local.isoformat(timespec="seconds"),
        comment.file_name,
        "",  # file_path (not available from email)
        "",  # file_id (not available from email)
        comment.message_id,
        commenter,
        ensure_timezone(comment.commented_date).isoformat(timespec="seconds"),
        match_title,
        match_row,
        f"{score:.2f}" if score else "",
        comment.comment_text or "",
    ]


def run_once(
    config: Config,
    state_store: StateStore,
    gmail_fetcher: GmailCommentFetcher,
    sheets_client: SheetsClient,
) -> Tuple[int, int]:
    state = state_store.load()
    header, song_rows = sheets_client.fetch_song_rows()
    if not song_rows:
        logging.warning("No song rows found in the sheet; skipping sync.")
        return 0, 0

    ensure_comment_headers(header, sheets_client, config)
    ensure_comment_log(sheets_client)

    rows_by_number, rows_by_normalized = build_row_indexes(song_rows)
    matcher = SongMatcher(song_rows, threshold=config.match_threshold)

    # Fetch unread comment emails from Gmail
    pending_comments: List[DropboxCommentEmail] = []
    for comment in gmail_fetcher.fetch_unread_comment_emails():
        if comment.message_id in state.processed_comment_ids:
            continue
        pending_comments.append(comment)

    if not pending_comments:
        logging.info("No new comment emails found.")
        state.last_polled = datetime.now(timezone.utc).isoformat(timespec="seconds")
        state_store.save(state)
        return 0, 0

    pending_comments.sort(key=lambda c: ensure_timezone(c.commented_date))

    comment_log_rows: List[List[str]] = []
    processed = 0
    unmatched = 0
    for comment in pending_comments:
        matched_row, score = find_row_for_file(
            comment, state.file_row_cache, rows_by_number, rows_by_normalized, matcher
        )

        if matched_row:
            formatted = format_comment_for_sheet(comment)
            sheets_client.update_comment_cells(
                matched_row.row_number, formatted, datetime.now(timezone.utc).astimezone()
            )
            processed += 1
            logging.info(
                "Updated row %s (%s) with new comment from email %s",
                matched_row.row_number,
                matched_row.title,
                comment.message_id,
            )
        else:
            unmatched += 1
            logging.warning(
                "Could not match Dropbox file '%s' to a sheet row (email %s).",
                comment.file_name,
                comment.message_id,
            )

        comment_log_rows.append(build_log_row(comment, matched_row, score))
        state.processed_comment_ids.add(comment.message_id)

    if comment_log_rows:
        sheets_client.append_to_comment_log(comment_log_rows)

    state.last_polled = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state_store.save(state)
    return processed, unmatched


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Dropbox comments into Google Sheets.")
    parser.add_argument("--env", dest="env_path", help="Path to a .env file.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single sync cycle and exit (default: keep polling).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    configure_logging(verbose=args.verbose)

    try:
        config = load_config(env_path=args.env_path)
    except Exception as exc:
        logging.error("Failed to load configuration: %s", exc)
        return 1

    state_store = StateStore(config.state_file)
    gmail_fetcher = GmailCommentFetcher(
        config.gmail_oauth_credentials_path,
        config.gmail_token_path,
        config.gmail_user_email
    )
    sheets_client = SheetsClient(config)

    poll_interval = config.poll_interval_seconds

    while True:
        try:
            processed, unmatched = run_once(config, state_store, gmail_fetcher, sheets_client)
            logging.info(
                "Run complete: %s updated, %s unmatched.",
                processed,
                unmatched,
            )
        except Exception as exc:
            logging.exception("Sync run failed: %s", exc)

        if args.once:
            break

        logging.debug("Sleeping for %s seconds before next poll.", poll_interval)
        time.sleep(poll_interval)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
