"""Data fetchers for various information sources."""

import requests
from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass

from .config import config


@dataclass
class WeatherData:
    """Weather information."""
    location: str
    temp_f: int
    condition: str
    high_f: int
    low_f: int
    humidity: int


@dataclass
class StockData:
    """Stock market data."""
    symbol: str
    price: float
    change: float
    change_percent: float


@dataclass
class CalendarEvent:
    """Calendar event."""
    title: str
    start_time: datetime
    all_day: bool


@dataclass
class NewsHeadline:
    """News headline."""
    title: str
    source: str


class WeatherFetcher:
    """Fetch weather data from OpenWeatherMap."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.openweather_api_key

    def fetch(self, location: Optional[str] = None) -> Optional[WeatherData]:
        """Fetch current weather.

        Args:
            location: Location string (e.g., "Seattle,WA,US").

        Returns:
            WeatherData or None if fetch failed.
        """
        if not self.api_key:
            print("OpenWeatherMap API key not configured")
            return None

        location = location or config.weather_location
        url = "https://api.openweathermap.org/data/2.5/weather"

        try:
            response = requests.get(
                url,
                params={
                    "q": location,
                    "appid": self.api_key,
                    "units": "imperial"
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            return WeatherData(
                location=data.get("name", location),
                temp_f=int(data["main"]["temp"]),
                condition=data["weather"][0]["main"],
                high_f=int(data["main"]["temp_max"]),
                low_f=int(data["main"]["temp_min"]),
                humidity=data["main"]["humidity"]
            )
        except Exception as e:
            print(f"Error fetching weather: {e}")
            return None

    def format_for_board(self, weather: WeatherData) -> list[str]:
        """Format weather data for Vestaboard display.

        Returns:
            List of lines for the board.
        """
        return [
            weather.location.upper(),
            "",
            f"{weather.temp_f}° {weather.condition.upper()}",
            "",
            f"HIGH {weather.high_f}°  LOW {weather.low_f}°",
            f"HUMIDITY {weather.humidity}%"
        ]


class StockFetcher:
    """Fetch stock data from Yahoo Finance."""

    def fetch(self, symbol: str) -> Optional[StockData]:
        """Fetch stock data for a symbol.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            StockData or None if fetch failed.
        """
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info

            price = info.get("regularMarketPrice") or info.get("currentPrice", 0)
            prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose", price)

            change = price - prev_close
            change_percent = (change / prev_close * 100) if prev_close else 0

            return StockData(
                symbol=symbol.upper(),
                price=round(price, 2),
                change=round(change, 2),
                change_percent=round(change_percent, 2)
            )
        except Exception as e:
            print(f"Error fetching stock {symbol}: {e}")
            return None

    def fetch_multiple(self, symbols: list[str] = None) -> list[StockData]:
        """Fetch data for multiple symbols.

        Args:
            symbols: List of ticker symbols.

        Returns:
            List of StockData.
        """
        symbols = symbols or config.stock_symbols
        results = []
        for symbol in symbols:
            data = self.fetch(symbol)
            if data:
                results.append(data)
        return results

    def format_for_board(self, stocks: list[StockData]) -> list[str]:
        """Format stock data for Vestaboard display.

        Returns:
            List of lines for the board.
        """
        lines = ["MARKETS"]
        lines.append("")

        for stock in stocks[:4]:  # Max 4 stocks to fit
            sign = "+" if stock.change >= 0 else ""
            lines.append(
                f"{stock.symbol} ${stock.price:.0f} {sign}{stock.change_percent:.1f}%"
            )

        return lines


class CalendarFetcher:
    """Fetch calendar events from ICS URL."""

    def __init__(self, calendar_url: Optional[str] = None):
        self.calendar_url = calendar_url or config.calendar_url

    def fetch_today(self) -> list[CalendarEvent]:
        """Fetch today's calendar events.

        Returns:
            List of CalendarEvent for today.
        """
        if not self.calendar_url:
            return []

        try:
            from icalendar import Calendar
            response = requests.get(self.calendar_url, timeout=10)
            response.raise_for_status()

            cal = Calendar.from_ical(response.text)
            today = date.today()
            events = []

            for component in cal.walk():
                if component.name == "VEVENT":
                    dtstart = component.get("dtstart")
                    if dtstart:
                        dt = dtstart.dt
                        if isinstance(dt, datetime):
                            event_date = dt.date()
                            all_day = False
                        else:
                            event_date = dt
                            all_day = True

                        if event_date == today:
                            events.append(CalendarEvent(
                                title=str(component.get("summary", "Event")),
                                start_time=dt if isinstance(dt, datetime) else datetime.combine(dt, datetime.min.time()),
                                all_day=all_day
                            ))

            # Sort by start time
            events.sort(key=lambda e: e.start_time)
            return events

        except Exception as e:
            print(f"Error fetching calendar: {e}")
            return []

    def format_for_board(self, events: list[CalendarEvent]) -> list[str]:
        """Format calendar events for Vestaboard display.

        Returns:
            List of lines for the board.
        """
        today = date.today()
        lines = [today.strftime("%A").upper(), today.strftime("%B %d").upper()]

        if not events:
            lines.append("")
            lines.append("NO EVENTS TODAY")
        else:
            lines.append("")
            for event in events[:3]:  # Max 3 events
                if event.all_day:
                    lines.append(event.title[:22].upper())
                else:
                    time_str = event.start_time.strftime("%I:%M%p").lstrip("0")
                    title = event.title[:15].upper()
                    lines.append(f"{time_str} {title}")

        return lines


class NewsFetcher:
    """Fetch news headlines."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.news_api_key

    def fetch_headlines(self, category: str = "general", count: int = 5) -> list[NewsHeadline]:
        """Fetch top headlines.

        Args:
            category: News category (business, technology, general, etc.).
            count: Number of headlines to fetch.

        Returns:
            List of NewsHeadline.
        """
        if not self.api_key:
            return []

        try:
            response = requests.get(
                "https://newsapi.org/v2/top-headlines",
                params={
                    "country": "us",
                    "category": category,
                    "pageSize": count,
                    "apiKey": self.api_key
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            headlines = []
            for article in data.get("articles", []):
                headlines.append(NewsHeadline(
                    title=article.get("title", ""),
                    source=article.get("source", {}).get("name", "")
                ))
            return headlines

        except Exception as e:
            print(f"Error fetching news: {e}")
            return []

    def format_for_board(self, headline: NewsHeadline) -> list[str]:
        """Format a single headline for Vestaboard display.

        Returns:
            List of lines for the board.
        """
        from .characters import wrap_text

        lines = ["NEWS"]
        lines.append("")

        # Wrap the headline text
        wrapped = wrap_text(headline.title.upper(), width=22)
        lines.extend(wrapped[:4])  # Max 4 lines for headline

        return lines


class CountdownFetcher:
    """Format countdowns for display."""

    def __init__(self, storage=None):
        self.storage = storage

    def get_active_countdowns(self) -> list[tuple[str, int]]:
        """Get active countdowns with days remaining.

        Returns:
            List of (name, days_remaining) tuples, sorted by days remaining.
        """
        if not self.storage:
            from .storage import Storage
            self.storage = Storage()

        countdowns = self.storage.get_countdowns(enabled_only=True, include_past=False)
        today = date.today()

        results = []
        for countdown in countdowns:
            days_remaining = (countdown.target_date - today).days
            if days_remaining >= 0:
                results.append((countdown.name, days_remaining))

        # Sort by days remaining (soonest first)
        results.sort(key=lambda x: x[1])
        return results

    def format_for_board(self, countdowns: list[tuple[str, int]] = None) -> list[str]:
        """Format countdowns for Vestaboard display.

        Args:
            countdowns: List of (name, days_remaining) tuples.
                       If None, fetches from storage.

        Returns:
            List of lines for the board.
        """
        if countdowns is None:
            countdowns = self.get_active_countdowns()

        if not countdowns:
            return [
                "COUNTDOWNS",
                "",
                "NO ACTIVE",
                "COUNTDOWNS",
                "",
                "ADD ONE IN THE APP"
            ]

        lines = ["COUNTDOWNS"]
        lines.append("")

        # Show up to 4 countdowns (to fit on 6-line display)
        for name, days in countdowns[:4]:
            # Truncate name to fit with days count
            # Format: "EVENT NAME    123 DAYS"
            if days == 0:
                day_str = "TODAY!"
            elif days == 1:
                day_str = "1 DAY"
            else:
                day_str = f"{days} DAYS"

            # Calculate max name length (22 - len(day_str) - 1 space)
            max_name_len = 22 - len(day_str) - 1
            truncated_name = name[:max_name_len].upper()

            # Pad to align days on right
            padding = 22 - len(truncated_name) - len(day_str)
            line = truncated_name + " " * padding + day_str
            lines.append(line)

        return lines
