<p align="center">
  <a href="https://cdth.ca"><img src="assets/banner.webp" alt="Canada's Defence Tech Hackathon — Edmonton + Online" width="100%"></a>
</p>

<h1 align="center">CDTH Data Kit</h1>

<p align="center">
  <b>Practice data, starter notebooks and open datasets for Canada's Defence Tech Hackathon.</b><br>
  November 14–15, 2026 · Edmonton and online across Canada
</p>

<p align="center">
  <a href="https://cdth.ca"><img alt="cdth.ca" src="https://img.shields.io/badge/cdth.ca-website-FF5A4E?style=for-the-badge&labelColor=0B0F14"></a>
  <img alt="Nov 14–15, 2026" src="https://img.shields.io/badge/Nov_14–15-2026-2FD8A0?style=for-the-badge&labelColor=0B0F14">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10+-E8ECEF?style=for-the-badge&logo=python&logoColor=E8ECEF&labelColor=0B0F14">
  <a href="LICENSES.md"><img alt="Open licences" src="https://img.shields.io/badge/data-open_licences-E8ECEF?style=for-the-badge&labelColor=0B0F14"></a>
</p>

<p align="center">
  <a href="#-quick-start">Quick start</a> ·
  <a href="#-the-four-challenges">Challenges</a> ·
  <a href="#-how-scoring-works">Scoring</a> ·
  <a href="CATALOG.md">Dataset catalogue</a> ·
  <a href="reference/README.md">Reference layers</a> ·
  <a href="#-licence">Licence</a>
</p>

---

The kit gives teams something real to build on from the first hour.

| | | |
|:---:|---|---|
| 🎯 | **4 practice challenges** | One per theme, with ready-to-use data, labels for a training window and a scoring script. Answers for a hidden test window are held back so results can be compared fairly. |
| 📓 | **4 starter notebooks** | Each one loads the data, draws a map, runs a simple baseline, scores it and writes a correctly formatted submission. |
| 🗺️ | **Real Canadian reference layers** | Airports, runways, navaids, power plants, communities, ports, roads, provinces and historical wildfires, all under open licences. |
| 📚 | **69 real public datasets** | Catalogued by theme in [`CATALOG.md`](CATALOG.md). Each one was checked on 2026-10-04 with a link, its licence and how to get access. |

> [!IMPORTANT]
> **Practice data is synthetic.** The challenge scenarios are fictional and made by computer. The ships, drones, jammers, fires and weather are not real, and no file contains classified, sensitive or personal information. Real geography is used where noted: places, roads, aerodromes and fuel types. Do not treat anything in `challenges/` as a description of real events, real capabilities or real vulnerabilities.

## 🚀 Quick start

```bash
git clone https://github.com/mholovetskyi/cdth.git && cd cdth
python -m pip install -r requirements.txt
cd challenges/01_arctic_watch
jupyter lab starter.ipynb          # or open it in VS Code / Colab
```

Every starter notebook runs top to bottom in **under a minute** on a laptop.

## 🧭 The four challenges

<table>
<tr>
<td width="50%" valign="top">

### 🧊 [01 · Arctic Watch](challenges/01_arctic_watch)
**Maritime awareness in the Canadian Arctic**

14 days of AIS ship positions on real Arctic routes, satellite radar (SAR) detections and areas of interest.

- **1A** — tell AIS ships, "dark" ships and clutter apart in SAR
- **1B** — find suspicious behaviour: AIS gaps, spoofing, rendezvous, MMSI cloning and more

</td>
<td width="50%" valign="top">

### 🛸 [02 · Eyes on the Sky](challenges/02_eyes_on_the_sky)
**Airspace awareness and counter-drone**

7 days of fused sensor tracks at three Edmonton-area sites: radar, RF direction finding, ADS-B, acoustic and a camera classifier.

- **2A** — drone, bird, manned aircraft or other?
- **2B** — alert on unauthorized drones entering protected zones
- **2C** — find the pilot

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 📡 [03 · Stay Connected](challenges/03_stay_connected)
**Resilient positioning, navigation and timing**

