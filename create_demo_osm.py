#!/usr/bin/env python3
"""
Create minimal OSM data for demo purposes
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
from pathlib import Path

def create_demo_osm():
    """Create minimal OSM road and building data for Rio de Janeiro"""
    
    print("=== Creating Demo OSM Data ===")
    
    # Rio de Janeiro bounds (approximate)
    RIO_BOUNDS = {
        'west': -43.7963,
        'south': -23.1821, 
        'east': -43.0926,
        'north': -22.7461
    }
    
    osm_dir = Path("data/raw/osm")
    osm_dir.mkdir(parents=True, exist_ok=True)
    
    # Create sample roads
    print("🔄 Creating sample roads...")
    
    roads_data = []
    # Create a few main roads across Rio
    road_coords = [
        [(-43.2, -22.9), (-43.1, -22.9)],  # East-west road
        [(-43.15, -22.95), (-43.15, -22.85)],  # North-south road 
        [(-43.25, -22.88), (-43.12, -22.92)],  # Diagonal road
        [(-43.18, -22.87), (-43.13, -22.89)],  # Another road
        [(-43.22, -22.91), (-43.16, -22.94)],  # Cross road
    ]
    
    for i, coords in enumerate(road_coords):
        road_geom = Point(coords[0]).buffer(0.001).exterior  # Simple line buffer
        roads_data.append({
            'osm_id': f'road_{i+1}',
            'highway': 'primary' if i < 2 else 'secondary',
            'name': f'Demo Road {i+1}',
            'geometry': Polygon(road_geom.coords)
        })
    
    roads_gdf = gpd.GeoDataFrame(roads_data, crs='EPSG:4326')
    
    # Convert to projected CRS for proper distance calculations
    roads_gdf = roads_gdf.to_crs('EPSG:32723')  # UTM Zone 23S for Rio
    
    roads_path = osm_dir / "roads.parquet"
    roads_gdf.to_parquet(roads_path)
    print(f"✅ Created {len(roads_gdf)} roads -> {roads_path}")
    
    # Create sample buildings/parks
    print("🔄 Creating sample buildings and parks...")
    
    buildings_data = []
    
    # Create some buildings
    building_centers = [
        (-43.18, -22.90, 'residential'),
        (-43.16, -22.91, 'commercial'), 
        (-43.14, -22.89, 'residential'),
        (-43.20, -22.88, 'office'),
        (-43.17, -22.92, 'residential'),
    ]
    
    for i, (lon, lat, building_type) in enumerate(building_centers):
        # Create rectangular building
        size = 0.0005  # ~50m
        building_geom = Polygon([
            (lon - size, lat - size),
            (lon + size, lat - size), 
            (lon + size, lat + size),
            (lon - size, lat + size)
        ])
        
        buildings_data.append({
            'osm_id': f'building_{i+1}',
            'building': building_type,
            'name': f'Demo Building {i+1}',
            'geometry': building_geom
        })
    
    # Create some parks
    park_centers = [
        (-43.175, -22.895, 'Copacabana Park'),
        (-43.155, -22.905, 'Ipanema Green'),
        (-43.195, -22.885, 'Central Park'),
    ]
    
    for i, (lon, lat, name) in enumerate(park_centers):
        # Create park area
        size = 0.002  # ~200m 
        park_geom = Polygon([
            (lon - size, lat - size),
            (lon + size, lat - size),
            (lon + size, lat + size), 
            (lon - size, lat + size)
        ])
        
        buildings_data.append({
            'osm_id': f'park_{i+1}',
            'leisure': 'park',
            'name': name,
            'geometry': park_geom
        })
    
    buildings_gdf = gpd.GeoDataFrame(buildings_data, crs='EPSG:4326')
    buildings_gdf = buildings_gdf.to_crs('EPSG:32723')  # UTM Zone 23S
    
    buildings_path = osm_dir / "buildings.parquet"
    buildings_gdf.to_parquet(buildings_path)
    print(f"✅ Created {len(buildings_gdf)} buildings/parks -> {buildings_path}")
    
    print(f"\n✅ Demo OSM data created!")
    print(f"  Roads: {len(roads_gdf)} features")
    print(f"  Buildings/Parks: {len(buildings_gdf)} features")
    print(f"  Location: Rio de Janeiro, Brazil")
    
    return True

if __name__ == "__main__":
    create_demo_osm()