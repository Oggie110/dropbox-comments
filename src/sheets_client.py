from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Sequence, Tuple

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import Config


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@dataclass
class SongRow:
    row_number: int  # 1-based row number in the sheet
    values: List[str]
    title: str


def _column_index_to_letter(index: int) -> str:
    index += 1  # Convert 0-based to 1-based
    letters = []
    while index:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


def _extract_column_from_cell_ref(cell_ref: str) -> Optional[str]:
    match = re.match(r"([A-Za-z]+)", cell_ref)
    return match.group(1) if match else None


def _column_letter_to_index(letter: str) -> int:
    value = 0
    for char in letter.upper():
        value = value * 26 + (ord(char) - 64)
    return value - 1


def _parse_range_width(range_expression: str) -> int:
    if "!" in range_expression:
        _, range_expression = range_expression.split("!", 1)

    if ":" in range_expression:
        start_ref, end_ref = range_expression.split(":", 1)
        end_col = _extract_column_from_cell_ref(end_ref) or "A"
        return _column_letter_to_index(end_col) + 1

    single_col = _extract_column_from_cell_ref(range_expression) or "A"
    return _column_letter_to_index(single_col) + 1


class SheetsClient:
    def __init__(self, config: Config):
        self.config = config
        credentials = Credentials.from_service_account_file(
            str(config.google_sheets_credentials_path), scopes=SCOPES
        )
        self.service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self.expected_columns = _parse_range_width(config.sheet_range)

    def fetch_song_rows(self) -> Tuple[List[str], List[SongRow]]:
        try:
            response = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.config.sheet_id, range=self.config.sheet_range)
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"Failed to read sheet data: {exc}") from exc

        values = response.get("values", [])
        if not values:
            return [], []

        header = self._pad_row(values[0])
        song_rows: List[SongRow] = []
        for offset, row in enumerate(values[1:], start=2):
            padded = self._pad_row(row)
            title = ""
            if len(padded) > self.config.sheet_title_column:
                title = padded[self.config.sheet_title_column]
            song_rows.append(SongRow(row_number=offset, values=padded, title=title))
        return header, song_rows

    def _pad_row(self, row: Sequence[str]) -> List[str]:
        padded = list(row)
        if len(padded) < self.expected_columns:
            padded.extend([""] * (self.expected_columns - len(padded)))
        return padded

    def ensure_header_value(self, column_index: int, value: str) -> None:
        column_letter = _column_index_to_letter(column_index)
        target_range = f"{self.config.sheet_name}!{column_letter}1"
        body = {"values": [[value]]}
        self.service.spreadsheets().values().update(
            spreadsheetId=self.config.sheet_id,
            range=target_range,
            valueInputOption="RAW",
            body=body,
        ).execute()

    def update_comment_cells(self, row_number: int, comment: str, last_update: datetime) -> None:
        comment_col_letter = _column_index_to_letter(self.config.sheet_comments_column)
        last_update_col_letter = _column_index_to_letter(self.config.sheet_last_update_column)
        rows = [
            {
                "range": f"{self.config.sheet_name}!{comment_col_letter}{row_number}",
                "values": [[comment]],
            },
            {
                "range": f"{self.config.sheet_name}!{last_update_col_letter}{row_number}",
                "values": [[last_update.isoformat(timespec="seconds")]],
            },
        ]
        body = {"valueInputOption": "RAW", "data": rows}
        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=self.config.sheet_id, body=body
        ).execute()

    def ensure_comment_log_sheet(self, header: List[str]) -> None:
        spreadsheet = (
            self.service.spreadsheets().get(spreadsheetId=self.config.sheet_id).execute()
        )
        sheets = spreadsheet.get("sheets", [])
        sheet_titles = {sheet["properties"]["title"] for sheet in sheets}
        if self.config.comment_log_sheet in sheet_titles:
            return

        requests = [
            {
                "addSheet": {
                    "properties": {
                        "title": self.config.comment_log_sheet,
                        "hidden": True,
                    }
                }
            }
        ]
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.config.sheet_id, body={"requests": requests}
        ).execute()

        header_range = f"{self.config.comment_log_sheet}!A1:{_column_index_to_letter(len(header) - 1)}1"
        self.service.spreadsheets().values().update(
            spreadsheetId=self.config.sheet_id,
            range=header_range,
            valueInputOption="RAW",
            body={"values": [header]},
        ).execute()

    def append_to_comment_log(self, rows: Iterable[List[str]]) -> None:
        rows = list(rows)
        if not rows:
            return

        self.service.spreadsheets().values().append(
            spreadsheetId=self.config.sheet_id,
            range=f"{self.config.comment_log_sheet}!A:Z",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()
