# 01 · Arctic Watch: maritime awareness in the Canadian Arctic

Ships at sea report their identity and position over **AIS**. Some switch it off, fake it or borrow another ship's identity. Satellite radar (**SAR**) sees ships whether or not they transmit, but it also picks up icebergs and clutter. Your job is to use the two together to find what doesn't add up.

**Synthetic data.** All 112 ships and their voyages, the SAR passes, detections and behaviour events are made up.
- **Routes:** voyages follow real Arctic water corridors, routed on Natural Earth coastlines.
- **Identities:** MMSIs start with 999, which is not an assigned country code. Names, call signs and flags are random, and flags carry no signal.
- **Areas:** the areas of interest are illustrative. `AOI_DAVIS_CLOSED` is fictional.

**Period.** 2025-09-01 00:00Z to 2025-09-15 00:00Z (14 days).
- **Labels released:** before 2025-09-10 00:00Z (training window).
- **Hidden test window:** 2025-09-10 to 2025-09-15.
- SAR detections are split by timestamp and behaviour events by their midpoint.

## Files

| File | Rows | What it is |
|---|---|---|
| `ais_positions.csv` | 94,065 | `timestamp, mmsi, lat, lon, sog` (knots), `cog, heading` (deg), `nav_status` (AIS code), `source` (terrestrial / satellite) |
| `vessels.csv` | 112 | AIS static data: `mmsi, name, call_sign, ais_type_code, ais_type, flag, length_m, beam_m, draught_m, declared_destination` |
| `ais_receivers.csv` | 13 | Terrestrial AIS stations with a nominal 70 km range (outside it you rely on satellite AIS, which has gaps) |
| `sar_detections.csv` | 1,270 | `detection_id, pass_id, timestamp, lat, lon, length_m, heading_deg` (blank if unknown), `confidence` |
| `sar_passes.geojson` | 90 | Pass footprints (`mode`: routine or tasked; tasked passes were cued to a location) |
| `areas_of_interest.geojson` | 5 | Lancaster Sound, Hudson Strait, Queen Maud Gulf, Beaufort approaches and a fictional closed fishing area |
| `labels_train/sar_detection_labels.csv` | 652 | `detection_id, label` (ais_vessel / dark_vessel / not_vessel), `truth_class, truth_mmsi` |
| `labels_train/behaviour_events.csv` | 15 | `event_id, event_type, mmsi, start, end, note` |

## Tasks

**1A: what did the radar see?** Label every SAR detection in the test window:
- `ais_vessel`: a ship with its AIS on
- `dark_vessel`: a ship with no AIS
- `not_vessel`: iceberg or clutter

Submission: `submissions/sar_labels.csv` with `detection_id,label`. The metric is **macro F1** over the three classes.

**1B: what are ships doing?** Find events in the test window:
- `ais_gap_intentional`
- `protected_area_entry`
- `loitering`
- `rendezvous`
- `position_spoofing`
- `identity_change`
- `mmsi_clone`

Submission: `submissions/behaviour_events.csv` with `event_type,mmsi,start,end`. Use `;` to list several MMSIs, and `DARK` for an unidentified partner.

A prediction matches a true event when:
- the event type is the same
- the MMSI sets share at least one value
- the times overlap, allowing 2 hours of slack

Matching is one-to-one. The metric is **micro F1**.

## Scoring

```bash
python score.py sar    --submission submissions/sar_labels.csv       --labels my_val_sar_labels.csv
python score.py events --submission submissions/behaviour_events.csv --labels my_val_events.csv \
       --window-start 2025-09-08T00:00:00Z --window-end 2025-09-10T00:00:00Z
```

You can also import `score_sar` and `score_events` from Python.

## Baseline (from `starter.ipynb`)

**1A:**
- If a ship's AIS track, interpolated to the detection time, passes within 2 km, the detection is `ais_vessel`.
- Otherwise a random forest decides, using length, confidence, distance to AIS and nearby density.

**1B:** a handful of transparent rules.

| | Hidden test window |
|---|---|
| 1A macro F1 | 0.93 |
| 1B micro F1 | 0.84 (precision 0.93, recall 0.76) |

## Harder variants and ideas
- Find dark ships using SAR alone: drop the AIS-matching shortcut and use only detection features and context.
- Predict where a dark vessel will be at the next SAR pass, then task the pass, as the tasked passes in the data do.
- Detect rendezvous with a dark partner, which the baseline misses.
- Build a live operator view: a timeline of alerts, an explanation for each and one-click evidence.
- For real data, see `CATALOG.md`: Norwegian open AIS, Global Fishing Watch SAR detections, Canadian Ice Service charts and RADARSAT-1.
