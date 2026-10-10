from dotenv import load_dotenv; load_dotenv()
import geopandas as gpd

gdf = gpd.read_parquet("data/raw/osm/buildings.parquet")
print("All 8 rows in buildings.parquet:")
for _, row in gdf.iterrows():
    print(f"  osm_id={row['osm_id']}  building={row['building']}  leisure={row['leisure']}  name={row.get('name')}")
