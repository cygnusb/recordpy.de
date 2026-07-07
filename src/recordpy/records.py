"""Berechnung der Temperaturrekorde aus einer Tageswert-Reihe."""

from dataclasses import dataclass, field
from datetime import date

from .dwd import DailyValue


@dataclass
class Record:
    value: float
    record_date: date


@dataclass
class StationRecords:
    # Schlüssel: (Monat, Tag) bzw. Monat
    daily_high: dict[tuple[int, int], Record] = field(default_factory=dict)
    daily_low: dict[tuple[int, int], Record] = field(default_factory=dict)
    monthly_high: dict[int, Record] = field(default_factory=dict)
    monthly_low: dict[int, Record] = field(default_factory=dict)
    alltime_high: Record | None = None
    alltime_low: Record | None = None
    first_year: int | None = None
    last_year: int | None = None


def _update_high(current: Record | None, value: float, day: date) -> Record:
    # Bei Gleichstand gewinnt das jüngere Datum ("Rekord eingestellt").
    if current is None or value >= current.value:
        return Record(value, day)
    return current


def _update_low(current: Record | None, value: float, day: date) -> Record:
    if current is None or value <= current.value:
        return Record(value, day)
    return current


def compute_records(values: list[DailyValue]) -> StationRecords:
    r = StationRecords()
    for v in values:
        if v.tmax is None and v.tmin is None:
            continue
        if r.first_year is None:
            r.first_year = v.day.year
        r.last_year = v.day.year
        md = (v.day.month, v.day.day)
        if v.tmax is not None:
            r.daily_high[md] = _update_high(r.daily_high.get(md), v.tmax, v.day)
            r.monthly_high[v.day.month] = _update_high(
                r.monthly_high.get(v.day.month), v.tmax, v.day
            )
            r.alltime_high = _update_high(r.alltime_high, v.tmax, v.day)
        if v.tmin is not None:
            r.daily_low[md] = _update_low(r.daily_low.get(md), v.tmin, v.day)
            r.monthly_low[v.day.month] = _update_low(r.monthly_low.get(v.day.month), v.tmin, v.day)
            r.alltime_low = _update_low(r.alltime_low, v.tmin, v.day)
    return r
