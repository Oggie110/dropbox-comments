"""Background sync worker thread for the menu bar app."""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from queue import Queue
from typing import Optional

from .config import Config
from .gmail_client import GmailCommentFetcher
from .sheets_client import SheetsClient
from .state_store import StateStore
from .sync import run_once


class SyncStatus(Enum):
    """Status of the sync worker."""
    IDLE = "idle"
    SYNCING = "syncing"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class SyncResult:
    """Result from a sync run."""
    status: SyncStatus
    processed_count: int = 0
    unmatched_count: int = 0
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class SyncWorker:
    """
    Background worker that runs sync operations on a timer.

    Communicates with the UI thread via a result queue.
    """

    def __init__(
        self,
        config: Config,
        result_queue: Queue,
        interval_minutes: int = 15
    ):
        """
        Initialize the sync worker.

        Args:
            config: Application configuration
            result_queue: Queue to send SyncResult objects to UI thread
            interval_minutes: How often to run automatic sync (5, 10, 15, or 30)
        """
        self.config = config
        self.result_queue = result_queue
        self.interval_minutes = interval_minutes

        # Threading
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._manual_sync_event = threading.Event()

        # Clients (initialized in worker thread to avoid thread-safety issues)
        self._state_store: Optional[StateStore] = None
        self._gmail_fetcher: Optional[GmailCommentFetcher] = None
        self._sheets_client: Optional[SheetsClient] = None

        # State
        self._last_sync_time: Optional[datetime] = None
        self._is_running = False

    def start(self) -> None:
        """Start the background worker thread."""
        if self._is_running:
            logging.warning("Sync worker already running")
            return

        self._stop_event.clear()
        self._is_running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        logging.info("Sync worker started with %d minute interval", self.interval_minutes)

    def stop(self) -> None:
        """Stop the background worker thread."""
        if not self._is_running:
            return

        logging.info("Stopping sync worker...")
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._is_running = False
        logging.info("Sync worker stopped")

    def trigger_manual_sync(self) -> None:
        """Trigger an immediate sync (in addition to timer-based syncs)."""
        if not self._is_running:
            logging.warning("Cannot trigger sync: worker not running")
            return

        logging.info("Manual sync triggered")
        self._manual_sync_event.set()

    def update_interval(self, interval_minutes: int) -> None:
        """
        Update the sync interval.

        Args:
            interval_minutes: New interval (5, 10, 15, or 30)
        """
        if interval_minutes not in (5, 10, 15, 30):
            raise ValueError(f"Interval must be 5, 10, 15, or 30 minutes, got {interval_minutes}")

        old_interval = self.interval_minutes
        self.interval_minutes = interval_minutes
        logging.info("Sync interval updated from %d to %d minutes", old_interval, interval_minutes)

    def reload_credentials(self) -> None:
        """
        Reload Gmail and Sheets credentials.

        This forces re-initialization of API clients on the next sync.
        Call this when user updates credentials files.
        """
        logging.info("Credentials reload requested")
        # Clear clients so they'll be re-initialized on next sync
        self._gmail_fetcher = None
        self._sheets_client = None
        self._state_store = None

    @property
    def last_sync_time(self) -> Optional[datetime]:
        """Get the timestamp of the last completed sync."""
        return self._last_sync_time

    @property
    def is_running(self) -> bool:
        """Check if the worker thread is running."""
        return self._is_running

    def _initialize_clients(self) -> None:
        """Initialize API clients (called in worker thread)."""
        if self._state_store is None:
            self._state_store = StateStore(self.config.state_file)

        if self._gmail_fetcher is None:
            self._gmail_fetcher = GmailCommentFetcher(
                self.config.gmail_oauth_credentials_path,
                self.config.gmail_token_path,
                self.config.gmail_user_email
            )

        if self._sheets_client is None:
            self._sheets_client = SheetsClient(self.config)

    def _run_sync(self) -> SyncResult:
        """
        Run a single sync operation.

        Returns:
            SyncResult with outcome of the sync
        """
        start_time = time.time()

        try:
            # Ensure clients are initialized
            self._initialize_clients()

            # Run the sync
            processed, unmatched = run_once(
                self.config,
                self._state_store,
                self._gmail_fetcher,
                self._sheets_client
            )

            duration = time.time() - start_time
            self._last_sync_time = datetime.now()

            return SyncResult(
                status=SyncStatus.SUCCESS,
                processed_count=processed,
                unmatched_count=unmatched,
                duration_seconds=duration,
                timestamp=self._last_sync_time
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            logging.exception("Sync failed: %s", error_msg)

            return SyncResult(
                status=SyncStatus.ERROR,
                error_message=error_msg,
                duration_seconds=duration
            )

    def _worker_loop(self) -> None:
        """Main worker thread loop."""
        logging.info("Sync worker thread started")

        # Calculate sleep intervals
        interval_seconds = self.interval_minutes * 60
        check_interval = 1.0  # Check for stop/manual events every second

        seconds_since_sync = 0.0

        while not self._stop_event.is_set():
            # Check if manual sync was triggered
            if self._manual_sync_event.is_set():
                self._manual_sync_event.clear()
                logging.info("Running manual sync...")

                # Send "syncing" status
                self.result_queue.put(SyncResult(status=SyncStatus.SYNCING))

                # Run sync and send result
                result = self._run_sync()
                self.result_queue.put(result)

                # Reset timer after manual sync
                seconds_since_sync = 0.0

            # Check if it's time for automatic sync
            elif seconds_since_sync >= interval_seconds:
                logging.info("Running automatic sync (interval: %d min)...", self.interval_minutes)

                # Send "syncing" status
                self.result_queue.put(SyncResult(status=SyncStatus.SYNCING))

                # Run sync and send result
                result = self._run_sync()
                self.result_queue.put(result)

                # Reset timer
                seconds_since_sync = 0.0

            # Sleep briefly and update timer
            time.sleep(check_interval)
            seconds_since_sync += check_interval

        logging.info("Sync worker thread exiting")
