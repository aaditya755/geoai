"""Verify building-to-park distances match what the API returns."""
from dotenv import load_dotenv; load_dotenv()
import geopandas as gpd
from shapely.ops import unary_union

gdf       = gpd.read_parquet("data/raw/osm/buildings.parquet")
buildings = gdf[gdf["building"].notna() & gdf["leisure"].isna()].copy()
parks     = gdf[gdf["leisure"] == "park"].copy()
park_u    = unary_union(parks.geometry)

print("Building-to-park distances:")
for _, row in buildings.iterrows():
    d     = row.geometry.distance(park_u)
    label = row.get("name", row["osm_id"])
    keep  = d <= 200
    print(f"  {str(label):30s}  dist={d:.0f} m   qualifies_200m={keep}")

qualifying = [row for _, row in buildings.iterrows() if row.geometry.distance(park_u) <= 200]
print(f"\n{len(qualifying)} / {len(buildings)} buildings qualify at 200 m")
