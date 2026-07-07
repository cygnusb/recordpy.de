from datetime import date, timezone
from pathlib import Path

from recordpy.dwd import (
    DailyValue,
    parse_10min_tu,
    parse_daily_kl,
    parse_station_list,
    read_zip_member,
)
from recordpy.records import compute_records

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_station_list():
    text = (FIXTURES / "kl_stations_sample.txt").read_bytes().decode("latin-1")
    stations = parse_station_list(text)
    assert len(stations) == 48
    aach = stations[0]
    assert aach.id == "00001"
    assert aach.name == "Aach"
    assert aach.bundesland == "Baden-Württemberg"
    assert aach.von == date(1937, 1, 1)
    assert aach.altitude == 478
    assert abs(aach.lat - 47.8413) < 1e-6
    # station name containing spaces/parentheses
    donaueschingen = next(s for s in stations if s.id == "00011")
    assert donaueschingen.name == "Donaueschingen (Landeplatz)"


def test_parse_daily_kl():
    values = parse_daily_kl((FIXTURES / "produkt_klima_tag_sample.txt").read_bytes())
    assert values[0] == DailyValue(day=date(1957, 9, 1), tmax=16.8, tmin=11.9)
    # SDK is -999 in the first line — must not affect TXK/TNK
    assert all(v.tmax is None or -60 < v.tmax < 60 for v in values)


def test_parse_10min_now_zip():
    data = read_zip_member((FIXTURES / "10minutenwerte_TU_02667_now.zip").read_bytes())
    values = parse_10min_tu(data)
    assert values
    ts, tt = values[0]
    assert ts.tzinfo == timezone.utc
    assert -60 < tt < 60


def test_compute_records():
    values = [
        DailyValue(date(2000, 7, 7), tmax=30.0, tmin=15.0),
        DailyValue(date(2001, 7, 7), tmax=32.0, tmin=14.0),
        DailyValue(date(2001, 7, 8), tmax=28.0, tmin=None),
        DailyValue(date(2002, 1, 1), tmax=5.0, tmin=-10.0),
    ]
    r = compute_records(values)
    assert r.first_year == 2000 and r.last_year == 2002
    assert r.daily_high[(7, 7)].value == 32.0
    assert r.daily_high[(7, 7)].record_date == date(2001, 7, 7)
    assert r.daily_low[(7, 7)].value == 14.0
    assert (7, 8) not in r.daily_low  # tmin fehlt
    assert r.monthly_high[7].value == 32.0
    assert r.alltime_high.value == 32.0
    assert r.alltime_low.value == -10.0
