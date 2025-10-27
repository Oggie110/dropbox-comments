from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


@dataclass
class DropboxCommentEmail:
    """Represents a parsed Dropbox comment notification email."""
    message_id: str
    file_name: str
    comment_text: str
    commenter_name: str
    commented_date: datetime


class GmailCommentFetcher:
    """Fetches and parses Dropbox comment notification emails from Gmail."""

    def __init__(self, oauth_credentials_path: Path, token_path: Path, user_email: str):
        self.oauth_credentials_path = oauth_credentials_path
        self.token_path = token_path
        self.user_email = user_email
        self.service = self._build_service()

    def _build_service(self):
        """Authenticate with Gmail API using OAuth 2.0."""
        creds = None

        # Load existing token if available
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.oauth_credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save the credentials for future runs
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())

        return build('gmail', 'v1', credentials=creds)

    def fetch_unread_comment_emails(self) -> List[DropboxCommentEmail]:
        """
        Fetch unread Dropbox comment notification emails (forwarded).

        Returns:
            List of parsed comment emails
        """
        comments = []

        try:
            # Search for unread emails
            # Note: Gmail's search indexing for forwarded emails can be slow,
            # so we fetch all unread messages and filter manually
            query = 'is:unread'
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=50  # Adjust if you have more unread emails
            ).execute()

            all_messages = results.get('messages', [])

            # Filter for "commented" in subject (handles forwarded Dropbox notifications)
            messages = []
            for msg in all_messages:
                full_msg = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['Subject']
                ).execute()
                headers = {h['name']: h['value'] for h in full_msg['payload']['headers']}
                subject = headers.get('Subject', '')
                if 'commented' in subject.lower():
                    messages.append(msg)

            for message in messages:
                comment = self._parse_message(message['id'])
                if comment:
                    comments.append(comment)
                    # Mark as read after successful parsing
                    self._mark_as_read(message['id'])

        except Exception as exc:
            raise RuntimeError(f"Failed to fetch Gmail messages: {exc}") from exc

        return comments

    def _parse_message(self, message_id: str) -> Optional[DropboxCommentEmail]:
        """Parse a Gmail message to extract comment information."""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            # Extract headers
            headers = {h['name']: h['value'] for h in message['payload']['headers']}
            subject = headers.get('Subject', '')
            date_str = headers.get('Date', '')

            # Remove "Fwd: " prefix if present (for forwarded emails)
            clean_subject = re.sub(r'^(Fwd:\s*)+', '', subject, flags=re.IGNORECASE)

            # Parse subject to extract file name
            # Expected format: "Charlie Cavenius commented on \"Vera Sol_Inner Bloom.wav\""
            file_name_match = re.search(r'commented on ["\']([^"\']+)["\']', clean_subject)
            if not file_name_match:
                # Try alternative format without quotes
                file_name_match = re.search(r'commented on (.+)$', clean_subject)

            if not file_name_match:
                return None

            file_name = file_name_match.group(1).strip()

            # Extract commenter name from subject
            commenter_match = re.match(r'^(.+?) commented on', clean_subject)
            commenter_name = commenter_match.group(1) if commenter_match else "Unknown"

            # Parse date
            try:
                commented_date = parsedate_to_datetime(date_str)
            except Exception:
                commented_date = datetime.now()

            # Extract comment text from body
            comment_text = self._extract_comment_text(message['payload'])

            if not comment_text:
                return None

            return DropboxCommentEmail(
                message_id=message_id,
                file_name=file_name,
                comment_text=comment_text,
                commenter_name=commenter_name,
                commented_date=commented_date
            )

        except Exception as exc:
            print(f"Warning: Failed to parse message {message_id}: {exc}")
            return None

    def _extract_comment_text(self, payload) -> Optional[str]:
        """Extract the comment text from email body."""
        def get_body(payload):
            """Recursively extract body from email payload."""
            if 'body' in payload and 'data' in payload['body']:
                return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')

            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        if 'data' in part['body']:
                            return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    elif part['mimeType'] == 'text/html':
                        if 'data' in part['body']:
                            html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                            # Extract text from HTML (simple approach)
                            return self._extract_text_from_html(html)
                    elif 'parts' in part:
                        result = get_body(part)
                        if result:
                            return result
            return None

        body = get_body(payload)
        if not body:
            return None

        # Extract the actual comment from the email body
        # Handle forwarded email structure
        lines = body.split('\n')
        comment_lines = []
        found_comment = False
        skip_forwarding_headers = False

        # Check if this is a forwarded email
        if 'Begin forwarded message:' in body or 'Fwd:' in body[:200]:
            skip_forwarding_headers = True

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip forwarding header section
            if skip_forwarding_headers:
                # Look for end of forwarding headers (typically Message-Id is last)
                if line_stripped.startswith('Message-Id:') or line_stripped.startswith('Message-ID:'):
                    skip_forwarding_headers = False
                    continue
                # Also check for common header patterns
                if any(line_stripped.startswith(h) for h in ['From:', 'Subject:', 'Date:', 'To:']):
                    continue

            # Skip "Begin forwarded message" header
            if 'Begin forwarded message' in line_stripped:
                continue

            # Look for the commenter's name and date pattern (indicates start of actual comment)
            # This appears in the Dropbox notification after the file name line
            if re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}', line_stripped):
                found_comment = True
                continue

            # Once we've found the comment start, collect all lines until we hit footer content
            if found_comment:
                # Stop if we hit Dropbox links or "Reply" button
                if 'dropbox.com' in line_stripped.lower() or 'reply' in line_stripped.lower():
                    break

                # Add the line (including empty lines between paragraphs)
                comment_lines.append(line_stripped)

        if comment_lines:
            return '\n'.join(comment_lines).strip()

        # Fallback: return body without URLs and common footer text
        cleaned = re.sub(r'https?://\S+', '', body)
        cleaned = re.sub(r'Reply.*?$', '', cleaned, flags=re.MULTILINE)
        return cleaned.strip()[:500]  # Limit to 500 chars as fallback

    def _extract_text_from_html(self, html: str) -> str:
        """Simple HTML to text extraction."""
        # Remove script and style tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Decode HTML entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        return text

    def _mark_as_read(self, message_id: str):
        """Mark a message as read."""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
        except Exception as exc:
            print(f"Warning: Failed to mark message {message_id} as read: {exc}")
