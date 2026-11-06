from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import get_settings


def today() -> date:
    """Today's date where the user lives, not where the server runs (Docker is in UTC)."""
    return datetime.now(ZoneInfo(get_settings().timezone)).date()
