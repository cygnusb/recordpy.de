# recordpy.de

Temperaturrekorde Deutschland als Live-Karte — inspiriert von [recordpy.fr](https://recordpy.fr),
auf Basis von [DWD Open Data](https://opendata.dwd.de/climate_environment/CDC/) (CDC).

Für jede Wetterstation mit mindestens 30 Jahren Messhistorie und aktuellen
10-Minuten-Daten zeigt die Karte, wie nah die heutige Temperatur an den
historischen Rekorden liegt: Tagesrekord (gleicher Kalendertag), Monatsrekord
und Allzeitrekord — jeweils für Hitze (Tmax) und Kälte (Tmin).

## Setup

```sh
uv sync

# Einmalig (und danach z. B. monatlich): Historie laden, Rekorde berechnen.
# Lädt ~340 Stations-ZIPs vom DWD (Cache in data/cache/), dauert ein paar Minuten.
uv run python -m recordpy.ingest

# Webserver starten (pollt alle 15 min die DWD-Live-Daten)
uv run recordpy
```

Dann <http://localhost:8000> öffnen.

## Architektur

- `dwd.py` — Download + Parsing der DWD-Dateien (Stationslisten, Tageswerte `daily/kl`, 10-Minuten-Werte)
- `records.py` / `ingest.py` — Rekordberechnung und Import in SQLite (`data/recordpy.sqlite`)
- `live.py` — Poller für die heutigen Max/Min-Werte (`10_minutes/air_temperature/now`, ~30 min Latenz)
- `app.py` — FastAPI: `/api/stations` (Karte), `/api/stations/{id}` (Details), statisches Frontend
- `static/` — Leaflet-Karte (CARTO-Dark-Tiles), Hitze/Kälte-Umschalter, Filter nach Bundesland/Höhe

## Datenlizenz

Datenbasis: Deutscher Wetterdienst, eigene Elemente ergänzt. Die DWD-Daten stehen
unter der [GeoNutzV](https://www.gesetze-im-internet.de/geonutzv/) — Quellenvermerk erforderlich.

## Tests

```sh
uv run pytest
```
