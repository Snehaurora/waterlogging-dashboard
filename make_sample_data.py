import json
import random
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

random.seed(42)
Path("data").mkdir(exist_ok=True)

CENTER_LAT, CENTER_LON = 29.8649, 77.8966  # approx IITR campus

rows = []
for i in range(1, 11):
    lat = CENTER_LAT + random.uniform(-0.004, 0.004)
    lon = CENTER_LON + random.uniform(-0.005, 0.005)
    # build a circle of random radius, in metres (UTM zone 43N = EPSG:32643)
    pt = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(32643).iloc[0]
    radius = random.uniform(6, 25)
    geom = pt.buffer(radius)
    depth = round(random.uniform(0.1, 0.8), 2)
    area = round(geom.area, 1)
    rows.append({
        "id": f"H{i:02d}",
        "depth_m": depth,
        "area_m2": area,
        "volume_m3": round(area * depth * 0.4, 1),
        "twi_mean": round(random.uniform(8, 16), 1),
        "is_sample": True,
        "geometry": geom,
    })

gdf = gpd.GeoDataFrame(rows, crs=32643).to_crs(4326)
gdf = gdf.sort_values("volume_m3", ascending=False).reset_index(drop=True)
gdf["rank"] = gdf.index + 1
gdf.to_file("data/hotspots.geojson", driver="GeoJSON")

metrics = {
    "is_sample": True,
    "precision": 0.80,
    "recall": 0.72,
    "f1": 0.76,
    "iou": 0.61,
    "dtm_rmse_m": 0.08,
}
with open("data/metrics.json", "w") as f:
    json.dump(metrics, f, indent=2)

print("Done: data/hotspots.geojson and data/metrics.json created")
