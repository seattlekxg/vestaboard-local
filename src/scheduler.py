"""Message scheduler using cron expressions."""

import threading
import time
from datetime import datetime
from typing import Callable, Optional

from croniter import croniter

from .client import VestaboardClient
from .fetchers import WeatherFetcher, StockFetcher, CalendarFetcher, NewsFetcher, CountdownFetcher, FlightFetcher
from .storage import Storage, ScheduledMessage


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
        self.stock_fetcher = StockFetcher()
        self.calendar_fetcher = CalendarFetcher()
        self.news_fetcher = NewsFetcher()
        self.countdown_fetcher = CountdownFetcher(storage=self.storage)
        self.flight_fetcher = FlightFetcher(storage=self.storage)

        self._running = False
        self._thread: Optional[threading.Thread] = None

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

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
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
