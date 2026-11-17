# 345-kV local routing experiment

This isolated prototype is separate from the repository's existing root app. It is not deployed and does not alter the current service. It provides a local FastAPI map, state switching, OpenStreetMap tiles, click-to-select endpoints, PYORPS routing, and optional screening overlays from a separately supplied GIS dataset.

Requires Python, FastAPI, Uvicorn, GeoPandas, Rasterio, NumPy, Shapely, Pillow and PYORPS 0.4.0 in an existing environment. No dependency changes are made to the repository's current deployment. Point `PYORPS_DATA_DIR` to the separate `PYORPS_MISO_NYISO_Data` directory, or place it in your Downloads directory. The data files are not included in this repository.

```powershell
$env:PYORPS_DATA_DIR = 'C:\path\to\PYORPS_MISO_NYISO_Data'
python -m uvicorn app:app --host 127.0.0.1 --port 8769
```

Then open http://127.0.0.1:8769/. Run `npm test` for the frontend syntax check. The code assembles a temporary route surface from intersecting GIS tiles, so memory use and route resolution vary with route length. The full raster data and prepared virtual mosaics are not stored in GitHub. Dataset setup and installation must be handled before any server deployment. OpenStreetMap tiles require internet access.

## Scope

The state selector changes the map view. The backend determines actual route states from generalized 2025 Census 1:20m boundaries and applies MISO's MTEP24 single-circuit state rates in 2024 dollars. New York and any other state without a guide rate require a user-entered rate. The route uses a 3 km search buffer; a better route may exist outside it. The estimated dollars do not use the routing weight values, and separate substation costs are excluded. User-adjustable, ordinal preferences live in `weights.json`.

MISO and New York footprints are planning masks. The MISO source is a 2021 public territory polygon; the NYISO mask is a New York state proxy. Source protected-area polygons have different designations and are discouraged rather than treated as universally prohibited. Invalid geometries are repaired in memory for routing; original data are not altered. NWI values above zero are conservatively penalized, but the bundle's value legend is unverified. This is not a complete siting, permitting, parcel, or legal boundary analysis. Parcel boundaries, tribal areas, floodplains, cultural sites, land rights, and many other constraints are not represented. See `boundary_audit.json` for feature counts and geometry validity, which describe this bundle and are not counts of independent legal boundaries.

This local prototype has an open CORS policy. It must be restricted and separately reviewed before public deployment. Do not expose it directly as an unprotected public service or assume it is ready for Render's free-tier resource limits. There is no deployed website integration yet.
