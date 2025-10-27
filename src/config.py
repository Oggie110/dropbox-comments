import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    gmail_oauth_credentials_path: Path
    gmail_token_path: Path
    gmail_user_email: str
    sheet_id: str
    sheet_range: str
    google_sheets_credentials_path: Path
    match_threshold: float
    poll_interval_seconds: int
    state_file: Path
    comment_log_sheet: str = "Comment Log"
    sheet_comments_column: int = 6  # Column G (0-based)
    sheet_title_column: int = 3  # Column D (0-based)
    sheet_last_update_column: int = 7  # Column H (0-based)

    @property
    def sheet_name(self) -> str:
        if "!" in self.sheet_range:
            return self.sheet_range.split("!", 1)[0]
        return self.sheet_range


def load_config(env_path: Optional[Path] = None) -> Config:
    if env_path:
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    gmail_user_email = os.getenv("GMAIL_USER_EMAIL")
    if not gmail_user_email:
        raise ValueError("GMAIL_USER_EMAIL is required in the environment.")

    sheet_id = os.getenv("SHEET_ID")
    if not sheet_id:
        raise ValueError("SHEET_ID is required in the environment.")

    gmail_oauth_creds_raw = os.getenv("GMAIL_OAUTH_CREDENTIALS", "./credentials/oauth_credentials.json")
    gmail_oauth_credentials_path = Path(gmail_oauth_creds_raw).expanduser().resolve()

    gmail_token_raw = os.getenv("GMAIL_TOKEN_PATH", "./credentials/gmail_token.json")
    gmail_token_path = Path(gmail_token_raw).expanduser().resolve()

    google_sheets_creds_raw = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "./credentials/service_account.json")
    google_sheets_credentials_path = Path(google_sheets_creds_raw).expanduser().resolve()

    sheet_range = os.getenv("SHEET_RANGE", "Sheet1!A:H")

    match_threshold = float(os.getenv("MATCH_THRESHOLD", "0.85"))
    poll_interval_seconds = int(os.getenv("POLL_INTERVAL_SECONDS", "900"))

    state_file = Path(os.getenv("STATE_FILE", "data/processed_state.json")).resolve()

    return Config(
        gmail_oauth_credentials_path=gmail_oauth_credentials_path,
        gmail_token_path=gmail_token_path,
        gmail_user_email=gmail_user_email,
        sheet_id=sheet_id,
        sheet_range=sheet_range,
        google_sheets_credentials_path=google_sheets_credentials_path,
        match_threshold=match_threshold,
        poll_interval_seconds=poll_interval_seconds,
        state_file=state_file,
    )
