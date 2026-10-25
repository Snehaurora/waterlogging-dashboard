import numpy as np
import geopandas as gpd
import rasterio
from rasterio.enums import Resampling
from rasterio.features import shapes
from scipy import ndimage as ndi
from shapely.geometry import shape
from skimage.morphology import reconstruction

# ---------- settings you can change ----------
DTM_PATH = "raw_data/iitr_dtm.tif"
TARGET_RES = 1.0      # work at 1 m pixels (keeps it fast)
MIN_DEPTH = 0.10      # ignore depressions shallower than 10 cm (DTM noise)
MIN_AREA = 10.0       # ignore depressions smaller than 10 m2
MAX_HOTSPOTS = 300    # keep the largest 300 by volume
# ---------------------------------------------

with rasterio.open(DTM_PATH) as src:
    print("CRS:", src.crs, "| pixel size:", src.res, "| size:", src.width, "x", src.height)
    if src.crs is None or src.crs.is_geographic:
        raise SystemExit("The DTM is not in a metric (projected) CRS. Send me the CRS printed above.")
    f = max(1.0, TARGET_RES / abs(src.res[0]))
    out_h, out_w = int(src.height / f), int(src.width / f)
    dem = src.read(1, out_shape=(out_h, out_w), resampling=Resampling.average, masked=True)
    transform = src.transform * src.transform.scale(src.width / out_w, src.height / out_h)
    crs = src.crs

nodata = np.ma.getmaskarray(dem)
data = dem.filled(np.nan).astype(np.float32)
nodata |= np.isnan(data)
data[nodata] = np.nanmin(data) - 1.0          # no-data acts as a drain
print("Working grid:", data.shape, "| pixel:", abs(transform.a), "m")

# ---- fill depressions (priority-flood style, via morphological reconstruction) ----
seed = np.full(data.shape, data.max(), dtype=np.float32)
seed[0, :], seed[-1, :], seed[:, 0], seed[:, -1] = data[0, :], data[-1, :], data[:, 0], data[:, -1]
seed[nodata] = data[nodata]
print("Filling depressions (can take a few minutes)...")
filled = reconstruction(seed, data, method="erosion")

depth = (filled - data).astype(np.float32)
depth[nodata] = 0
depth[depth < MIN_DEPTH] = 0

# ---- measure each depression ----
labels, n = ndi.label(depth > 0)
ids = np.arange(1, n + 1)
cell = abs(transform.a * transform.e)
area = ndi.sum(np.ones_like(depth), labels, ids) * cell
vol = ndi.sum(depth, labels, ids) * cell
dmax = ndi.maximum(depth, labels, ids)

keep = np.zeros(n + 1, bool)
keep[ids[area >= MIN_AREA]] = True
labels = np.where(keep[labels], labels, 0).astype(np.int32)
print("Depressions found:", int(keep.sum()))

rows = []
for geom, val in shapes(labels, mask=labels > 0, transform=transform):
    i = int(val) - 1
    rows.append({"depth_m": round(float(dmax[i]), 2), "area_m2": round(float(area[i]), 1),
                 "volume_m3": round(float(vol[i]), 1), "geometry": shape(geom)})

gdf = gpd.GeoDataFrame(rows, crs=crs)
gdf = gdf.sort_values("volume_m3", ascending=False).head(MAX_HOTSPOTS).reset_index(drop=True)
gdf["rank"] = gdf.index + 1
gdf["id"] = ["H%03d" % r for r in gdf["rank"]]
gdf["is_sample"] = False
gdf["geometry"] = gdf.geometry.simplify(abs(transform.a))
gdf = gdf.to_crs(4326)
gdf[["id", "rank", "depth_m", "area_m2", "volume_m3", "is_sample", "geometry"]].to_file(
    "data/hotspots.geojson", driver="GeoJSON")
print("Saved data/hotspots.geojson with", len(gdf), "hotspots")