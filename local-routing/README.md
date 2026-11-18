# Local transmission routing experiment

This isolated prototype is separate from the repository's existing root app. It is not deployed and does not alter the current service. It provides a local FastAPI map, state switching, OpenStreetMap tiles, click-to-select endpoints, PYORPS routing, and optional screening overlays from a separately supplied GIS dataset.

Requires Python 3.12 and the packages listed in `requirements.txt`. These dependencies are scoped to this prototype and do not change the existing root deployment. Point `PYORPS_DATA_DIR` to the separate `PYORPS_MISO_NYISO_Data` directory, or place it in your Downloads directory. The data files are not included in this repository.

```powershell
$env:PYORPS_DATA_DIR = 'C:\path\to\PYORPS_MISO_NYISO_Data'
python -m uvicorn app:app --host 127.0.0.1 --port 8769
```

Then open http://127.0.0.1:8769/. Run `npm test` for the frontend syntax check. The code assembles a temporary route surface from intersecting GIS tiles, so memory use and route resolution vary with route length. The full raster data and prepared virtual mosaics are not stored in GitHub. Dataset setup and installation must be handled before any server deployment. OpenStreetMap tiles require internet access.

## Scope

The state selector changes the map view. The backend determines actual route states from generalized 2025 Census 1:20m boundaries and applies MISO's MTEP24 single-circuit state rates in 2024 dollars. New York and any other state without a guide rate require a user-entered rate. The route uses a 3 km search buffer; a better route may exist outside it. The estimated dollars do not use the routing weight values, and separate substation costs are excluded. User-adjustable, ordinal preferences live in `weights.json`.

MISO and New York footprints are planning masks. The MISO source is a 2021 public territory polygon; the NYISO mask is a New York state proxy. Source protected-area polygons have different designations and are discouraged rather than treated as universally prohibited. Invalid geometries are repaired in memory for routing; original data are not altered. NWI values above zero are conservatively penalized, but the bundle's value legend is unverified. This is not a complete siting, permitting, parcel, or legal boundary analysis. Parcel boundaries, tribal areas, floodplains, cultural sites, land rights, and many other constraints are not represented. See `boundary_audit.json` for feature counts and geometry validity, which describe this bundle and are not counts of independent legal boundaries.

## Five nearby POIs and line voltage

Click a start and choose “Find and route nearest 5 POIs.” The five nearest are chosen by straight-line great-circle distance, then PYORPS calculates each route separately. A route can fail if the source data do not cover it; the failure is shown beside that POI. Nearest does not mean electrically compatible, available for interconnection, or feasible. POIs can share coordinates and represent different buses. The voltage selector uses 69, 115, 138, 230 and 345 kV single-circuit estimates from MISO MTEP24 Table 4.1-1. They are a shortlist based on the most frequently tagged voltage values in a local nationwide OpenStreetMap line-segment extract, not a verified ranking of projects built. All MISO states with published rates are supported. Route preferences are not voltage-specific.

`poi_coordinates_clean.csv` contains 10,012 rows with valid values in the supplied latitude and longitude columns; 2,833 rows without such a pair were omitted. Estimated-only coordinates were not promoted into those columns. The original status and source columns are retained. Source names and coordinates are not independently validated by this app; some are HIFLD name matches rather than MISO's public map locations.

## Separate frontend and API

`routing-config.js` defaults to a same-origin API for local use. For a Workers-hosted copy of the map, set `window.ROUTING_API_BASE` to the actual HTTPS Render service origin and serve the map HTML, CSS, JS, and config together. Set the backend environment variable `CORS_ORIGINS` to the exact frontend origin; it accepts comma-separated origins. Never set an invented URL. The existing API service must have the GIS bundle at `PYORPS_DATA_DIR`, and its bundled POI CSV beside the code.

The 4.81 GiB GIS folder is stored in GitHub release archives, not Git history. `gis_release_manifest.json` maps each original file to an archive and records checksums. Set `PYORPS_DATA_BASE_URL` to the release download base URL. The backend downloads and checks only the archives needed for each route, and uses temporary storage unless `PYORPS_DATA_DIR` specifies another directory. It downloads the relevant regional PAD-US GeoPackage in full; the MISO file alone is about 220 MiB. A local HTTP source is accepted only when the explicit test flag `PYORPS_ALLOW_LOCAL_HTTP=1` is set; do not use it in deployment. The downloader expects a publicly readable URL.

`../render.yaml` is a draft Blueprint for a separate Free service with a Python 3.12 build. Do not create the service until the GitHub release is published and accessible. Render Free has an ephemeral filesystem and 512 MB RAM, so downloaded files disappear after restart or spin-down. A local HTTP simulation confirmed selective archive downloads and a real route, but the Render build, runtime, memory and CPU use have not been tested. Five routes are computed sequentially and can be slow or exceed free-tier resources. The code has not been integrated into the existing Workers site or deployed.
