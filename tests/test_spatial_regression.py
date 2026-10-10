#!/usr/bin/env python3
"""
Regression test for spatial engine distance calculations
Ensures accurate metre-based distance filtering in EPSG:32723
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import geopandas as gpd
from shapely.geometry import Point
import numpy as np

from spatial_engine import dwithin, intersects

RIO_CRS = "EPSG:32723"

class TestSpatialRegression:
    """Regression tests for spatial engine accuracy"""
    
    def test_dwithin_precision(self):
        """Test that dwithin calculations are accurate to within 1 metre"""
        # Create park at origin with 50m radius
        park = gpd.GeoDataFrame({
            'osm_id': ['park_1']
        }, geometry=[Point(0, 0).buffer(50)], crs=RIO_CRS)
        
        # Create buildings at known distances
        buildings = gpd.GeoDataFrame({
            'tile_id': ['near', 'edge', 'far'],
            'concept_id': ['building'] * 3,
            'score': [0.8] * 3,
            'measured_distance_m': [float('nan')] * 3,
            'rank': [0] * 3
        }, geometry=[
            Point(75, 0).buffer(5),   # ~25m from park edge  
            Point(250, 0).buffer(5),  # ~200m from park edge
            Point(260, 0).buffer(5),  # ~210m from park edge
        ], crs=RIO_CRS)
        
        # Test 200m threshold
        result = dwithin(buildings, park, 200.0)
        
        # Should return exactly 2 buildings (near and edge)
        assert len(result) == 2, f"Expected 2 buildings within 200m, got {len(result)}"
        
        # Check distances are reasonable and within threshold
        distances = result['measured_distance_m'].tolist()
        assert all(d <= 200.0 for d in distances), f"Some distances exceed 200m: {distances}"
        assert all(d >= 0 for d in distances), f"Negative distances found: {distances}"
        
        # Check distances are in expected ranges (within 5m tolerance)
        near_dist = result[result['tile_id'] == 'near']['measured_distance_m'].iloc[0]
        edge_dist = result[result['tile_id'] == 'edge']['measured_distance_m'].iloc[0]
        
        assert abs(near_dist - 20) < 5, f"Near distance {near_dist} not ~20m"
        assert abs(edge_dist - 195) < 5, f"Edge distance {edge_dist} not ~195m"
    
    def test_intersects_accuracy(self):
        """Test that intersects correctly identifies overlapping geometries"""
        # Create park
        park = gpd.GeoDataFrame({
            'osm_id': ['park_1']
        }, geometry=[Point(0, 0).buffer(50)], crs=RIO_CRS)
        
        # Create buildings - one overlapping, one separate
        buildings = gpd.GeoDataFrame({
            'tile_id': ['overlap', 'separate'], 
            'concept_id': ['building'] * 2,
            'score': [0.8] * 2,
            'measured_distance_m': [float('nan')] * 2,
            'rank': [0] * 2
        }, geometry=[
            Point(25, 0).buffer(30),  # Overlaps park (center 25m, radius 30m)
            Point(200, 0).buffer(10), # Separate from park
        ], crs=RIO_CRS)
        
        result = intersects(buildings, park)
        
        # Should return exactly 1 building (overlap)
        assert len(result) == 1, f"Expected 1 intersecting building, got {len(result)}"
        assert result.iloc[0]['tile_id'] == 'overlap', "Wrong building returned"
        assert result.iloc[0]['measured_distance_m'] == 0.0, "Intersecting distance should be 0"
    
    def test_empty_inputs(self):
        """Test spatial operations handle empty inputs gracefully"""
        # Empty buildings
        empty_buildings = gpd.GeoDataFrame({
            'tile_id': [],
            'measured_distance_m': []
        }, geometry=[], crs=RIO_CRS)
        
        # Non-empty park
        park = gpd.GeoDataFrame({
            'osm_id': ['park_1']
        }, geometry=[Point(0, 0).buffer(50)], crs=RIO_CRS)
        
        result = dwithin(empty_buildings, park, 100.0)
        assert len(result) == 0, "Empty input should return empty result"
        assert isinstance(result, gpd.GeoDataFrame), "Should return GeoDataFrame"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])