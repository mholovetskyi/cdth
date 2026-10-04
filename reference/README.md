# Reference layers (real open data)

These layers are real, Canada-wide data under open licences, cut down and tidied for quick use. Use them with any challenge or your own project. Sources and attributions are in `../LICENSES.md`.

| File | Rows | Source and processing |
|---|---|---|
| `airports_canada.csv` | 3,365 | OurAirports (public domain). Canadian airports, heliports, seaplane bases and closed sites. Two duplicate records and one misplaced "YEG" record were removed. |
| `runways_canada.csv` | 1,587 | OurAirports runways for those airports: length, width, surface, lighting, ends, heading |
| `navaids_canada.csv` | 622 | OurAirports navaids: VOR, NDB, DME and others, with frequency and position |
| `drone_advisory_zones_approx.geojson` | 773 | Circles of 5.6 km around large and medium airports and 1.9 km around heliports, drawn from the OurAirports points. **These are approximate and not for flight planning.** Real drone rules and zones come from Transport Canada and NAV CANADA. |
| `power_plants_canada.csv` | 1,159 | WRI Global Power Plant Database v1.3 (CC BY 4.0): name, capacity in MW, fuel, owner and position. The data is several years old. |
| `communities_canada.csv` | 3,061 | GeoNames (CC BY 4.0): populated places with name, province, position, population where known, and time zone |
| `provinces_canada.geojson` | 13 | Natural Earth admin-1 boundaries (public domain) |
| `ports_canada.geojson` | 67 | Natural Earth ports (public domain) |
| `roads_canada.geojson` | 900 | Natural Earth 10 m roads for Canada (public domain). Coarse; for a detailed network use the National Road Network listed in `../CATALOG.md`. |
| `wildfires_alberta_2000_on.csv` | 35,498 | Canadian National Fire Database (CNFDB) fire points: Alberta, 2000 onward. Each row has an ID, position, dates, size in hectares, cause and type. |
| `wildfires_canada_200ha_plus.csv` | 21,678 | CNFDB fire points across Canada for fires of 200 ha or larger. `YEAR = -999` means the year is unknown. |

## Notes
- Coordinates are WGS84 decimal degrees.
- CNFDB data come from many agencies and their quality varies. Natural Resources Canada must be acknowledged whenever you display them (see `LICENSES.md`).
- Burned-area polygons (NBAC) are not included, because simplifying them would alter the official product. Download them from CWFIS if you need them.
