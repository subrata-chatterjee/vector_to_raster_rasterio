#import geotable
import array
import math
import geopandas as gpd
import numpy as np
import rasterio as rio
from rasterio.features import rasterize, MergeAlg
import pandas as pd

from rasterio.io import MemoryFile
from rasterio.enums import Resampling


def convert_wgs_to_utm(lon: float, lat: float):
    """Based on lat and lng, return best utm epsg-code"""
    utm_band = str((math.floor((lon + 180) / 6 ) % 60) + 1)
    if len(utm_band) == 1:
        utm_band = '0'+utm_band
    if lat >= 0:
        epsg_code = '326' + utm_band
        return epsg_code
    epsg_code = '327' + utm_band
    return epsg_code

   ## read unzipped file with geopandas
gdf = gpd.read_file('US_Tornado_2022-11-29_griddata_1669972503.GEOJSON',driver='GeoJSON')

gdf_bound = gdf.to_crs('epsg:3857').total_bounds

total_xmin = (np.floor(gdf_bound[0]/20) * 20) - 100 - 20
total_ymin = (np.floor(gdf_bound[1]/20) * 20) - 100 - 20
total_xmax = (np.ceil(gdf_bound[2]/20) * 20) + 100 + 20
total_ymax = (np.ceil(gdf_bound[3]/20) * 20) + 100 + 20

geom_lst = [] 
buffersize_lst = []

gdf['utm_epsg'] = gdf.geometry.apply(lambda x: convert_wgs_to_utm(x.centroid.x,x.centroid.y) )
gdf_lst = [] 
for utm, df in gdf.groupby('utm_epsg', as_index=False):
    df = df.to_crs(utm)
    df['buffer'] = df.geometry.buffer(100)
    df.geometry.crs=utm
    df['buffer'].crs = utm
    df.geometry = df.geometry.to_crs(3857)
    #df = df.set_geometry('buffer')
    df['buffer'] = df['buffer'].to_crs(3857)        
    gdf_lst.append(df)

gdf = pd.concat(gdf_lst)

geom_lst = gdf.geometry.to_list()+gdf['buffer'].to_list()


buffersize_lst = gdf['predicted_ef_rank'].to_list()+ [100 for i in range(len(gdf))]


profile = rio.profiles.DefaultGTiffProfile()
profile.update(
        dtype=rio.uint8,
        count=1,
        compress='deflate',
        height=int((total_ymax-total_ymin) / 20),
        width=int((total_xmax-total_xmin) / 20),
        transform=rio.transform.Affine(20, 0, total_xmin, 0, -20, total_ymax),
        crs=rio.crs.CRS.from_epsg(3857),
        nodata = 255
    
)
print(profile)
tiff_file = MemoryFile()
reprojected_file = MemoryFile()


## rasterize the polygons
rast = rasterize(
    shapes=zip(reversed(geom_lst), reversed(buffersize_lst)),
    out_shape=(profile['height'], profile['width']),
    transform=profile['transform'],
    fill=profile['nodata'],
    all_touched=False,
    merge_alg=MergeAlg.replace,
    dtype=np.uint8
)

tiff_file = MemoryFile()
reprojected_file = MemoryFile()
with tiff_file.open(**profile) as src:
    src.write(rast.astype(rio.uint8), 1)
    src.build_overviews([2, 4, 8], Resampling.nearest)

print(tiff_file) 

## write rasterized image to file (optional)
with rio.open('rast3.tif', 'w',**profile) as dst:
    #dst.write(rast, 1)
    dst.write(rast.astype(rio.uint8), 1)
    dst.build_overviews([2, 4, 8], Resampling.nearest)
    




