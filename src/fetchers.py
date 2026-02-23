"""Data fetchers for various information sources."""

import requests
from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from .config import config

# Default timezone for display
LOCAL_TZ = ZoneInfo("America/Los_Angeles")


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

    def __init__(self, api_key: Optional[str] = None, storage=None):
        self.api_key = api_key or config.openweather_api_key
        self.storage = storage

    def get_location(self) -> str:
        """Get weather location from database or config."""
        if self.storage:
            saved = self.storage.get_setting("weather_location")
            if saved:
                return saved
        return config.weather_location or "Seattle,WA,US"

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

        location = location or self.get_location()
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

    def __init__(self, storage=None):
        self.storage = storage

    def get_symbols(self) -> list[str]:
        """Get stock symbols from database or config."""
        if self.storage:
            saved = self.storage.get_setting("stock_symbols")
            if saved:
                return [s.strip() for s in saved.split(",") if s.strip()]
        return config.stock_symbols or []

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
        symbols = symbols or self.get_symbols()
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
            # Show cents for prices under $10, whole numbers for $10+
            if stock.price < 10:
                price_str = f"${stock.price:.2f}"
            else:
                price_str = f"${stock.price:.0f}"
            lines.append(
                f"{stock.symbol} {price_str} {sign}{stock.change_percent:.1f}%"
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

        Shows up to 6 countdowns (one per line), with event name on the left
        and days remaining on the right.

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
                "",
                "NO COUNTDOWNS",
                "",
                "ADD EVENTS IN",
                "THE CONTROL PANEL",
                ""
            ]

        lines = []

        # Show up to 6 countdowns (one per line, fills entire board)
        for name, days in countdowns[:6]:
            # Format days string (right side)
            if days == 0:
                day_str = "TODAY!"
            elif days == 1:
                day_str = "1 DAY"
            else:
                day_str = f"{days}D"

            # Calculate max name length (22 - len(day_str) - 1 space minimum)
            max_name_len = 22 - len(day_str) - 1
            truncated_name = name[:max_name_len].upper()

            # Pad to align: name on left, days on right
            padding = 22 - len(truncated_name) - len(day_str)
            line = truncated_name + " " * padding + day_str
            lines.append(line)

        # Pad with empty lines if fewer than 6 countdowns
        while len(lines) < 6:
            lines.append("")

        return lines


@dataclass
class FlightStatus:
    """Flight status information."""
    flight_number: str
    airline: str
    departure_airport: str
    departure_code: str
    arrival_airport: str
    arrival_code: str
    status: str  # "scheduled", "active", "landed", "cancelled", "diverted"
    scheduled_departure: Optional[datetime]
    actual_departure: Optional[datetime]
    scheduled_arrival: Optional[datetime]
    actual_arrival: Optional[datetime]
    delay_minutes: int = 0


