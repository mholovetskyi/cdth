# 04 · Ready and Resilient: wildfire evacuation in northern Alberta

It is the morning briefing. Several wildfires are burning in northern Alberta, and a dry cold front is on its way. You coordinate the response. Here is what you have:
- what the satellites, the night's infrared mapping flights and the weather stations have told you so far
- the road network, aerodromes, reception centres and a fleet of buses and aircraft

You must decide who leaves, when, by which road and to where. If you move too late, people are still in town when the fire arrives. If you move too early, or move the wrong towns, people are uprooted for nothing and reception centres overflow.

**Fictional scenarios on real geography.** The fires, weather, forecasts, satellite detections, closures, reception-centre capacities, fleet and "needs transport" numbers are all synthetic. Real inputs:
- roads: National Road Network, Alberta
- fuel types: NRCan CFFDRS FBP Fuel Types 2024
- aerodromes and runway lengths: OurAirports
- community names and positions: GeoNames

Populations come from GeoNames where it has one. Otherwise they are marked `synthetic_estimate`. **This is not a forecast, a hazard map or a recreation of any real fire season.** The fire spread model is a simplified, FBP-inspired research model, not an operational tool.

## Two scenarios

| | `scenario_practice` | `scenario_eval` |
|---|---|---|
| Start (t0) | 2030-05-04 18:00Z | 2030-05-20 18:00Z |
| **Decision time** | **2030-05-07 06:00Z** (06:00 local) | **2030-05-23 12:00Z** (06:00 local) |
| End | 2030-05-10 18:00Z | 2030-05-26 18:00Z |
| Data after the decision time | released (so you can see what happened) | withheld |
| Truth | `scenario_practice/truth/` | held by the organizers |

For a fair practice run, only use data stamped at or before the decision time. The starter notebook has a helper for this.

## Files

`common/` (shared by both scenarios):

| File | What it is |
|---|---|
| `communities.csv` | 114 places. Columns are listed below. |
| `road_nodes.csv`, `road_edges.csv`, `road_edges.geojson` | Road graph between junctions: 4,007 nodes and 5,267 edges, with `length_km, travel_time_min, speed_kmh, capacity_vph, road_class, paved, route, name` |
| `aerodromes.csv` | 85 aerodromes with `longest_runway_ft, runway_surface, paved` |
| `host_sites.csv` | 26 reception centres and host sites with `capacity_people` (synthetic) |
| `fleet.csv` | 207 buses at 17 depots, plus turboprops, jets, light twins and helicopters, with seats, speed and runway needs (synthetic) |
| `weather_stations.csv` | 18 synthetic stations placed at aerodromes |
| `fuel_types_270m.tif`, `fuel_types_legend.csv` | Real FBP fuel types resampled to 270 m (EPSG:3978) |

Columns in `communities.csv`:
- `community_id, name, lat, lon`
- `population` and `population_source`
- `needs_transport`: people who cannot drive themselves
- `impact_radius_km`: the community footprint
- `access`: `road` or `air_only`
- `road_node_id`
- `exit_capacity_vph`: vehicles per hour that can leave town
- `nearest_aerodrome_id`: the nearest aerodrome within 25 km, any runway

`scenario_*/`:

| File | What it is |
|---|---|
| `scenario.json` | Times and fire IDs |
| `fire_reports.csv` | Daily 17:00 local situation reports: size, status and origin |
| `fire_perimeters_observed.geojson` | Nightly airborne infrared perimeters at 22:00 local. Some nights are missed. |
| `satellite_hotspots.csv` | FIRMS-style VIIRS and MODIS detections. Columns are listed below. |
| `weather_observations_hourly.csv` | Temperature, RH, wind, gust and precipitation per station |
| `weather_forecasts.csv` | 72 h hourly forecasts issued daily at 12:00 local. They contain realistic errors. |
| `fwi_daily.csv` | Canadian Fire Weather Index System codes (FFMC, DMC, DC, ISI, BUI, FWI) from noon observations |
| `road_closures.csv`, `aerodrome_closures.csv` | Closures announced so far |
| `truth/` (practice only) | Details below |

