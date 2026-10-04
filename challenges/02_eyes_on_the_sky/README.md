# 02 · Eyes on the Sky: airspace awareness and counter-drone

Three sites near Edmonton each run a small sensor set:
- a radar
- two RF direction finders that hear a drone's controller link
- an acoustic array
- a camera with an onboard classifier

ADS-B shows manned aircraft that broadcast it. Your job is to work out what each track is and alert only when an unauthorized drone enters a protected zone. If you can, also locate the pilot.

**Synthetic data.** The sites are real places: Edmonton International Airport, Genesee Generating Station and the Royal Alexandra Hospital heliport. Everything else is fictional:
- the sensor deployments
- the tracks
- the flight authorizations and operators

The data says nothing about real security arrangements at these sites.

**Period.** 2025-09-15 06:00Z to 2025-09-22 06:00Z (7 days).
- **Labels released:** for tracks starting before 2025-09-20 06:00Z.
- **Hidden test window:** the last 2 days.
- One physical object can appear as several track fragments, because the tracker opens a new ID after a gap of more than 12 s. Labels are per track fragment.

## Files

| File | Rows | What it is |
|---|---|---|
| `sensor_tracks.csv` | 76,718 | Per-update fused tracks. Columns are listed below. |
| `sites.csv` | 3 | Site centre, alert radius and advisory radius |
| `sensors.csv` | 15 | Sensor positions: radar, two RF direction finders, acoustic array and camera per site |
| `zones.geojson` | 5 | Alert and advisory circles |
| `flight_authorizations.csv` | 11 | Approved drone flights: time window, area, max altitude, band and operator position |
| `labels_train/track_labels.csv` | 1,037 | Training labels. Columns are listed below. |

Columns in `sensor_tracks.csv`:
- `timestamp, site_id, track_id, lat, lon, alt_m, speed_mps, heading_deg, climb_mps, range_m`
- `rcs_dbsm`: radar cross-section
- `doppler_mod_hz`: micro-Doppler modulation, blank when not measurable
- `rf_detected, rf_band_ghz, rf_rssi_dbm, rf1_bearing_deg, rf2_bearing_deg`
- `adsb, adsb_icao`
- `acoustic_dba`
- `eo_label, eo_conf`

Columns in `track_labels.csv`:
- `track_id, site_id, start`
- `true_class`: drone_multirotor, drone_fixed_wing, bird, aircraft, helicopter, balloon or ground_vehicle
- `category`: drone, bird, manned or other
- `flight_pattern`
- `authorized, autonomous_no_rf, enters_alert_zone, zone_entry`
- `operator_lat, operator_lon`

## Tasks
- **2A, what is it:** predict `category` for every test track. Metric: **macro F1**.
- **2B, raise the alarm:** `alert = 1` when the track is a drone that is not authorized and enters its site's alert zone. Metric: **F1** of the alert class.
- **2C, find the pilot:** estimate `operator_lat, operator_lon` for RF-controlled drones. Metric: **median error in metres**. A blank estimate counts as 5,000 m.

Submission: `submissions/tracks.csv` with `track_id,category,alert,operator_lat,operator_lon`.

## Scoring
```bash
python score.py --submission submissions/tracks.csv --labels my_val_labels.csv
```

You can also call `from score import score_tracks` from Python.

## Baseline (from `starter.ipynb`)

The baseline has three parts:
- **Classifying tracks:** a random forest on per-track features.
- **Alerts:** a rule that fires on a predicted drone inside the alert circle with no matching authorization.
- **Finding the pilot:** the median of the crossing points of the two RF bearing lines.

| | Hidden test window |
|---|---|
| 2A macro F1 | 0.99 |
| 2B alert F1 | 1.00 |
| 2C median pilot error | 97 m (64% within 300 m) |

2A and 2B are warm-ups. The signals are clean, so a simple model already scores near the top.

## Harder variants and ideas
- **Decide early.** Classify and alert using only the first 10 seconds of each track. Speed matters more than accuracy after the fact.
- **Fewer sensors.** Drop RF, or drop RF and the camera, and see what radar alone can do. Then estimate the value of each sensor.
- **Pilots without bearings.** Find pilots when only one direction finder hears the link, or none (autonomous drones).
- **Re-join fragments.** Link fragmented tracks back into objects.
- **Build an operator console.** Show one alert per incident with a confidence and a reason, and make sure birds don't wake anyone up.
- **Real data.** See `CATALOG.md`: DroneRF, RFUAV, the Drone Detection Dataset (IR, video and audio), OpenSky ADS-B and OurAirports.
