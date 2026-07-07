const HEAT_COLORS = {
  alltime: { color: "#b3001b", label: "Allzeitrekord gebrochen" },
  month: { color: "#e63946", label: "Monatsrekord gebrochen" },
  day: { color: "#ff6d3f", label: "Tagesrekord gebrochen" },
  near: { color: "#ffb454", label: "nah am Tagesrekord" },
  none: { color: "#5a6577", label: "kein Rekord" },
  nodata: { color: "#333a48", label: "keine aktuellen Daten" },
};
const COLD_COLORS = {
  alltime: { color: "#0335ff", label: "Allzeitrekord gebrochen" },
  month: { color: "#2f6fed", label: "Monatsrekord gebrochen" },
  day: { color: "#41a5ee", label: "Tagesrekord gebrochen" },
  near: { color: "#8fd0ff", label: "nah am Tagesrekord" },
  none: { color: "#5a6577", label: "kein Rekord" },
  nodata: { color: "#333a48", label: "keine aktuellen Daten" },
};

let mode = "heat";
let stations = [];
let markers = new Map();

const map = L.map("map", { zoomSnap: 0.5 }).setView([51.2, 10.3], 6);
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
  maxZoom: 12,
}).addTo(map);

function statusKey(st) {
  const s = mode === "heat" ? st.heat : st.cold;
  const today = mode === "heat" ? st.tmax_today : st.tmin_today;
  if (today === null) return "nodata";
  if (s.level) return s.level;
  if (s.near) return "near";
  return "none";
}

function colors() {
  return mode === "heat" ? HEAT_COLORS : COLD_COLORS;
}

function fmtTemp(v) {
  return v === null || v === undefined ? "–" : v.toFixed(1).replace(".", ",") + " °C";
}
function fmtDate(iso) {
  if (!iso) return "–";
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

function recordRow(label, rec, todayVal) {
  if (!rec) return "";
  return `<tr><td>${label}</td><td class="val">${fmtTemp(rec.value)}</td><td class="date">${fmtDate(rec.date)}</td></tr>`;
}

function showPanel(st) {
  const c = colors();
  const key = statusKey(st);
  const recs = mode === "heat" ? st.records.high : st.records.low;
  document.getElementById("panel-content").innerHTML = `
    <h2>${st.name}</h2>
    <div class="meta">${st.bundesland} · ${st.altitude} m · Daten seit ${st.first_year}</div>
    <span class="badge" style="background:${c[key].color}">${c[key].label}</span>
    <div class="today-vals">
      <span class="hot">▲ ${fmtTemp(st.tmax_today)}</span>
      <span class="cold">▼ ${fmtTemp(st.tmin_today)}</span>
    </div>
    <div class="meta">heutiges Max/Min${st.last_measurement ? ", letzte Messung " + st.last_measurement.slice(11, 16) + " Uhr" : ""}</div>
    <table>
      <tr><th>${mode === "heat" ? "Hitzerekorde" : "Kälterekorde"}</th><th></th><th></th></tr>
      ${recordRow("heutiger Kalendertag", recs.day)}
      ${recordRow("laufender Monat", recs.month)}
      ${recordRow("Allzeit", recs.alltime)}
    </table>`;
  document.getElementById("panel").classList.remove("hidden");
}

function passesFilter(st) {
  const land = document.getElementById("filter-land").value;
  if (land && st.bundesland !== land) return false;
  const maxAlt = document.getElementById("filter-alt").value;
  if (maxAlt !== "" && st.altitude > Number(maxAlt)) return false;
  return true;
}

function render() {
  const c = colors();
  for (const st of stations) {
    const m = markers.get(st.id);
    if (!passesFilter(st)) {
      map.removeLayer(m);
      continue;
    }
    if (!map.hasLayer(m)) m.addTo(map);
    const key = statusKey(st);
    m.setStyle({
      fillColor: c[key].color,
      radius: key === "none" || key === "nodata" ? 4.5 : 7,
    });
    if (key !== "none" && key !== "nodata") m.bringToFront();
  }
  renderLegend();
}

function renderLegend() {
  const c = colors();
  document.getElementById("legend").innerHTML = ["alltime", "month", "day", "near", "none", "nodata"]
    .map((k) => `<span><i style="background:${c[k].color}"></i>${c[k].label}</span>`)
    .join("");
}

async function load() {
  const resp = await fetch("api/stations");
  const data = await resp.json();
  stations = data.stations;
  document.getElementById("generated-at").textContent = data.generated_at.slice(0, 16).replace("T", " ");

  const laender = [...new Set(stations.map((s) => s.bundesland))].sort();
  const sel = document.getElementById("filter-land");
  sel.length = 1;
  for (const l of laender) sel.add(new Option(l, l));

  for (const m of markers.values()) map.removeLayer(m);
  markers.clear();
  for (const st of stations) {
    const m = L.circleMarker([st.lat, st.lon], {
      radius: 5, weight: 1, color: "#0b0e13", fillOpacity: 0.95,
    });
    m.on("click", () => showPanel(st));
    markers.set(st.id, m);
  }
  render();
}

document.getElementById("mode-heat").addEventListener("click", () => {
  mode = "heat";
  document.getElementById("mode-heat").classList.add("active");
  document.getElementById("mode-cold").classList.remove("active");
  render();
});
document.getElementById("mode-cold").addEventListener("click", () => {
  mode = "cold";
  document.getElementById("mode-cold").classList.add("active");
  document.getElementById("mode-heat").classList.remove("active");
  render();
});
document.getElementById("filter-land").addEventListener("change", render);
document.getElementById("filter-alt").addEventListener("input", render);
document.getElementById("panel-close").addEventListener("click", () =>
  document.getElementById("panel").classList.add("hidden")
);

load();
setInterval(load, 5 * 60 * 1000);
