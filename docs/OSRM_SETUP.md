# OSRM Setup

The backend uses a self-hosted OSRM service for real road distances, travel
times, route legs, and route geometry.

## Map File

The Tunisia OpenStreetMap extract is stored locally at:

```text
osrm-data/tunisia-latest.osm.pbf
```

Source:

```text
https://download.geofabrik.de/africa/tunisia-latest.osm.pbf
```

The downloaded file verified on June 8, 2026:

```text
Size:   83,789,183 bytes
SHA256: 2BAE4C5357450859C759AEBE2010F5FAF7DE522D4DBA5CB442B00F3D570FD1C2
```

## One-Time OSRM Preprocessing

Run these commands from the repository root, `coficab_platform`.

```powershell
docker run --rm -t -v "${PWD}/osrm-data:/data" osrm/osrm-backend:latest `
  osrm-extract -p /opt/car.lua /data/tunisia-latest.osm.pbf

docker run --rm -t -v "${PWD}/osrm-data:/data" osrm/osrm-backend:latest `
  osrm-partition /data/tunisia-latest.osrm

docker run --rm -t -v "${PWD}/osrm-data:/data" osrm/osrm-backend:latest `
  osrm-customize /data/tunisia-latest.osrm
```

After preprocessing, `osrm-data/` should contain `tunisia-latest.osrm` plus
related OSRM sidecar files.

## Run OSRM

The Docker Compose files include an `osrm` service:

```powershell
docker compose up osrm
```

The backend expects:

```text
OSRM_BASE_URL=http://osrm:5000
OSRM_PROFILE=driving
```

For a host-machine smoke test after `osrm` starts:

```powershell
Invoke-RestMethod "http://localhost:5000/nearest/v1/driving/10.2316,36.7703"
```

The response should include `"code": "Ok"`.
