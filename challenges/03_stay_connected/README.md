# 03 · Stay Connected: resilient positioning, navigation and timing

GNSS (GPS, Galileo and others) gives position and time to phones, vehicles, aircraft, power grids and networks. Two things can go wrong deliberately:
- **Jamming** drowns the signal. Signal-to-noise (C/N0) falls, and the receiver's automatic gain control (AGC) drops as it fights the extra power.
- **Spoofing** feeds the receiver fake signals. The signals look healthy, often too uniform, while the reported position and clock drift away.

Geomagnetic storms and downtown streets also degrade GNSS. They are natural causes and should not raise a security alarm. Your job is to tell all of these apart, from receiver logs alone.

**Synthetic data.** Every jammer, spoofer, storm and receiver track is made up.
- **Receivers:** fixed stations sit at real towns in central Alberta. Vehicles drive approximate highway alignments, and aircraft fly approaches and departures at Edmonton International.
- **Physics:** the signal model uses the standard effective C/N0 relation and free-space loss at 1575.42 MHz. It is simplified, not a receiver emulator.

**Period.** 2025-10-06 06:00Z to 2025-10-13 06:00Z (7 days).
- **Labels released:** before 2025-10-11 06:00Z.
- **Hidden test window:** the last 2 days.
- The last training day happens to be quiet, so the starter notebook validates leave-one-day-out instead.

## Files

| File | Rows | What it is |
|---|---|---|
| `gnss_logs.csv` | 148,824 | One row per receiver epoch. Columns are listed below. |
| `receivers.csv` | 88 | 12 fixed stations (with surveyed positions), 20 vehicles and 56 aircraft |
| `highways_approx.geojson` | 6 | Approximate road alignments used by the simulator |
| `labels_train/epoch_labels.csv` | 104,090 | `timestamp, receiver_id, state` (nominal / natural / jamming / spoofing), `true_lat, true_lon` |
| `labels_train/interference_events.csv` | 4 | `event_id, kind, mobile, start, end, lat_at_midpoint, lon_at_midpoint, power_dbm, note` |

Columns in `gnss_logs.csv`:
- `timestamp, receiver_id, receiver_type`
- `lat, lon, alt_m, speed_mps`: what the receiver reports
- `fix_type, sats_tracked, sats_used`
- `cn0_mean_dbhz, cn0_std_dbhz`
- `agc_db`
- `hdop, pos_err_est_m`
- `clock_bias_ns`

Logging rates differ by receiver: fixed stations log every 120 s, and vehicles and aircraft every 10 s.

## Tasks
- **3A, what is happening:** give a `state` for every test epoch. Metric: **macro F1** over the 4 states.
- **3B, find the source:** report each jamming or spoofing event with `kind, start, end, lat, lon`. Metric: **mean location error (km)**, plus detection F1.
  - An event matches when the kind is the same and the times overlap, allowing 1 hour of slack.
  - An unmatched true event counts as 50 km, and matched errors are capped at 50 km.
- **3C, where is it really (optional):** for spoofed epochs, add `est_lat, est_lon` to the 3A file. Metric: **median error (m)**.

Submissions:
- `submissions/epoch_states.csv`: `timestamp,receiver_id,state[,est_lat,est_lon]`
- `submissions/interference_sources.csv`: `kind,start,end,lat,lon`

## Scoring
```bash
python score.py states  --submission submissions/epoch_states.csv         --labels my_val_epochs.csv
python score.py sources --submission submissions/interference_sources.csv --events my_val_events.csv
```

## Baseline (from `starter.ipynb`)

- **3A:** gradient boosting on features measured against each receiver's own normal: AGC drop, C/N0 level and spread, clock jumps, implied versus reported speed, and network-wide context.
- **3B:** groups flagged epochs into events and places each source at the AGC-weighted centre of the affected receivers.
- **3C:** holds the last trusted position.

| | Hidden test window |
|---|---|
| 3A macro F1 | 0.99 |
| 3B mean location error | 10.6 km (all 3 events found) |
| 3C median error | 1,029 m |

3A is a warm-up. The localisation tasks are where there is room to improve.

## Harder variants and ideas
- **Detect fast.** Flag jamming within one epoch of onset, and measure detection delay.
- **Fixed stations only.** Locate a moving jammer using only the 12 fixed stations, the way a city-wide monitoring network would.
- **Track the jammer.** Follow a mobile jammer along the highway over time, not just at the midpoint.
- **Fuse other sources.** Combine with dead reckoning (speed and heading) to ride through jamming.
- **Real data.** See `CATALOG.md`: Jammertest 2025, TEXBAT, the Tuni2025 spoofing IQ data, Android raw GNSS logs and NOAA SWPC space weather.
