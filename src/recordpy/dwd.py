"""Download und Parsing der DWD-Open-Data-Dateien (CDC)."""

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

from . import config

MISSING = -999.0


@dataclass(frozen=True)
class StationInfo:
    id: str  # fünfstellig, z. B. "02667"
    von: date
    bis: date
    altitude: int
    lat: float
    lon: float
    name: str
    bundesland: str


@dataclass(frozen=True)
class DailyValue:
    day: date
    tmax: float | None  # TXK
    tmin: float | None  # TNK


_STATION_RE = re.compile(
    r"^(?P<id>\d{5}) (?P<von>\d{8}) (?P<bis>\d{8})\s+(?P<alt>-?\d+)\s+"
    r"(?P<lat>-?\d+\.\d+)\s+(?P<lon>-?\d+\.\d+)\s+(?P<rest>\S.*)$"
)


def parse_station_list(text: str) -> list[StationInfo]:
    """Parst eine DWD-Stationsbeschreibungsdatei (latin-1-dekodierter Text)."""
    stations = []
    for line in text.splitlines()[2:]:  # Header + Trennzeile überspringen
        m = _STATION_RE.match(line.rstrip())
        if not m:
            continue
        # Name und Bundesland sind durch >=2 Spaces getrennt; Namen können
        # einzelne Spaces enthalten ("Donaueschingen (Landeplatz)").
        rest = re.split(r"\s{2,}", m.group("rest"))
        stations.append(
            StationInfo(
                id=m.group("id"),
                von=datetime.strptime(m.group("von"), "%Y%m%d").date(),
                bis=datetime.strptime(m.group("bis"), "%Y%m%d").date(),
                altitude=int(m.group("alt")),
                lat=float(m.group("lat")),
                lon=float(m.group("lon")),
                name=rest[0],
                bundesland=rest[1] if len(rest) > 1 else "",
            )
        )
    return stations


def parse_daily_kl(data: bytes) -> list[DailyValue]:
    """Extrahiert TXK/TNK aus einer produkt_klima_tag-Datei (Rohbytes)."""
    lines = data.decode("latin-1").splitlines()
    header = [h.strip() for h in lines[0].split(";")]
    i_date, i_txk, i_tnk = header.index("MESS_DATUM"), header.index("TXK"), header.index("TNK")
    values = []
    for line in lines[1:]:
        fields = line.split(";")
        if len(fields) <= max(i_txk, i_tnk):
            continue
        txk = float(fields[i_txk])
        tnk = float(fields[i_tnk])
        values.append(
            DailyValue(
                day=datetime.strptime(fields[i_date].strip(), "%Y%m%d").date(),
                tmax=None if txk == MISSING else txk,
                tmin=None if tnk == MISSING else tnk,
            )
        )
    return values


def parse_10min_tu(data: bytes) -> list[tuple[datetime, float]]:
    """Extrahiert (Zeitstempel UTC, TT_10) aus einer produkt_zehn_now_tu-Datei."""
    lines = data.decode("latin-1").splitlines()
    header = [h.strip() for h in lines[0].split(";")]
    i_date, i_tt = header.index("MESS_DATUM"), header.index("TT_10")
    values = []
    for line in lines[1:]:
        fields = line.split(";")
        if len(fields) <= i_tt:
            continue
        tt = float(fields[i_tt])
        if tt == MISSING:
            continue
        ts = datetime.strptime(fields[i_date].strip(), "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
        values.append((ts, tt))
    return values


def read_zip_member(data: bytes, prefix: str = "produkt") -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if Path(name).name.startswith(prefix):
                return zf.read(name)
    raise FileNotFoundError(f"no member starting with {prefix!r} in zip")


class DwdClient:
    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or config.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.http = httpx.Client(timeout=60, follow_redirects=True)
        self._historical_index: dict[str, str] | None = None

    def close(self) -> None:
        self.http.close()

    def _get(self, url: str) -> bytes:
        resp = self.http.get(url)
        resp.raise_for_status()
        return resp.content

    def _get_cached(self, url: str, filename: str, refresh: bool = False) -> bytes:
        path = self.cache_dir / filename
        if path.exists() and not refresh:
            return path.read_bytes()
        data = self._get(url)
        path.write_bytes(data)
        return data

    def kl_stations(self) -> list[StationInfo]:
        data = self._get(config.DAILY_KL_HISTORICAL + config.KL_STATIONS_FILE)
        return parse_station_list(data.decode("latin-1"))

    def tu_now_stations(self) -> list[StationInfo]:
        data = self._get(config.TU_NOW + config.TU_NOW_STATIONS_FILE)
        return parse_station_list(data.decode("latin-1"))

    def _historical_zip_name(self, station_id: str) -> str | None:
        """Die historical-Dateinamen enthalten den Datenzeitraum und müssen
        aus dem Verzeichnisindex ermittelt werden."""
        if self._historical_index is None:
            html = self._get(config.DAILY_KL_HISTORICAL).decode("latin-1")
            self._historical_index = {
                m.group(1): m.group(0)
                for m in re.finditer(r"tageswerte_KL_(\d{5})_\d{8}_\d{8}_hist\.zip", html)
            }
        return self._historical_index.get(station_id)

    def daily_values(self, station_id: str) -> list[DailyValue]:
        """Komplette Tageswert-Reihe einer Station (historical + recent)."""
        values: dict[date, DailyValue] = {}
        zip_name = self._historical_zip_name(station_id)
        if zip_name:
            data = self._get_cached(config.DAILY_KL_HISTORICAL + zip_name, zip_name)
            for v in parse_daily_kl(read_zip_member(data)):
                values[v.day] = v
        try:
            data = self._get(config.DAILY_KL_RECENT + f"tageswerte_KL_{station_id}_akt.zip")
        except httpx.HTTPStatusError:
            data = None
        if data:
            for v in parse_daily_kl(read_zip_member(data)):
                values[v.day] = v  # recent überschreibt historical am Übergang
        return [values[d] for d in sorted(values)]

    def now_values(self, station_id: str) -> list[tuple[datetime, float]]:
        data = self._get(config.TU_NOW + f"10minutenwerte_TU_{station_id}_now.zip")
        return parse_10min_tu(read_zip_member(data))
