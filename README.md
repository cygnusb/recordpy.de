# recordpy.de

Temperaturrekorde Deutschland als Live-Karte — inspiriert von [recordpy.fr](https://recordpy.fr),
auf Basis von [DWD Open Data](https://opendata.dwd.de/climate_environment/CDC/) (CDC).

Für jede Wetterstation mit mindestens 30 Jahren Messhistorie und aktuellen
10-Minuten-Daten zeigt die Karte, wie nah die heutige Temperatur an den
historischen Rekorden liegt: Tagesrekord (gleicher Kalendertag), Monatsrekord
und Allzeitrekord — jeweils für Hitze (Tmax) und Kälte (Tmin).

## Betrieb mit Docker (empfohlen)

```sh
docker compose up -d
```

Dann <http://localhost:8000> öffnen. Beim ersten Start lädt der Container die
komplette DWD-Historie (~340 Stations-ZIPs, ein paar Minuten) automatisch in
das Volume `recordpy-data`; die Karte füllt sich, sobald der Import fertig ist.

Danach laufen zwei Scheduler-Jobs im Container:

- **Live-Poll** alle 15 min (`RECORDPY_LIVE_POLL_MINUTES`): heutiges Max/Min
  aller Stationen aus den DWD-10-Minuten-Daten — das ist der "aktuelle Tagesstand"
  auf der Karte. Häufiger als ~15 min lohnt nicht, der DWD publiziert die
  Daten selbst nur mit ~30 min Latenz.
- **Ingest** täglich um `RECORDPY_INGEST_HOUR`:30 (Default 04:30): Rekorde aus
  der Tageswert-Historie neu berechnen. Täglich reicht, weil der DWD die
  `daily/kl`-recent-Daten nur einmal pro Tag aktualisiert.

## Setup ohne Docker

```sh
uv sync
uv run python -m recordpy.ingest   # einmalig: Historie laden, Rekorde berechnen
uv run recordpy                    # Webserver auf Port 8000
```

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
