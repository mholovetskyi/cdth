# Sources, licences and attributions

## Synthetic practice data
These folders contain synthetic data generated for Canada's Defence Tech Hackathon:
- `challenges/01_arctic_watch`
- `challenges/02_eyes_on_the_sky`
- `challenges/03_stay_connected`
- the scenario files in `challenges/04_ready_and_resilient`

Ships, voyages, radar detections, drone and sensor tracks, GNSS logs, jammers, spoofers, fires, weather, forecasts, closures, capacities and fleets are all fictional.

The synthetic data, starter notebooks and scoring scripts may be used freely by participants during and after the event. Keep the "synthetic" notice when you share them.

## Real inputs used in the kit

| Data | Used in | Licence | Attribution |
|---|---|---|---|
| OurAirports airports, runways and navaids | `reference/`, challenge 04 aerodromes | Public domain | "Airport data: OurAirports (ourairports.com)" (courtesy, not required) |
| Natural Earth: land, minor islands, admin-1, ports, roads, lakes | `reference/`; Arctic water routing for challenge 01 | Public domain | "Made with Natural Earth" (courtesy) |
| GeoNames populated places | `reference/communities_canada.csv`; challenge 04 community names, positions and populations | CC BY 4.0 | "Contains data from GeoNames (geonames.org), licensed under CC BY 4.0" |
| WRI Global Power Plant Database v1.3.0 | `reference/power_plants_canada.csv` | CC BY 4.0 | "Global Power Plant Database v1.3.0, World Resources Institute, CC BY 4.0" |
| Canadian National Fire Database (CNFDB), fire points | `reference/wildfires_*.csv` | Open Government Licence – Canada (OGL-Canada) | "Canadian National Fire Database – Agency Fire Data. Natural Resources Canada, Canadian Forest Service, Northern Forestry Centre, Edmonton, Alberta." When displaying the data, acknowledge Natural Resources Canada as the source. Do not misrepresent or falsely modify the data. |
| National Road Network (NRN), Alberta, edition 17 | challenge 04 road graph | Open Government Licence – Canada | "Contains information licensed under the Open Government Licence – Canada" (Statistics Canada / Natural Resources Canada) |
| CFFDRS FBP Fuel Types 2024 | challenge 04 `fuel_types_270m.tif` (resampled from 30 m to 270 m by mode) | Open Government Licence – Canada | "Contains information licensed under the Open Government Licence – Canada" (Natural Resources Canada, Canadian Forest Service) |

## Derived products and their limits
These products are **not authoritative**:
- **Road graph and exit capacities (challenge 04).** Simplified from NRN. Speeds and capacities are assumptions.
- **Resampled fuel grid (challenge 04).** Resampled from the 30 m FBP Fuel Types layer.
- **Drone advisory circles (`reference/`).** Drawn around OurAirports points.

Do not use any of them for navigation, flight planning, emergency operations or public safety decisions.

## Methods referenced (no data copied)
- **Fire Weather Index System equations:** Van Wagner & Pickett (1985); hourly FFMC after Van Wagner (1977).
- **Fire Behaviour Prediction fuel-type rate-of-spread curves:** Forestry Canada Fire Danger Group (1992), ST-X-3.

The kit's fire model is a simplified research implementation, not the official CFFDRS software.

## Datasets listed in CATALOG.md
Those datasets are not redistributed here. Each has its own licence, shown in `catalog.csv`. Several are non-commercial or share-alike, so read the terms before using them in a product.
