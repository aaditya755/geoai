#!/usr/bin/env python3
"""
Fix georeferencing for SpaceNet tiles that have degenerate transforms.

The tiles have correct bounds but invalid affine transforms with zero scaling.
This script recomputes proper transforms from bounds and image dimensions.
"""

import rasterio
from rasterio.transform import from_bounds
from pathlib import Path
import numpy as np
import shutil

def fix_tile_georeferencing(input_path: Path, output_path: Path) -> bool:
    """
    Fix a tile's georeferencing by computing proper transform from bounds.
    
    Returns True if the tile was fixed, False if it was already correct.
    """
    
    with rasterio.open(input_path) as src:
        # Check if transform is degenerate (has near-zero scaling)
        transform = src.transform
        if abs(transform.a) < 1e-5 or abs(transform.e) < 1e-5:
            print(f"Fixing degenerate transform in {input_path.name}")
            
            # Get current metadata
            bounds = src.bounds
            width = src.width  
            height = src.height
            crs = src.crs
            
            # Compute proper affine transform from bounds
            proper_transform = from_bounds(
                bounds.left, bounds.bottom, bounds.right, bounds.top,
                width, height
            )
            
            print(f"  Original transform: {transform}")
            print(f"  New transform: {proper_transform}")
            print(f"  Bounds: {bounds}")
            
            # Copy metadata and update transform
            meta = src.meta.copy()
            meta.update(transform=proper_transform)
            
            # Read image data
            data = src.read()
            
            # Write with corrected georeferencing
            with rasterio.open(output_path, "w", **meta) as dst:
                dst.write(data)
                
            return True
        else:
            print(f"Transform already correct in {input_path.name}")
            # Just copy the file
            shutil.copy2(input_path, output_path)
            return False

def fix_tiles_in_directory(input_dir: Path, output_dir: Path):
    """Fix all tiles in a directory."""
    
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    
    if not input_dir.exists():
        print(f"Input directory {input_dir} does not exist")
        return
        
    output_dir.mkdir(parents=True, exist_ok=True)
    
    tile_paths = list(input_dir.glob("*.tif"))
    print(f"Found {len(tile_paths)} tiles in {input_dir}")
    
    fixed_count = 0
    for tile_path in tile_paths:
        output_path = output_dir / tile_path.name
        if fix_tile_georeferencing(tile_path, output_path):
            fixed_count += 1
            
    print(f"Fixed {fixed_count} tiles out of {len(tile_paths)} total")

if __name__ == "__main__":
    # Fix processed tiles
    fix_tiles_in_directory(
        "data/processed/tiles_8bit",
        "data/processed/tiles_8bit_fixed" 
    )
    
    print()
    print("Tile georeferencing fix complete!")
    print("To use the fixed tiles, update the tiles_dir path in object_detector.py")