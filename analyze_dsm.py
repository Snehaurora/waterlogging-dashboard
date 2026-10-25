import numpy as np
import geopandas as gpd
import rasterio
from rasterio.enums import Resampling
from rasterio.features import shapes
from scipy import ndimage as ndi
from shapely.geometry import shape
from skimage.morphology import reconstruction

# ---------- settings you can change ----------
DSM_PATH = "raw_data/iitr_dsm.tif"
TARGET_RES = 1.0       # work at 1 m pixels (use 2.0 if the laptop struggles)
OBJECT_HEIGHT = 2.0    # anything >2 m above estimated ground = building/tree
OPEN_WINDOW_M = 51     # should be wider than the biggest building
GROW_M = 2             # widen the building/tree mask by 2 m
MIN_DEPTH = 0.10       # ignore depressions shallower than 10 cm
MIN_AREA = 10.0        # ignore depressions smaller than 10 m2
MAX_HOTSPOTS = 300     # keep the largest 300 by volume
# ---------------------------------------------

with rasterio.open(DSM_PATH) as src:
    print("CRS:", src.crs, "| pixel size:", src.res, "| size:", src.width, "x", src.height)
    if src.crs is None or src.crs.is_geographic:
        raise SystemExit("The DSM is not in a metric (projected) CRS. Send me the CRS printed above.")
    f = max(1.0, TARGET_RES / abs(src.res[0]))
    out_h, out_w = int(src.height / f), int(src.width / f)
    print("Reading and shrinking the DSM (a few minutes)...")
    dsm = src.read(1, out_shape=(out_h, out_w), resampling=Resampling.average, masked=True)
    transform = src.transform * src.transform.scale(src.width / out_w, src.height / out_h)
    crs = src.crs

px = abs(transform.a)
nodata = np.ma.getmaskarray(dsm)
data = dsm.filled(np.nan).astype(np.float32)
nodata |= np.isnan(data)
data[nodata] = np.nanmedian(data)
print("Working grid:", data.shape, "| pixel:", round(px, 2), "m")

# ---- 1) estimate bare ground and mask buildings/trees ----
win = int(OPEN_WINDOW_M / px) | 1
print("Estimating ground surface...")
ground = ndi.grey_opening(data, size=(win, win))
objects = (data - ground) > OBJECT_HEIGHT
objects = ndi.binary_dilation(objects, iterations=max(1, int(GROW_M / px)))
surface = np.where(objects, ground, data).astype(np.float32)
print("Masked as buildings/trees: %.1f %% of the area" % (100 * objects.mean()))

# ---- 2) fill depressions (priority-flood style) ----
surface[nodata] = surface.min() - 1.0          # no-data acts as a drain
seed = np.full(surface.shape, surface.max(), dtype=np.float32)
seed[0, :], seed[-1, :], seed[:, 0], seed[:, -1] = surface[0, :], surface[-1, :], surface[:, 0], surface[:, -1]
seed[nodata] = surface[nodata]
print("Filling depressions (can take a few minutes)...")
filled = reconstruction(seed, surface, method="erosion")

depth = (filled - surface).astype(np.float32)
depth[nodata | objects] = 0
depth[depth < MIN_DEPTH] = 0

# ---- 3) measure each depression ----
labels, n = ndi.label(depth > 0)
ids = np.arange(1, n + 1)
cell = px * px
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
gdf["geometry"] = gdf.geometry.simplify(px)
gdf = gdf.to_crs(4326)
gdf[["id", "rank", "depth_m", "area_m2", "volume_m3", "is_sample", "geometry"]].to_file(
    "data/hotspots.geojson", driver="GeoJSON")
print("Saved data/hotspots.geojson with", len(gdf), "hotspots")