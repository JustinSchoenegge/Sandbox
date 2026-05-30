import contextlib
import io
import json
import os
import warnings
from datetime import datetime, timedelta

from storage import atomic_save

# Must be registered before urllib3 is imported (fires at import time)
warnings.filterwarnings("ignore", message=".*LibreSSL.*")

CACHE_FILE = "data/prices_cache.json"
CACHE_TTL_MINUTES = 5       # disk cache TTL at startup
SESSION_TTL_MINUTES = 30    # per-price TTL within a session

_session_cache: dict = {}
_prev_close_cache: dict = {}
_price_fetched_at: dict = {}   # ticker → datetime of last network fetch
_cache_loaded = False
_cache_time = None


def _load_disk_cache():
    global _cache_loaded, _cache_time
    if _cache_loaded:
        return
    _cache_loaded = True
    if not os.path.exists(CACHE_FILE):
        return
    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)
        cached_at = datetime.fromisoformat(data.get("cached_at", ""))
        if datetime.now() - cached_at < timedelta(minutes=CACHE_TTL_MINUTES):
            _session_cache.update(data.get("prices", {}))
            _prev_close_cache.update(data.get("prev_closes", {}))
            _cache_time = cached_at
            # Treat all disk-loaded prices as fetched at disk cache time
            for ticker in _session_cache:
                _price_fetched_at[ticker] = cached_at
    except (json.JSONDecodeError, ValueError, KeyError):
        pass


def _save_disk_cache():
    global _cache_time
    _cache_time = datetime.now()
    atomic_save(CACHE_FILE, {
        "cached_at": _cache_time.isoformat(),
        "prices": _session_cache,
        "prev_closes": _prev_close_cache,
    })


def _session_price_stale(ticker: str) -> bool:
    """True if the in-session price is older than SESSION_TTL_MINUTES."""
    ts = _price_fetched_at.get(ticker)
    if ts is None:
        return True
    return (datetime.now() - ts).total_seconds() > SESSION_TTL_MINUTES * 60


def fetch_price(ticker, fallback=None):
    _load_disk_cache()
    if ticker in _session_cache and not _session_price_stale(ticker):
        return _session_cache[ticker]
    try:
        import yfinance as yf
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            info = yf.Ticker(ticker).fast_info
            price = info.last_price
            prev = info.previous_close
        if price and price > 0:
            _session_cache[ticker] = round(price, 2)
            _price_fetched_at[ticker] = datetime.now()
            if prev and prev > 0:
                _prev_close_cache[ticker] = round(prev, 2)
            _save_disk_cache()
            return _session_cache[ticker]
    except Exception:
        pass
    return fallback


def day_change_pct(ticker):
    """Return today's % change vs previous close, or None if unavailable."""
    _load_disk_cache()
    price = _session_cache.get(ticker)
    prev = _prev_close_cache.get(ticker)
    if price and prev and prev > 0:
        return (price - prev) / prev * 100
    return None


def last_updated_label():
    _load_disk_cache()
    if _cache_time:
        return f"live  •  Updated {_cache_time.strftime('%I:%M %p')}"
    return "approximate"


def cached_price(ticker: str) -> "float | None":
    """Return cached current price for ticker — no network calls, no blocking."""
    _load_disk_cache()
    if ticker in _session_cache and not _session_price_stale(ticker):
        return _session_cache[ticker]
    return None


def cached_changes() -> dict:
    """Day-change % for all tickers in disk cache. No network calls."""
    _load_disk_cache()
    result = {}
    for ticker in list(_session_cache.keys()):
        chg = day_change_pct(ticker)
        if chg is not None:
            result[ticker] = round(chg, 2)
    return result
