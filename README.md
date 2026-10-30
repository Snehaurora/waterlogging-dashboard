# Identification of Waterlogging Locations Using LiDAR (CEC-201 Term Project, Team 11)

CEC-201 Geospatial Engineering II, Department of Civil Engineering, IIT Roorkee, AY 2026-27 (guide: Prof. Prakhar Misra).
Area of interest: the part of the IIT Roorkee campus covered by the LiDAR-derived DTM (about 1.2 km x 0.9 km, EPSG:32643).

## What this repository contains

| File | Purpose |
|---|---|
| `app.py` | Streamlit dashboard (intro page, hotspot map, effect-of-buildings tab, method tab) |
| `prep.py` | Turns the GeoTIFF/GeoJSON results into dashboard files: PNG overlays, hotspot depth, animated flow lines |
| `validate.py` | Accuracy assessment against field observations (AUC, precision, recall, F1) |
| `Dockerfile`, `requirements-full.txt` | Environment for the whole pipeline (`requirements.txt` is the lean list for hosting the dashboard only) |
| `data/` | Derived layers used by the dashboard (see "Data") |

## Workflow (problem -> data -> method -> result -> validation)

**Data.** Point-cloud-derived DTM (IDW, `demground`, ground only), campus building footprints (shapefile, clipped to the DTM extent). All layers in EPSG:32643. Raw point cloud and DSM are not included.

**Method** (QGIS 3 with GRASS/GDAL providers; every step is also in QGIS *Processing > History*, exported to `qgis_processing_history.txt`):

1. Clip the footprints to the DTM extent (Extract layer extent, Clip).
2. Rasterise the footprints on the DTM grid (value 1, pre-initialised 0) -> `buildings_mask`.
3. Burn buildings into the terrain: `dtm_burned = dtm + 10 * buildings_mask`, so flow goes around buildings.
4. `r.fill.dir` on `dtm_burned` -> `filled_dem_bld`; depression depth = `filled_dem_bld - dtm_burned`.
5. `r.watershed` on `filled_dem_bld` (multiple flow direction, convergence factor 5, positive accumulation, region = DTM extent) -> flow accumulation and topographic index (TWI).
6. Baseline: the same `r.watershed` on the DTM without buildings -> `flowacc_base`.
7. Log scale `ln(acc + 1)` with cells below 0 set to no data; effect of buildings = log accumulation with buildings minus without.
8. Building cells set to no data. Depth cleaned: pits under 5 cm removed, values up to 1 m kept, 1-3 m set to 1 m, above 3 m set to 0 (courtyard artefacts caused by the burn-in).
9. TWI: GRASS wrote `nan` as no-data, so it was re-saved with no-data -9999 (GDAL Warp), then `twi_n3 = clip((TWI - 2) / 12, 0, 1)`. Flow accumulation and depth are scaled to 0-1 (`acc_n`, `depth_c`).
10. Risk score: `risk = 0.4 * acc_n + 0.3 * twi_n3 + 0.3 * depth_c` (weights are adjustable; no weight optimisation was done).
11. Hotspots: cells at or above the 95th percentile of `risk` (`r.quantile`) -> polygons, minimum area 20 m2, mean risk added as `score`, area as `area_m2`. Result: 351 polygons, 13,478 m2 in total.
12. `prep.py` adds the depth of every hotspot (`depth_max_m`, `depth_mean_m`) and builds flow-direction lines (D8 direction on the filled DEM, kept where accumulation is in the top 3 %). The dashboard draws them as moving dashes.

> TODO before submission: copy the exact normalisation bounds used for `acc_n` and the QGIS tool versions from *Processing > History* into this section.

**Validation.** Run `python validate.py` after adding `data/validation_points.csv` (see `validation_points_template.csv`). It reports AUC of the baseline layer (flow accumulation without buildings), the extension (building-aware accumulation), TWI, depth and the final risk score, plus precision, recall and F1 of the hotspot polygons.

> Results table: TO BE FILLED from `data/validation_results.csv`. Do not enter numbers that were not produced by the script.

## Run it

Local:
```
pip install -r requirements-full.txt
python prep.py
python -m streamlit run app.py
```
Docker (from this folder, with `data/` present):
```
docker build -t waterlogging-dashboard .
docker run -p 8501:8501 waterlogging-dashboard
```
Open http://localhost:8501. To rebuild the dashboard files inside the container: `docker run --rm -v "%cd%/data:/app/data" waterlogging-dashboard python prep.py` (Windows cmd; use `$(pwd)` on Linux/macOS).

Files expected in `data/`: `risk2.tif`, `flowacc_bld_log.tif`, `flowacc_base_log.tif`, `twi_n3.tif`, `depth_c.tif`, `buildings_effect.tif`, `filled_dem_bld.tif`, `hotspots.geojson`, `buildings.geojson`.

## What was adopted and what was developed

| Adopted (cited) | Developed by the team |
|---|---|
| GRASS GIS `r.fill.dir`, `r.watershed`, `r.topidx`, `r.quantile`; QGIS and GDAL; rasterio, GeoPandas, Shapely, Folium, Streamlit, streamlit-folium, Matplotlib | Building burn-in workflow on the campus DTM, depth cleaning rules, risk score and hotspot extraction, flow-line tracing (`prep.py`), dashboard (`app.py`), validation script (`validate.py`) |
| TWI (Beven & Kirkby, 1979), depression filling and flow direction (Jenson & Domingue, 1988), multiple flow direction (Holmgren, 1994) | Combination of these into a building-aware campus workflow and its evaluation against a terrain-only baseline |

## Limitations

Terrain-based indices only: no storm-drain network, infiltration, land cover or rainfall data. The study area is the LiDAR-covered part of the campus only. Cells near the raster edge are less reliable. The depth layer ignores pits under 5 cm and is capped at 1 m. Hotspot weights are fixed, not calibrated.

## Data protection

The data and layers describe the IIT Roorkee campus and were provided for the course. Do not publish them or the dashboard publicly.
