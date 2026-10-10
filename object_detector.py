"""
object_detector.py — Object detection for GeoLens AI.

Implements genuine object detection on retrieved tiles using available models.
Converts detection results to georeferenced geometries for spatial verification.

Currently implements a lightweight detection approach using image analysis
to bridge the gap until OWLv2/Grounding DINO integration is completed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

import numpy as np
import geopandas as gpd
from shapely.geometry import box, Point
import rasterio
from rasterio.warp import transform_bounds
from rasterio.crs import CRS
import cv2
from PIL import Image

RIO_CRS = "EPSG:32723"
WGS84 = "EPSG:4326"

# Detection confidence threshold
MIN_DETECTION_CONFIDENCE = 0.3

def detect_buildings_in_tile(tile_path: Path, concept: str = "building") -> List[Dict[str, Any]]:
    """
    Detect buildings in a single tile using image analysis.
    
    This is a practical implementation that uses edge detection and contour analysis
    to find building-like rectangular structures. While not as sophisticated as 
    OWLv2/Grounding DINO, it provides genuine object-level detections rather than
    tile footprints.
    
    Parameters
    ----------
    tile_path : Path to the SpaceNet tile (.tif file)
    concept : Target concept ("building", "road", etc.)
    
    Returns
    -------
    List of detection dictionaries with pixel coordinates and confidence scores
    """
    detections = []
    
    if not tile_path.exists():
        return detections
    
    try:
        # Read the tile
        with rasterio.open(tile_path) as src:
            # Read RGB bands
            image_data = src.read([1, 2, 3])  # RGB
            image_data = np.transpose(image_data, (1, 2, 0))  # HWC format
            
            # Convert to uint8 if needed
            if image_data.dtype != np.uint8:
                image_data = (image_data * 255).astype(np.uint8)
            
        # Apply building detection based on concept
        if concept == "building":
            detections = _detect_buildings_cv2(image_data)
        elif concept == "road":
            detections = _detect_roads_cv2(image_data)
        elif concept == "park":
            detections = _detect_green_areas_cv2(image_data)
        else:
            # Generic rectangular structure detection
            detections = _detect_rectangular_structures(image_data)
            
    except Exception as e:
        print(f"[detector] Error processing {tile_path}: {e}")
        
    return detections

def _detect_buildings_cv2(image: np.ndarray) -> List[Dict[str, Any]]:
    """Detect building-like structures using OpenCV edge detection"""
    
    detections = []
    
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Edge detection
    edges = cv2.Canny(blurred, 50, 150)
    
    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for contour in contours:
        # Filter by area (buildings should be reasonably sized)
        area = cv2.contourArea(contour)
        if area < 100 or area > 50000:  # Filter very small/large areas
            continue
            
        # Approximate contour to polygon
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        
        # Buildings tend to be rectangular (4-sided)
        if len(approx) >= 4:
            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by aspect ratio (buildings are usually not extremely elongated)
            aspect_ratio = max(w, h) / min(w, h)
            if aspect_ratio > 5:  # Too elongated, probably not a building
                continue
                
            # Calculate confidence based on rectangularity and size
            rect_area = w * h
            contour_area = cv2.contourArea(contour)
            rectangularity = contour_area / rect_area if rect_area > 0 else 0
            
            confidence = min(0.9, 0.3 + rectangularity * 0.6)  # Base confidence + rectangularity bonus
            
            if confidence >= MIN_DETECTION_CONFIDENCE:
                detections.append({
                    'bbox': [x, y, x + w, y + h],  # [x1, y1, x2, y2]
                    'confidence': confidence,
                    'area': contour_area,
                    'concept': 'building'
                })
    
    return detections

def _detect_roads_cv2(image: np.ndarray) -> List[Dict[str, Any]]:
    """Detect road-like linear structures"""
    
    detections = []
    
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    
    # Apply morphological operations to enhance linear structures
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    processed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    
    # Edge detection optimized for linear features
    edges = cv2.Canny(processed, 30, 100)
    
    # Hough line detection for road-like features
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50, minLineLength=30, maxLineGap=10)
    
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            
            # Calculate line properties
            length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            
            if length > 20:  # Minimum road segment length
                # Create bounding box around line with some width
                width = 10  # Road width in pixels
                
                # Calculate perpendicular offset
                dx = x2 - x1
                dy = y2 - y1
                norm = np.sqrt(dx*dx + dy*dy)
                if norm > 0:
                    offset_x = -dy * width / (2 * norm)
                    offset_y = dx * width / (2 * norm)
                    
                    bbox_x1 = min(x1 + offset_x, x1 - offset_x, x2 + offset_x, x2 - offset_x)
                    bbox_y1 = min(y1 + offset_y, y1 - offset_y, y2 + offset_y, y2 - offset_y)
                    bbox_x2 = max(x1 + offset_x, x1 - offset_x, x2 + offset_x, x2 - offset_x)
                    bbox_y2 = max(y1 + offset_y, y1 - offset_y, y2 + offset_y, y2 - offset_y)
                    
                    confidence = min(0.8, 0.4 + min(1.0, length / 100) * 0.4)
                    
                    detections.append({
                        'bbox': [int(bbox_x1), int(bbox_y1), int(bbox_x2), int(bbox_y2)],
                        'confidence': confidence,
                        'area': length * width,
                        'concept': 'road'
                    })
    
    return detections

def _detect_green_areas_cv2(image: np.ndarray) -> List[Dict[str, Any]]:
    """Detect green areas (parks) using color-based segmentation"""
    
    detections = []
    
    # Convert to HSV for better color segmentation
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    
    # Define range for green colors (vegetation)
    lower_green = np.array([35, 25, 25])
    upper_green = np.array([85, 255, 255])
    
    # Create mask for green areas
    green_mask = cv2.inRange(hsv, lower_green, upper_green)
    
    # Apply morphological operations to clean up the mask
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
    green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, kernel)
    
    # Find contours
    contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 500:  # Minimum park area
            x, y, w, h = cv2.boundingRect(contour)
            
            # Calculate confidence based on green coverage
            roi_mask = green_mask[y:y+h, x:x+w]
            green_ratio = np.sum(roi_mask > 0) / (w * h) if w * h > 0 else 0
            
            confidence = min(0.8, 0.2 + green_ratio * 0.6)
            
            if confidence >= MIN_DETECTION_CONFIDENCE:
                detections.append({
                    'bbox': [x, y, x + w, y + h],
                    'confidence': confidence,
                    'area': area,
                    'concept': 'park'
                })
    
    return detections

def _detect_rectangular_structures(image: np.ndarray) -> List[Dict[str, Any]]:
    """Generic rectangular structure detection"""
    # Use building detection as fallback for unknown concepts
    return _detect_buildings_cv2(image)

def georeference_detections(
    detections: List[Dict[str, Any]], 
    tile_path: Path,
    target_crs: str = RIO_CRS
) -> gpd.GeoDataFrame:
    """
    Convert pixel-coordinate detections to georeferenced geometries.
    
    Parameters
    ----------
    detections : List of detection dictionaries with pixel bboxes
    tile_path : Path to the source tile for coordinate transformation
    target_crs : Target coordinate reference system
    
    Returns
    -------
    GeoDataFrame with georeferenced detection geometries
    """
    
    if not detections or not tile_path.exists():
        return gpd.GeoDataFrame(columns=[
            'tile_id', 'bbox', 'score', 'concept_id', 
            'geometry', 'measured_distance_m', 'rank'
        ], crs=target_crs)
    
    georef_results = []
    
    try:
        with rasterio.open(tile_path) as src:
            # Get the tile's geospatial transform
            transform = src.transform
            crs = src.crs
            
            for detection in detections:
                # Extract pixel coordinates
                x1, y1, x2, y2 = detection['bbox']
                
                # Transform pixel coordinates to geographic coordinates
                # Top-left corner
                lon1, lat1 = rasterio.transform.xy(transform, y1, x1)
                # Bottom-right corner  
                lon2, lat2 = rasterio.transform.xy(transform, y2, x2)
                
                # Create geometry (bounding box in source CRS)
                if crs:
                    # Create box in source CRS
                    geom = box(min(lon1, lon2), min(lat1, lat2), max(lon1, lon2), max(lat1, lat2))
                    
                    # Create GeoDataFrame with source CRS
                    temp_gdf = gpd.GeoDataFrame([1], geometry=[geom], crs=crs)
                    
                    # Transform to target CRS
                    temp_gdf = temp_gdf.to_crs(target_crs)
                    transformed_geom = temp_gdf.geometry.iloc[0]
                else:
                    # Fallback: assume coordinates are already in target CRS
                    transformed_geom = box(min(lon1, lon2), min(lat1, lat2), max(lon1, lon2), max(lat1, lat2))
                
                # Create result record
                georef_results.append({
                    'tile_id': tile_path.stem,
                    'bbox': detection['bbox'],
                    'score': detection['confidence'],
                    'concept_id': detection['concept'],
                    'geometry': transformed_geom,
                    'measured_distance_m': float('nan'),
                    'rank': 0,
                    'detection_area': detection['area']
                })
                
    except Exception as e:
        print(f"[georeferencing] Error processing {tile_path}: {e}")
        
    if not georef_results:
        return gpd.GeoDataFrame(columns=[
            'tile_id', 'bbox', 'score', 'concept_id', 
            'geometry', 'measured_distance_m', 'rank'
        ], crs=target_crs)
    
    return gpd.GeoDataFrame(georef_results, crs=target_crs)

def detect_objects_in_tiles(
    tile_ids: List[str],
    concept: str,
    tiles_dir: Path = Path("data/processed/tiles_8bit")
) -> gpd.GeoDataFrame:
    """
    Detect objects in a list of tiles and return georeferenced results.
    
    This is the main interface used by vision.py for object detection.
    
    Parameters
    ----------
    tile_ids : List of tile identifiers from SkyCLIP retrieval
    concept : Target concept (building, road, park, etc.)
    tiles_dir : Directory containing processed tiles
    
    Returns
    -------
    GeoDataFrame with detected objects in target CRS
    """
    
    all_detections = []
    
    for tile_id in tile_ids:
        # Find the tile file
        tile_path = tiles_dir / f"{tile_id}.tif"
        
        if not tile_path.exists():
            print(f"[detector] Tile not found: {tile_path}")
            continue
            
        # Detect objects in this tile
        pixel_detections = detect_buildings_in_tile(tile_path, concept)
        
        if pixel_detections:
            # Georeference the detections
            georef_gdf = georeference_detections(pixel_detections, tile_path)
            
            if not georef_gdf.empty:
                all_detections.append(georef_gdf)
                print(f"[detector] Found {len(georef_gdf)} {concept}(s) in {tile_id}")
    
    if all_detections:
        # Combine all detections
        combined_gdf = gpd.pd.concat(all_detections, ignore_index=True)
        return combined_gdf
    else:
        # Return empty GeoDataFrame with correct schema
        return gpd.GeoDataFrame(columns=[
            'tile_id', 'bbox', 'score', 'concept_id', 
            'geometry', 'measured_distance_m', 'rank'
        ], crs=RIO_CRS)