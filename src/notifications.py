"""macOS notification support for the menu bar app."""

import rumps


def notify_new_comment(file_name: str, comment_preview: str, sheet_name: str) -> None:
    """
    Show notification for a new comment.

    Args:
        file_name: The Dropbox file that was commented on
        comment_preview: First ~100 chars of the comment
        sheet_name: Name of the Google Sheet that was updated
    """
    # Truncate preview if too long
    if len(comment_preview) > 100:
        comment_preview = comment_preview[:97] + "..."

    rumps.notification(
        title="New Dropbox Comment",
        subtitle=file_name,
        message=comment_preview,
        sound=True
    )


def notify_error(error_message: str) -> None:
    """
    Show notification for sync error.

    Args:
        error_message: Description of the error
    """
    # Truncate if too long
    if len(error_message) > 200:
        error_message = error_message[:197] + "..."

    rumps.notification(
        title="Dropbox Sync Error",
        subtitle="Failed to sync comments",
        message=error_message,
        sound=True
    )


def notify_sync_summary(new_comments: int, duration_seconds: float) -> None:
    """
    Show notification with sync summary.

    Args:
        new_comments: Number of new comments synced
        duration_seconds: How long the sync took
    """
    if new_comments == 0:
        message = f"No new comments (completed in {duration_seconds:.1f}s)"
    elif new_comments == 1:
        message = f"1 new comment synced in {duration_seconds:.1f}s"
    else:
        message = f"{new_comments} new comments synced in {duration_seconds:.1f}s"

    rumps.notification(
        title="Dropbox Sync Complete",
        subtitle="",
        message=message,
        sound=False  # Don't make noise for summary (less intrusive)
    )


def notify_credentials_reloaded() -> None:
    """Show notification that credentials were successfully reloaded."""
    rumps.notification(
        title="Credentials Reloaded",
        subtitle="",
        message="Gmail and Google Sheets credentials reloaded successfully",
        sound=False
    )


def notify_sync_started() -> None:
    """Show notification that manual sync has started (optional, can be noisy)."""
    rumps.notification(
        title="Syncing...",
        subtitle="",
        message="Checking for new Dropbox comments",
        sound=False
    )
