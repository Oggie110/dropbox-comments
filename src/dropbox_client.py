from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Generator, Iterable, List, Optional

import dropbox
from dropbox.exceptions import ApiError
from dropbox.files import FileMetadata


@dataclass
class DropboxFileComment:
    file_id: str
    file_name: str
    file_path: str
    comment_id: str
    comment_text: str
    created: datetime
    user_display_name: str
    user_email: Optional[str]


class DropboxCommentFetcher:
    def __init__(self, access_token: str, root_folder: str):
        self.client = dropbox.Dropbox(access_token)
        self.root_folder = root_folder or ""

    def iter_files(self) -> Generator[FileMetadata, None, None]:
        try:
            result = self.client.files_list_folder(self.root_folder, recursive=True, include_media_info=False)
        except ApiError as exc:
            raise RuntimeError(f"Failed to list Dropbox folder '{self.root_folder}': {exc}") from exc

        yield from self._iter_file_entries(result.entries)

        while result.has_more:
            result = self.client.files_list_folder_continue(result.cursor)
            yield from self._iter_file_entries(result.entries)

    def _iter_file_entries(self, entries: Iterable) -> Generator[FileMetadata, None, None]:
        for entry in entries:
            if isinstance(entry, FileMetadata):
                yield entry

    def fetch_comments_for_file(self, file_entry: FileMetadata) -> List[DropboxFileComment]:
        comments: List[DropboxFileComment] = []
        try:
            result = self.client.files_list_comments(file_entry.id)
        except ApiError as exc:
            if self._is_no_comments_error(exc):
                return comments
            raise RuntimeError(f"Failed to list comments for file '{file_entry.path_display}': {exc}") from exc

        comments.extend(self._convert_comments(file_entry, result.comments))

        while result.has_more:
            result = self.client.files_list_comments_continue(result.cursor)
            comments.extend(self._convert_comments(file_entry, result.comments))

        return comments

    def _convert_comments(self, file_entry: FileMetadata, raw_comments) -> List[DropboxFileComment]:
        converted: List[DropboxFileComment] = []
        for comment in raw_comments:
            actor = getattr(comment, "user", None)
            if actor is None and hasattr(comment, "author"):
                actor = comment.author
            display_name = getattr(actor, "display_name", "Unknown")
            email = getattr(actor, "email", None)
            converted.append(
                DropboxFileComment(
                    file_id=file_entry.id,
                    file_name=file_entry.name,
                    file_path=file_entry.path_display,
                    comment_id=comment.id,
                    comment_text=comment.text,
                    created=comment.created,
                    user_display_name=display_name,
                    user_email=email,
                )
            )
        return converted

    @staticmethod
    def _is_no_comments_error(error: ApiError) -> bool:
        # Dropbox returns a specific structured error when a file has no comments yet.
        try:
            return error.error.is_comment_not_found()
        except Exception:
            return False
