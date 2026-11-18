# Local POI and MISO model preview

Start the API from this folder with the `pyorps-env` environment and open http://127.0.0.1:8769/. It uses the existing local GIS data by default. This preview is not deployed to the website.

Blue circles are mapped POIs. Hover or focus a circle to see its queue name when available, otherwise its map/bus name, voltage, and coordinate provenance. Click a start on the map, then click a POI to set the destination. The map shows up to 500 POIs in the view; zoom in to see additional markers. The coordinate file has 10,012 rows, with 150 matched queue names. Names and coordinates do not establish interconnection feasibility.

The MISO project forecast lookup reads `miso_week13_forecasts.csv`, copied from `regional_models/MISO/Miso Models Week 13/results/current_active_forecasts_with_flags.csv` at repository commit `9d24176b6af0d954b8c07d47a0160771374e5ed8`. It selects the most recent available annual snapshot for the specified project ID. It reports operational and withdrawal probabilities for four quarters after that snapshot. The source output is historical, through 2025Q4 at most, and is not a live prediction for a new project or a POI. The model does not predict months to IA or COD. Refer to the source model's README and MODEL_EVALUATION.md for methods and limits.
