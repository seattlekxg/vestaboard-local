"""Message scheduler using cron expressions."""

import threading
import time
from datetime import datetime, date
from typing import Callable, Optional

from croniter import croniter

from .client import VestaboardClient
from .fetchers import WeatherFetcher, StockFetcher, CalendarFetcher, NewsFetcher, CountdownFetcher, FlightFetcher
from .storage import Storage, ScheduledMessage

# Flight statuses that indicate the flight is complete
COMPLETED_STATUSES = ["landed", "cancelled", "diverted"]


class MessageScheduler:
    """Scheduler for automated Vestaboard messages."""

    def __init__(
        self,
        client: Optional[VestaboardClient] = None,
        storage: Optional[Storage] = None
    ):
        self.client = client or VestaboardClient()
        self.storage = storage or Storage()
        self.weather_fetcher = WeatherFetcher()
        self.stock_fetcher = StockFetcher(storage=self.storage)
        self.calendar_fetcher = CalendarFetcher()
        self.news_fetcher = NewsFetcher()
        self.countdown_fetcher = CountdownFetcher(storage=self.storage)
        self.flight_fetcher = FlightFetcher(storage=self.storage)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._flight_thread: Optional[threading.Thread] = None
        self._last_flight_status: dict = {}  # Track last known status per flight

    def execute_message(self, msg: ScheduledMessage) -> bool:
        """Execute a scheduled message.

        Args:
            msg: The scheduled message to execute.

        Returns:
            True if message was sent successfully.
        """
        success = False
        content = ""

        try:
            if msg.message_type == "text":
                content = msg.content or ""
                success = self.client.send_message(content)

            elif msg.message_type == "weather":
                weather = self.weather_fetcher.fetch()
                if weather:
                    lines = self.weather_fetcher.format_for_board(weather)
                    content = "\n".join(lines)
                    success = self.client.send_lines(lines)

            elif msg.message_type == "stocks":
                stocks = self.stock_fetcher.fetch_multiple()
                if stocks:
                    lines = self.stock_fetcher.format_for_board(stocks)
                    content = "\n".join(lines)
                    success = self.client.send_lines(lines)

            elif msg.message_type == "calendar":
                events = self.calendar_fetcher.fetch_today()
                lines = self.calendar_fetcher.format_for_board(events)
                content = "\n".join(lines)
                success = self.client.send_lines(lines)

            elif msg.message_type == "news":
                headlines = self.news_fetcher.fetch_headlines(count=1)
                if headlines:
                    lines = self.news_fetcher.format_for_board(headlines[0])
                    content = "\n".join(lines)
                    success = self.client.send_lines(lines)

            elif msg.message_type == "countdowns":
                lines = self.countdown_fetcher.format_for_board()
                content = "\n".join(lines)
                success = self.client.send_lines(lines)

            elif msg.message_type == "flights":
                lines = self.flight_fetcher.format_for_board()
                content = "\n".join(lines)
                success = self.client.send_lines(lines)

            else:
                print(f"Unknown message type: {msg.message_type}")

        except Exception as e:
            print(f"Error executing message {msg.name}: {e}")
            content = str(e)

        # Log the result
        self.storage.log_message(msg.message_type, content, success)
        if success:
            self.storage.update_last_run(msg.id)

        return success

    def check_and_run_scheduled(self):
        """Check all scheduled messages and run any that are due."""
        messages = self.storage.get_scheduled_messages(enabled_only=True)
        now = datetime.now()

        for msg in messages:
            try:
                cron = croniter(msg.cron_expression, msg.last_run or datetime(2000, 1, 1))
                next_run = cron.get_next(datetime)

                if next_run <= now:
                    print(f"Running scheduled message: {msg.name}")
                    self.execute_message(msg)

            except Exception as e:
                print(f"Error checking schedule for {msg.name}: {e}")

    def check_active_flights(self):
        """Check for active flights and update the board if status changes."""
        today = date.today()
        flights = self.storage.get_flights(enabled_only=True, include_past=False)

        for flight in flights:
            # Only check today's flights
            if flight.flight_date != today:
                continue

            try:
                # Fetch current status
                status = self.flight_fetcher.fetch(flight.flight_number, flight.flight_date)
                if not status:
                    continue

                flight_key = f"{flight.flight_number}_{flight.flight_date}"
                last_status = self._last_flight_status.get(flight_key)

                # Check if status changed or first check
                if last_status != status.status:
                    print(f"Flight {flight.flight_number} status: {status.status}")

                    # Update the board with flight info
                    lines = self.flight_fetcher.format_for_board(status, flight)
                    success = self.client.send_lines(lines)
                    self.storage.log_message("flight_auto", "\n".join(lines), success)

                    # Remember this status
                    self._last_flight_status[flight_key] = status.status

                    # Stop tracking if flight is complete
                    if status.status in COMPLETED_STATUSES:
                        print(f"Flight {flight.flight_number} complete ({status.status})")

            except Exception as e:
                print(f"Error checking flight {flight.flight_number}: {e}")

    def _flight_tracker_loop(self):
        """Background loop for flight tracking (runs every 10 minutes)."""
        while self._running:
            try:
                self.check_active_flights()
            except Exception as e:
                print(f"Flight tracker error: {e}")
            # Sleep for 10 minutes (600 seconds)
            for _ in range(600):
                if not self._running:
                    break
                time.sleep(1)

    def start(self, check_interval: int = 60):
        """Start the scheduler in a background thread.

        Args:
            check_interval: Seconds between schedule checks.
        """
        if self._running:
            return

        self._running = True

        def run_loop():
            while self._running:
                try:
                    self.check_and_run_scheduled()
                except Exception as e:
                    print(f"Scheduler error: {e}")
                time.sleep(check_interval)

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()
        print(f"Scheduler started (checking every {check_interval}s)")

        # Start flight tracker thread
        self._flight_thread = threading.Thread(target=self._flight_tracker_loop, daemon=True)
        self._flight_thread.start()
        print("Flight tracker started (checking every 10 minutes)")

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._flight_thread:
            self._flight_thread.join(timeout=5)
        print("Scheduler stopped")

    def add_default_schedules(self):
        """Add default scheduled messages if none exist."""
        existing = self.storage.get_scheduled_messages()
        if existing:
            return

        defaults = [
            ScheduledMessage(
                id=None,
                name="Morning Weather",
                message_type="weather",
                content=None,
                cron_expression="0 7 * * *",  # 7:00 AM daily
                enabled=True
            ),
            ScheduledMessage(
                id=None,
                name="Market Open",
                message_type="stocks",
                content=None,
                cron_expression="30 9 * * 1-5",  # 9:30 AM weekdays
                enabled=True
            ),
            ScheduledMessage(
                id=None,
                name="Daily Calendar",
                message_type="calendar",
                content=None,
                cron_expression="0 8 * * *",  # 8:00 AM daily
                enabled=False  # Disabled by default (needs calendar URL)
            ),
            ScheduledMessage(
                id=None,
                name="Good Morning",
                message_type="text",
                content="Good Morning!",
                cron_expression="0 6 * * *",  # 6:00 AM daily
                enabled=True
            ),
            ScheduledMessage(
                id=None,
                name="Good Night",
                message_type="text",
                content="Good Night!",
                cron_expression="0 22 * * *",  # 10:00 PM daily
                enabled=True
            ),
        ]

        for msg in defaults:
            self.storage.save_scheduled_message(msg)
            print(f"Added default schedule: {msg.name}")
