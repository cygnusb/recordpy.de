"""FastAPI-App: API für die Karte + statisches Frontend + Live-Scheduler."""

import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from . import config, db, live

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

conn: sqlite3.Connection | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global conn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    conn = db.connect()
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        live.poll_all,
        "interval",
        args=[conn],
        minutes=config.LIVE_POLL_MINUTES,
        next_run_time=datetime.now(),  # sofort beim Start einmal pollen
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
    conn.close()


app = FastAPI(title="recordpy.de", lifespan=lifespan)


def _record(row) -> dict | None:
    if row is None:
        return None
    return {"value": row["value"], "date": row["record_date"]}


def _status(
    today_val: float | None, records: dict[str, dict | None], kind: str
) -> dict:
    """Vergleicht den heutigen Wert mit Tages-/Monats-/Allzeitrekord.

    kind="heat": today_val ist Tmax, Rekord gebrochen wenn größer.
    kind="cold": today_val ist Tmin, Rekord gebrochen wenn kleiner.
    """
    result = {"level": None, "near": False}
    if today_val is None:
        return result
    sign = 1 if kind == "heat" else -1
    for level in ("alltime", "month", "day"):
        rec = records.get(level)
        if rec is None:
            continue
        diff = sign * (today_val - rec["value"])
        if diff >= 0:
            result["level"] = level
            return result
    day_rec = records.get("day")
    if day_rec is not None and sign * (today_val - day_rec["value"]) >= -config.NEAR_RECORD_DELTA:
        result["near"] = True
    return result


@app.get("/api/stations")
def api_stations():
    now_local = datetime.now(ZoneInfo(config.LOCAL_TZ))
    today = now_local.date()
    month, day = today.month, today.day

    live_rows = {
        r["station_id"]: r
        for r in conn.execute("SELECT * FROM live_state WHERE date = ?", (today.isoformat(),))
    }
    daily = {
        (r["station_id"], r["kind"]): r
        for r in conn.execute(
            "SELECT * FROM daily_records WHERE month = ? AND day = ?", (month, day)
        )
    }
    monthly = {
        (r["station_id"], r["kind"]): r
        for r in conn.execute("SELECT * FROM monthly_records WHERE month = ?", (month,))
    }
    alltime = {
        (r["station_id"], r["kind"]): r for r in conn.execute("SELECT * FROM alltime_records")
    }

    stations = []
    for s in conn.execute("SELECT * FROM stations"):
        sid = s["id"]
        lr = live_rows.get(sid)
        tmax_today = lr["tmax_today"] if lr else None
        tmin_today = lr["tmin_today"] if lr else None
        high = {
            "day": _record(daily.get((sid, "high"))),
            "month": _record(monthly.get((sid, "high"))),
            "alltime": _record(alltime.get((sid, "high"))),
        }
        low = {
            "day": _record(daily.get((sid, "low"))),
            "month": _record(monthly.get((sid, "low"))),
            "alltime": _record(alltime.get((sid, "low"))),
        }
        stations.append(
            {
                "id": sid,
                "name": s["name"],
                "bundesland": s["bundesland"],
                "lat": s["lat"],
                "lon": s["lon"],
                "altitude": s["altitude"],
                "first_year": s["first_year"],
                "tmax_today": tmax_today,
                "tmin_today": tmin_today,
                "last_measurement": lr["last_measurement_at"] if lr else None,
                "records": {"high": high, "low": low},
                "heat": _status(tmax_today, high, "heat"),
                "cold": _status(tmin_today, low, "cold"),
            }
        )
    return {"date": today.isoformat(), "generated_at": now_local.isoformat(), "stations": stations}


@app.get("/api/stations/{station_id}")
def api_station_detail(station_id: str):
    s = conn.execute("SELECT * FROM stations WHERE id = ?", (station_id,)).fetchone()
    if s is None:
        raise HTTPException(status_code=404, detail="unknown station")
    monthly = [
        {"month": r["month"], "kind": r["kind"], "value": r["value"], "date": r["record_date"]}
        for r in conn.execute(
            "SELECT * FROM monthly_records WHERE station_id = ? ORDER BY month", (station_id,)
        )
    ]
    alltime = [
        {"kind": r["kind"], "value": r["value"], "date": r["record_date"]}
        for r in conn.execute("SELECT * FROM alltime_records WHERE station_id = ?", (station_id,))
    ]
    lr = conn.execute("SELECT * FROM live_state WHERE station_id = ?", (station_id,)).fetchone()
    return {
        "id": s["id"],
        "name": s["name"],
        "bundesland": s["bundesland"],
        "lat": s["lat"],
        "lon": s["lon"],
        "altitude": s["altitude"],
        "first_year": s["first_year"],
        "last_year": s["last_year"],
        "monthly_records": monthly,
        "alltime_records": alltime,
        "live": dict(lr) if lr else None,
    }


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
