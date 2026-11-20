# Energy Platform snapshot and Render service

Recorded November 20, 2026. This is a record of the existing configuration, not a deployment instruction or a change to the service.

## Render routing backend

- Service: `pyorps-backend` (Python web service, Free compute, Virginia US East).
- URL: https://pyorps-backend.onrender.com
- Repository: https://github.com/maxbegun1/pyorps-backend
- Render source branch: `codex/pyorps-local-routing-map`.
- Last successfully deployed backend commit observed: `3cec184373848a33e8aa94ee01a74fc89094e85d`.
- Root directory: `local-routing`.
- Build command: `pip install -r requirements.txt`.
- Start command: `PYORPS_DATA_BASE_URL=https://github.com/maxbegun1/pyorps-backend/releases/download/pyorps-gis-20261117 CORS_ORIGINS=https://queue-atlas-research-preview.mbbegun.workers.dev uvicorn app:app --host 0.0.0.0 --port $PORT`.
- Health check path: `/health`.
- Geographic files are retrieved as needed from the existing GitHub release, cached on Render's temporary filesystem, and discarded on spin-down or restart. The snapshot does not include the full GIS archives.
- Free service sleeps after inactivity; startup and GIS retrieval can delay routing. Health success alone does not prove a route calculation works.

## Cloudflare dashboard

- Dashboard: https://energy-platform-predictor-preview.mbbegun.workers.dev/
- Worker: `energy-platform-predictor-preview`.
- Deployed version observed: `3560b1ad-83e6-4f6c-bc3a-e058135acdc5`.
- Dashboard proxies routing requests to the Render backend. MISO and NYISO timelines use separate age-based research benchmarks; NYISO Queue-time v2 appears only as a comparison in the NYISO results.

## Snapshot

`local-routing-snapshots/energy-platform-snapshot-20261120-132450.zip` contains the local routing project, Queue Atlas UI, regional model files and a file checksum manifest as they stood when saved. It is a local source snapshot; it is not a claim that every included file is deployed. Git metadata, earlier snapshots, installed packages, bytecode caches and the separately hosted GIS release are excluded. No credentials or deployment hooks are recorded here.
