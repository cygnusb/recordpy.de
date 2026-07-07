"""Live-Poller: 10-Minuten-Daten holen und heutiges Max/Min je Station pflegen."""

import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config
from .dwd import DwdClient

log = logging.getLogger(__name__)

TZ = ZoneInfo(config.LOCAL_TZ)


def poll_station(client: DwdClient, station_id: str) -> tuple[str, float, float, datetime] | None:
    """Liefert (Datum lokal, Tmax, Tmin, letzte Messung) für heute — oder None."""
    values = [(ts.astimezone(TZ), tt) for ts, tt in client.now_values(station_id)]
    today = datetime.now(TZ).date()
    todays = [(ts, tt) for ts, tt in values if ts.date() == today]
    if not todays:
        return None
    temps = [tt for _, tt in todays]
    last_ts = max(ts for ts, _ in todays)
    return today.isoformat(), max(temps), min(temps), last_ts


def poll_all(conn: sqlite3.Connection, client: DwdClient | None = None) -> None:
    own_client = client is None
    client = client or DwdClient()
    station_ids = [row["id"] for row in conn.execute("SELECT id FROM stations")]
    log.info("Live-Poll für %d Stationen", len(station_ids))

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(poll_station, client, sid): sid for sid in station_ids}
        for future in as_completed(futures):
            sid = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                log.warning("Station %s: %s", sid, exc)
                continue
            if result:
                results.append((sid, *result))

    with conn:
        for sid, day, tmax, tmin, last_ts in results:
            conn.execute(
                "INSERT OR REPLACE INTO live_state VALUES (?,?,?,?,?)",
                (sid, day, tmax, tmin, last_ts.isoformat()),
            )
    log.info("Live-Poll fertig: %d/%d Stationen mit heutigen Daten", len(results), len(station_ids))
    if own_client:
        client.close()
