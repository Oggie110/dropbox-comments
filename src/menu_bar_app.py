"""macOS menu bar application for Dropbox comment sync."""

import logging
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue

import rumps

from .config import Config, load_config
from .preferences import Preferences
from .sync_worker import SyncResult, SyncStatus, SyncWorker
from . import notifications


# Icon path (template=True makes it adapt to light/dark mode)
ICON_PATH = str(Path(__file__).parent.parent / "resources" / "icon_cloud.png")


class DropboxSyncApp(rumps.App):
    """Menu bar app for monitoring Dropbox comment sync."""

    def __init__(self, config: Config, preferences: Preferences):
        super().__init__(
            name="Dropbox Sync",
            icon=ICON_PATH,
            template=True,  # Makes icon adapt to light/dark mode
        )

        self.config = config
        self.prefs = preferences

        # State
        self.current_status = SyncStatus.IDLE
        self.last_result: SyncResult | None = None

        # Load today's count from persistent storage
        self._load_today_count()

        # Communication with worker thread
        self.result_queue: Queue = Queue()
        self.sync_worker = SyncWorker(
            config=self.config,
            result_queue=self.result_queue,
            interval_minutes=self.prefs.sync_interval_minutes
        )

        # Build menu
        self._build_menu()

        # Start polling for results from worker thread
        self.timer = rumps.Timer(self._check_sync_results, 0.5)
        self.timer.start()

        # Start the sync worker
        self.sync_worker.start()

        # Override quit button with cleanup callback
        self.quit_button = rumps.MenuItem("Quit", callback=self.on_quit)

    def _load_today_count(self) -> None:
        """Load today's count from preferences, reset if new day."""
        today_str = datetime.now().date().isoformat()
        stored_date = self.prefs.today_date

        if stored_date == today_str:
            # Same day, load the count
            self.today_comment_count = self.prefs.today_count
        else:
            # New day, reset count
            self.today_comment_count = 0
            self.prefs.today_date = today_str
            self.prefs.today_count = 0

    def _save_today_count(self) -> None:
        """Save today's count to preferences."""
        today_str = datetime.now().date().isoformat()
        self.prefs.today_date = today_str
        self.prefs.today_count = self.today_comment_count

    def _build_menu(self) -> None:
        """Build the menu bar menu."""
        # Status line (will be updated dynamically)
        self.status_item = rumps.MenuItem("Status: Idle", callback=None)

        # Today's count
        self.count_item = rumps.MenuItem("Today: 0 comments", callback=None)

        # Sync interval display
        interval = self.prefs.sync_interval_minutes
        self.interval_item = rumps.MenuItem(f"Interval: Every {interval} min", callback=None)

        # Separator
        sep1 = rumps.separator

        # Action buttons
        self.sync_button = rumps.MenuItem("Sync Now", callback=self.sync_now)
        self.logs_button = rumps.MenuItem("View Logs", callback=self.view_logs)
        self.sheet_button = rumps.MenuItem("Open Sheet", callback=self.open_sheet)

        # Separator
        sep2 = rumps.separator

        # Preferences
        self.prefs_button = rumps.MenuItem("Preferences", callback=self.show_preferences)

        # About
        self.about_button = rumps.MenuItem("About", callback=self.show_about)

        # Add all items to menu (rumps will add Quit button automatically)
        self.menu = [
            self.status_item,
            self.count_item,
            self.interval_item,
            sep1,
            self.sync_button,
            self.logs_button,
            self.sheet_button,
            sep2,
            self.prefs_button,
            self.about_button,
        ]

    def _update_status_display(self) -> None:
        """Update the status line in the menu."""
        if self.current_status == SyncStatus.IDLE:
            if self.last_result and self.last_result.status == SyncStatus.SUCCESS:
                last_time = self.last_result.timestamp.strftime("%H:%M")
                self.status_item.title = f"Status: Last synced at {last_time}"
            else:
                self.status_item.title = "Status: Idle"
            # Icon stays as cloud emoji

        elif self.current_status == SyncStatus.SYNCING:
            self.status_item.title = "Status: Syncing..."
            # Icon stays as cloud emoji

        elif self.current_status == SyncStatus.SUCCESS:
            if self.last_result:
                last_time = self.last_result.timestamp.strftime("%H:%M")
                self.status_item.title = f"Status: Synced at {last_time}"
            # Icon stays as cloud emoji

        elif self.current_status == SyncStatus.ERROR:
            self.status_item.title = "Status: Error (see logs)"
            # Icon stays as cloud emoji

    def _update_count_display(self) -> None:
        """Update the today's count line in the menu."""
        if self.today_comment_count == 0:
            self.count_item.title = "Today: No new comments"
        elif self.today_comment_count == 1:
            self.count_item.title = "Today: 1 comment"
        else:
            self.count_item.title = f"Today: {self.today_comment_count} comments"

    def _update_interval_display(self) -> None:
        """Update the sync interval line in the menu."""
        interval = self.prefs.sync_interval_minutes
        self.interval_item.title = f"Interval: Every {interval} min"

    def _check_sync_results(self, _timer: rumps.Timer) -> None:
        """
        Timer callback to check for results from worker thread.

        This runs on the main UI thread and pulls results from the queue.
        """
        try:
            # Non-blocking check for results
            while True:
                result = self.result_queue.get_nowait()
                self._handle_sync_result(result)
        except Empty:
            # No results available
            pass

    def _handle_sync_result(self, result: SyncResult) -> None:
        """
        Handle a sync result from the worker thread.

        Args:
            result: The sync result to process
        """
        self.last_result = result
        self.current_status = result.status

        if result.status == SyncStatus.SYNCING:
            # Sync started
            self._update_status_display()

        elif result.status == SyncStatus.SUCCESS:
            # Sync completed successfully
            processed = result.processed_count

            # Update today's count and save to preferences
            self.today_comment_count += processed
            self._save_today_count()

            # Update display
            self._update_status_display()
            self._update_count_display()

            # Send notifications based on preferences
            if processed > 0 and self.prefs.notify_new_comments:
                # For simplicity, show one notification for all comments
                if processed == 1:
                    msg = "1 new comment synced"
                else:
                    msg = f"{processed} new comments synced"
                notifications.notify_new_comment(
                    file_name="Dropbox Files",
                    comment_preview=msg,
                    sheet_name="Google Sheet"
                )

            if self.prefs.notify_summary:
                notifications.notify_sync_summary(
                    new_comments=processed,
                    duration_seconds=result.duration_seconds
                )

            logging.info(
                "Sync completed: %d processed, %d unmatched, %.1fs",
                processed,
                result.unmatched_count,
                result.duration_seconds
            )

        elif result.status == SyncStatus.ERROR:
            # Sync failed
            self._update_status_display()

            if self.prefs.notify_errors:
                notifications.notify_error(result.error_message or "Unknown error")

            logging.error("Sync failed: %s", result.error_message)

    def sync_now(self, _sender: rumps.MenuItem) -> None:
        """Callback for 'Sync Now' button."""
        logging.info("User triggered manual sync")
        self.sync_worker.trigger_manual_sync()

    def view_logs(self, _sender: rumps.MenuItem) -> None:
        """Callback for 'View Logs' button - open logs directory in Finder."""
        logs_dir = Path(self.config.state_file).parent.parent / "logs"
        if logs_dir.exists():
            subprocess.run(["open", str(logs_dir)])
        else:
            rumps.alert(
                title="Logs Not Found",
                message=f"Logs directory does not exist:\n{logs_dir}"
            )

    def open_sheet(self, _sender: rumps.MenuItem) -> None:
        """Callback for 'Open Sheet' button - open Google Sheet in browser."""
        sheet_url = f"https://docs.google.com/spreadsheets/d/{self.config.sheet_id}"
        webbrowser.open(sheet_url)

    def show_preferences(self, _sender: rumps.MenuItem) -> None:
        """Callback for 'Preferences' button - show preferences dialog."""
        try:
            current_interval = self.prefs.sync_interval_minutes

            # Use text input window (more reliable than alert buttons)
            window = rumps.Window(
                message=f"Current interval: {current_interval} minutes\n\nEnter new interval (5, 10, 15, or 30):",
                title="Preferences",
                default_text=str(current_interval),
                ok="Update",
                cancel="Cancel"
            )

            response = window.run()

            if response.clicked:
                # User clicked Update
                try:
                    new_interval = int(response.text)
                    if new_interval not in (5, 10, 15, 30):
                        rumps.alert(
                            title="Invalid Interval",
                            message="Please enter 5, 10, 15, or 30 minutes.",
                            ok="OK"
                        )
                        return

                    # Only update if changed
                    if new_interval != current_interval:
                        # Update preferences
                        self.prefs.sync_interval_minutes = new_interval
                        self.sync_worker.update_interval(new_interval)

                        # Update interval display in menu
                        self._update_interval_display()

                        rumps.notification(
                            title="Preferences Updated",
                            subtitle="",
                            message=f"Sync interval changed to {new_interval} minutes",
                            sound=False
                        )
                except ValueError:
                    rumps.alert(
                        title="Invalid Input",
                        message="Please enter a number (5, 10, 15, or 30).",
                        ok="OK"
                    )
        except Exception as e:
            logging.error(f"Error in preferences dialog: {e}", exc_info=True)
            rumps.alert(
                title="Error",
                message=f"Failed to update preferences: {str(e)}",
                ok="OK"
            )

    def show_about(self, _sender: rumps.MenuItem) -> None:
        """Callback for 'About' button."""
        from . import __version__

        rumps.alert(
            title="Dropbox Comment Sync",
            message=f"Version {__version__.__version__}\n\n"
                    "Automatically syncs Dropbox file comments\n"
                    "from Gmail to Google Sheets.\n\n"
                    "Made with Claude Code",
            ok="OK"
        )

    def on_quit(self, _sender: rumps.MenuItem) -> None:
        """Callback when Quit button is clicked - cleanup before exit."""
        logging.info("Quit requested by user")
        # Stop the sync worker gracefully
        self.sync_worker.stop()
        # Quit the app
        rumps.quit_application()


def main():
    """Main entry point for the menu bar app."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Load configuration
    try:
        config = load_config()
    except Exception as e:
        rumps.alert(
            title="Configuration Error",
            message=f"Failed to load configuration:\n{e}\n\nPlease check your .env file."
        )
        sys.exit(1)

    # Load preferences
    preferences = Preferences()

    # Create and run app
    app = DropboxSyncApp(config, preferences)
    app.run()


if __name__ == "__main__":
    main()