Columns in `satellite_hotspots.csv`:
- `latitude, longitude, bright_ti4, bright_ti5, scan, track, acq_time, satellite, instrument, confidence, frp, daynight`
- `type`: 0 is a vegetation fire, 2 is a static industrial source, such as the oil sands heat sources north of Fort McMurray.

What `truth/` contains (practice only):
- `community_fire_times.csv`: hours since t0 when fire came within 15 km and 5 km of each community's edge, and when it reached the community
- `road_closures_truth.csv` and `aerodrome_closures_truth.csv`
- `fire_perimeters_truth_3h.geojson` and `fire_arrival_hours.tif`

## Tasks
- **4A, threat outlook.** For each community, give `p_24h, p_48h, p_72h`: the probability that fire comes within 5 km of the community's edge in the next 24, 48 or 72 h after the decision time. Communities already within 5 km at the decision time are not scored. Metric: **mean Brier score** (lower is better).
- **4B, evacuation plan.** You submit two files, `orders.csv` and `trips.csv` (columns are listed below). Metric: the simulator's **plan score** (lower is better).
  - **Orders:** when an order is given, drivers leave along a response curve, limited by the town's exit capacity. They take the fastest road open at that time and re-route at closures.
  - **Trips:** buses and aircraft carry the `needs_transport` group. In `air_only` places, that is everyone.
  - **How a plan is simulated:** the scorer plays the plan forward against the true fire. A vehicle's trips run in order.
- **4C, perimeter nowcast.** GeoJSON polygons with a `fire_id` property, estimating each fire's burned area at the decision time. Metric: **mean IoU**.

Columns in `orders.csv`:
- `community_id, order_time, destination_host_id`
- `share` (optional): the fraction of drivers sent to that host. Use several rows to split a town.

Columns in `trips.csv`:
- `vehicle_id, depart_time, pickup_community_id, dropoff_host_id`

The plan score adds up these penalties:

| Penalty | Points | Counts |
|---|---|---|
| exposed | 100 per person | still in a community when the fire reaches it, including people sent to a host the fire reaches |
| trapped | 100 per person | caught on a road that closes while driving |
| close_calls | 10 per person | still at home when the fire comes within 5 km, if that happens after the decision time |
| overflow | 5 per person | arrivals above a host's capacity |
| unnecessary | 1 per person | moved from places the fire never came within 15 km of |
| failed_trips | 25 per trip | vehicle trips that fail: no runway, closed aerodrome, arriving after the fire, and so on |

The output also shows the do-nothing score for comparison.

## Scoring
```bash
python score.py forecast  --scenario scenario_practice --submission my_forecast.csv
python score.py plan      --scenario scenario_practice --orders my_orders.csv --trips my_trips.csv --details plan_details.csv
python score.py perimeter --scenario scenario_practice --submission my_perimeters.geojson
```
The organizers score `scenario_eval` the same way with `--truth <eval truth folder>`.

## Baseline (from `starter.ipynb`)

The baseline does three things:
- **4C:** combines the last infrared perimeter with buffered recent hotspots.
- **4A:** a heuristic based on distance to the fire edge and on alignment with the forecast wind.
- **4B:** a rule-based plan.
  - Order high-risk towns soon after the decision time.
  - Split drivers across hosts with spare capacity.
  - Shuttle buses from the nearest depots, and airlift `air_only` places.

| | Practice | Eval (hidden truth) |
|---|---|---|
| 4A mean Brier | 0.0031 | 0.0027 |
| 4B plan score | 5,400 (do nothing: 7,345,900) | 2,220 (do nothing: 778,630) |
| 4C mean IoU | 0.65 | 0.81 |

## Harder variants and ideas
- **Model the fire.** Spread it with the real fuel grid, the FWI codes and the forecast wind, and show the uncertainty.
- **Plan for the wind shift.** The cold front swings winds from southwest to northwest, and flanks become heads.
- **Smarter evacuation.** Try staged or zoned evacuations, contraflow, and pre-positioning buses before the order.
- **Live hotspots.** Treat satellite hotspots as a time series. Filter out the static industrial sources and estimate the rate of spread.
- **A coordinator dashboard.** Show what is known, what is forecast, recommended actions and why.
- **Real data.** See `CATALOG.md`: CWFIS, NASA FIRMS, Alberta historical wildfire data, MSC Datamart and GeoMet, NAAD alerts and the National Road Network.
