"""Configuration management for Vestaboard automation."""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Application configuration."""

    # Vestaboard Local API
    vestaboard_local_url: str = ""
    vestaboard_local_key: str = ""

    # Weather API (OpenWeatherMap)
    openweather_api_key: Optional[str] = None
    weather_location: str = "Seattle,WA,US"

    # Stock symbols to track
    stock_symbols: list[str] = None

    # Calendar (Google Calendar ICS URL)
    calendar_url: Optional[str] = None

    # News API
    news_api_key: Optional[str] = None

    # Flight Tracking (AviationStack)
    aviationstack_api_key: Optional[str] = None

    # Web server
    web_host: str = "0.0.0.0"
    web_port: int = 8080

    # Database
    db_path: str = "data/vestaboard.db"

    def __post_init__(self):
        if self.stock_symbols is None:
            self.stock_symbols = ["SPY", "QQQ"]

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        stock_symbols_str = os.getenv("STOCK_SYMBOLS", "SPY,QQQ")
        stock_symbols = [s.strip() for s in stock_symbols_str.split(",")]

        return cls(
            vestaboard_local_url=os.getenv("VESTABOARD_LOCAL_URL", ""),
            vestaboard_local_key=os.getenv("VESTABOARD_LOCAL_KEY", ""),
            openweather_api_key=os.getenv("OPENWEATHER_API_KEY"),
            weather_location=os.getenv("WEATHER_LOCATION", "Seattle,WA,US"),
            stock_symbols=stock_symbols,
            calendar_url=os.getenv("CALENDAR_URL"),
            news_api_key=os.getenv("NEWS_API_KEY"),
            aviationstack_api_key=os.getenv("AVIATIONSTACK_API_KEY"),
            web_host=os.getenv("WEB_HOST", "0.0.0.0"),
            web_port=int(os.getenv("WEB_PORT", "8080")),
            db_path=os.getenv("DB_PATH", "data/vestaboard.db"),
        )


config = Config.from_env()