class FlightFetcher:
    """Fetch flight status from AirLabs API."""

    def __init__(self, api_key: Optional[str] = None, storage=None):
        self.api_key = api_key or config.airlabs_api_key
        self.storage = storage

    def fetch(self, flight_number: str, flight_date: date = None) -> Optional[FlightStatus]:
        """Fetch flight status.

        Args:
            flight_number: Flight number (e.g., "AA100").
            flight_date: Date of the flight.

        Returns:
            FlightStatus or None if not found.
        """
        if not self.api_key:
            print("AirLabs API key not configured")
            return None

        # Clean up flight number
        flight_number = flight_number.upper().replace(" ", "")

        try:
            # First try the schedules endpoint for future/scheduled flights
            params = {
                "api_key": self.api_key,
                "flight_iata": flight_number,
            }

            response = requests.get(
                "https://airlabs.co/api/v9/schedules",
                params=params,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                print(f"AirLabs error: {data['error']}")
                return None

            flights = data.get("response", [])

            # Filter by date if provided
            if flight_date and flights:
                matching = []
                for f in flights:
                    dep_time = f.get("dep_time", "")
                    if dep_time and dep_time.startswith(flight_date.isoformat()):
                        matching.append(f)
                if matching:
                    flights = matching

            if not flights:
                print(f"No flight found for {flight_number}")
                return None

            # Get the first matching flight
            flight = flights[0]

            # Parse times - prefer UTC times from AirLabs for accurate calculations
            def parse_time(time_str, is_utc=False):
                if not time_str:
                    return None
                try:
                    # Try parsing with timezone info first
                    if "+" in time_str or "Z" in time_str:
                        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    # Parse the time string
                    dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                    if is_utc:
                        # Mark as UTC
                        from datetime import timezone
                        return dt.replace(tzinfo=timezone.utc)
                    return dt
                except:
                    try:
                        dt = datetime.fromisoformat(time_str)
                        if is_utc:
                            from datetime import timezone
                            return dt.replace(tzinfo=timezone.utc)
                        return dt
                    except:
                        return None

            # Use UTC times for accurate time remaining calculations
            # Fall back to local times if UTC not available
            scheduled_dep = parse_time(flight.get("dep_time_utc"), is_utc=True)
            if not scheduled_dep:
                scheduled_dep = parse_time(flight.get("dep_time"))

            scheduled_arr = parse_time(flight.get("arr_time_utc"), is_utc=True)
            if not scheduled_arr:
                scheduled_arr = parse_time(flight.get("arr_time"))

            # AirLabs uses dep_delayed/arr_delayed for delays
            dep_delay = flight.get("dep_delayed") or 0
            arr_delay = flight.get("arr_delayed") or 0

            # Calculate actual times if delayed
            actual_dep = None
            actual_arr = None
            if dep_delay and scheduled_dep:
                from datetime import timedelta
                actual_dep = scheduled_dep + timedelta(minutes=dep_delay)
            if arr_delay and scheduled_arr:
                from datetime import timedelta
                actual_arr = scheduled_arr + timedelta(minutes=arr_delay)

            # Determine status
            status = flight.get("status", "scheduled")
            # Map AirLabs status to our format
            status_map = {
                "scheduled": "scheduled",
                "active": "active",
                "en-route": "active",
                "landed": "landed",
                "cancelled": "cancelled",
                "diverted": "diverted"
            }
            status = status_map.get(status.lower(), status) if status else "scheduled"

            # Get airline name from flight number prefix
            airline_code = flight.get("airline_iata", flight_number[:2])

            return FlightStatus(
                flight_number=flight_number,
                airline=flight.get("airline_name", airline_code),
                departure_airport=flight.get("dep_name", ""),
                departure_code=flight.get("dep_iata", ""),
                arrival_airport=flight.get("arr_name", ""),
                arrival_code=flight.get("arr_iata", ""),
                status=status,
                scheduled_departure=scheduled_dep,
                actual_departure=actual_dep,
                scheduled_arrival=scheduled_arr,
                actual_arrival=actual_arr,
                delay_minutes=dep_delay
            )

        except Exception as e:
            print(f"Error fetching flight {flight_number}: {e}")
            return None

    def get_tracked_flights(self) -> list[tuple]:
        """Get all tracked flights with their status.

        Returns:
            List of (TrackedFlight, FlightStatus) tuples.
        """
        if not self.storage:
            from .storage import Storage
            self.storage = Storage()

        flights = self.storage.get_flights(enabled_only=True, include_past=False)
        results = []

        for flight in flights:
            status = self.fetch(flight.flight_number, flight.flight_date)
            results.append((flight, status))

        return results

    def format_for_board(self, flight_status: FlightStatus = None, tracked_flight=None) -> list[str]:
        """Format flight status for Vestaboard display.

        Args:
            flight_status: FlightStatus object.
            tracked_flight: Optional TrackedFlight for context.

        Returns:
            List of lines for the board.
        """
        if not flight_status:
            # Try to get first tracked flight
            tracked = self.get_tracked_flights()
            if tracked:
                tracked_flight, flight_status = tracked[0]

        if not flight_status:
            return [
                "FLIGHT TRACKER",
                "",
                "NO FLIGHTS",
                "TRACKED",
                "",
                "ADD ONE IN THE APP"
            ]

        lines = []

        # Line 1: Flight number and route
        route = f"{flight_status.departure_code} TO {flight_status.arrival_code}"
        lines.append(f"{flight_status.flight_number} {route}")

        # Line 2: Airline (truncated)
        lines.append(flight_status.airline[:22].upper())

        # Line 3: Empty
        lines.append("")

        # Lines 4-5: Status specific info
        # Convert times to local timezone for display
        now = datetime.now(LOCAL_TZ)

        def to_local(dt):
            """Convert datetime to local timezone."""
            if dt is None:
                return None
            if dt.tzinfo is not None:
                return dt.astimezone(LOCAL_TZ)
            return dt

        if flight_status.status == "active":
            # In flight - show time remaining
            local_arrival = to_local(flight_status.scheduled_arrival)
            if local_arrival:
                remaining = local_arrival - now
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                if hours > 0:
                    lines.append(f"{hours}H {minutes}M REMAINING")
                else:
                    lines.append(f"{minutes}M REMAINING")
            else:
                lines.append("IN FLIGHT")
            lines.append("IN THE AIR")

        elif flight_status.status == "landed":
            lines.append("LANDED")
            local_arr = to_local(flight_status.actual_arrival)
            if local_arr:
                arr_time = local_arr.strftime("%I:%M %p").lstrip("0")
                lines.append(f"ARRIVED {arr_time}")
            else:
                lines.append("")

        elif flight_status.status == "cancelled":
            lines.append("CANCELLED")
            lines.append("")

        elif flight_status.status == "diverted":
            lines.append("DIVERTED")
            lines.append("")

        elif flight_status.status in ["scheduled", "unknown"]:
            # Show time until departure
            local_dep = to_local(flight_status.scheduled_departure)
            if local_dep:
                time_until = local_dep - now
                total_seconds = time_until.total_seconds()

                if total_seconds > 0:
                    hours = int(total_seconds // 3600)
                    minutes = int((total_seconds % 3600) // 60)
                    if hours > 24:
                        days = hours // 24
                        lines.append(f"DEPARTS IN {days}D")
                    elif hours > 0:
                        lines.append(f"DEPARTS IN {hours}H {minutes}M")
                    else:
                        lines.append(f"DEPARTS IN {minutes}M")
                else:
                    lines.append("DEPARTED")

                dep_time = local_dep.strftime("%I:%M %p").lstrip("0")
                lines.append(f"AT {dep_time}")
            else:
                lines.append("SCHEDULED")
                lines.append("")

        # Line 6: Delay info or on time
        if flight_status.delay_minutes > 0:
            lines.append(f"DELAYED {flight_status.delay_minutes} MIN")
        elif flight_status.status in ["scheduled", "active"]:
            lines.append("ON TIME")
        else:
            lines.append("")

        return lines[:6]  # Ensure max 6 lines