7 days of GNSS receiver logs from fixed stations, vehicles and aircraft in central Alberta.

- **3A** — nominal, natural, jamming or spoofing?
- **3B** — locate the interference source
- **3C** — recover the true position while spoofed

</td>
<td width="50%" valign="top">

### 🔥 [04 · Ready and Resilient](challenges/04_ready_and_resilient)
**Emergency response and infrastructure resilience**

Two fictional wildfire scenarios in northern Alberta built on real roads, communities, aerodromes and NRCan fuel types, with satellite hotspots, infrared perimeters, weather, forecasts and Fire Weather Index.

- **4A** — which communities will the fire threaten?
- **4B** — plan the evacuation (scored by a simulator)
- **4C** — nowcast the fire perimeter

</td>
</tr>
</table>

Each challenge folder has its own `README.md` datasheet with file schemas, task definitions, metrics, submission formats and baseline scores.

## 🏁 How scoring works

**Challenges 01–03** release labels for the first days (`labels_train/`) and keep the last days hidden.
1. Make your own validation slice from `labels_train/`, for example the last training day.
2. Score it with the challenge's `score.py`. The organizers run the same script on the hidden days.

**Challenge 04** has two scenarios.
- `scenario_practice` comes with its full truth, so you can see exactly what happened after the decision time.
- `scenario_eval` stops at the decision time, and the organizers hold its truth.

All scripts need only standard Python data tools and print a JSON summary. Run `python score.py --help` in any challenge folder.

> [!NOTE]
> Hidden-test answer keys are not in this repository. Organizers hold them separately.

## 📁 Folder layout

```
.
├── README.md                 this file
├── LICENSES.md               sources, licences and required attributions
├── CATALOG.md                69 real public datasets by theme (also catalog.csv)
├── requirements.txt
├── reference/                real open data layers for Canada (see reference/README.md)
└── challenges/
    ├── 01_arctic_watch/          data, labels_train/, starter.ipynb, score.py, README.md
    ├── 02_eyes_on_the_sky/       ...
    ├── 03_stay_connected/        ...
    └── 04_ready_and_resilient/   common/, scenario_practice/ (with truth/), scenario_eval/, ...
```

## 🌐 Time and coordinates

| | |
|---|---|
| **Timestamps** | ISO 8601 UTC (`...Z`). Alberta local time is UTC−6 in the challenge periods (Mountain Daylight Time). |
| **Coordinates** | WGS84 latitude and longitude in decimal degrees. |
| **Rasters (04)** | EPSG:3978, NAD83 / Canada Atlas Lambert. In this region grid north is 15–20° off true north, while wind directions are given relative to true north. |

## 💡 Using the data well

- **Keep to the decision time.** In challenge 04, only use information available at the decision time in your eval run. Each notebook includes a helper for this.
- **Simple labels.** The labels are simple on purpose. Several tasks have a strong simple baseline, so the interesting work is often in speed, explanation, fusion, interfaces and robustness rather than a slightly higher F1. Each datasheet lists harder variants.
- **Real data for the weekend.** If you build on real data during the event, [`CATALOG.md`](CATALOG.md) lists sources with licences and access notes. Check the licence before you ship anything commercial.

## ⚖️ Licence

- **Code** (starter notebooks, `score.py` scripts): MIT, see [`LICENSE`](LICENSE).
- **Synthetic practice data** in `challenges/`: free to use during and after the event. Keep the "synthetic" notice when you share it.
- **Real reference data** in `reference/` and challenge 04: each source keeps its own open licence (public domain, CC BY 4.0, OGL-Canada). Required attributions are in [`LICENSES.md`](LICENSES.md).
- **Catalogued datasets** in [`CATALOG.md`](CATALOG.md) are not redistributed here; check each one's licence.

## ✉️ Questions

Contact the organizers through [cdth.ca](https://cdth.ca). When you report a data problem, include the file name and the row.

---

<p align="center">
  <img src="assets/logo.webp" alt="CDTH maple leaf" width="96"><br>
  <sub>Canada's Defence Tech Hackathon · Edmonton + Online · 53.54°N 113.49°W</sub>
</p>
