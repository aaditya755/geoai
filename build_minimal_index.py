#!/usr/bin/env python3
"""
Build a minimal FAISS index for testing - uses first 50 tiles only
"""

import json
import time
from pathlib import Path
import numpy as np

def build_minimal_index():
    """Build a minimal FAISS index with first 50 tiles for testing"""
    
    print("=== Building Minimal FAISS Index ===")
    
    tiles_dir = Path("data/processed/tiles_8bit")
    output_dir = Path("data/embeddings")
    
    if not tiles_dir.exists():
        print("❌ Processed tiles directory not found")
        return False
        
    tile_paths = sorted(tiles_dir.glob("*.tif"))[:50]  # First 50 tiles only
    
    if not tile_paths:
        print("❌ No processed tiles found")
        return False
        
    print(f"✅ Found {len(tile_paths)} tiles for indexing")
    
    try:
        import faiss
        from PIL import Image
        from skyclip_loader import embed_crops, get_device, load_skyclip, make_crops
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print("🔄 Loading SkyCLIP model...")
        model, preprocess, tokenizer = load_skyclip()
        device = get_device()
        print(f"✅ Model loaded on {device}")
        
        embeddings = []
        meta = []
        
        print("🔄 Processing tiles...")
        t0 = time.time()
        
        for i, tile_path in enumerate(tile_paths):
            try:
                tile_id = tile_path.stem
                img = Image.open(tile_path).convert("RGB")
                arr = np.array(img)
                
                # Use single crop for speed
                crops = make_crops(arr, crop_size=224, n_crops=1)
                crop_features = embed_crops(model, preprocess, crops, device=device)
                
                # Mean-pool (though only 1 crop)
                mean_feat = crop_features.mean(axis=0)
                mean_feat = mean_feat / (np.linalg.norm(mean_feat) + 1e-8)
                embeddings.append(mean_feat)
                
                meta.append({
                    "tile_id": tile_id,
                    "tile_path": str(tile_path),
                    "n_crops": len(crops),
                })
                
                if (i + 1) % 10 == 0:
                    elapsed = time.time() - t0
                    print(f"  Processed {i+1}/{len(tile_paths)} tiles ({elapsed:.1f}s)")
                    
            except Exception as e:
                print(f"⚠️  Failed to process {tile_path.name}: {e}")
                continue
        
        if not embeddings:
            print("❌ No embeddings generated")
            return False
            
        print("🔄 Building FAISS index...")
        embeddings_array = np.vstack(embeddings).astype("float32")
        embed_dim = embeddings_array.shape[1]
        
        print(f"  Embedding dimension: {embed_dim}")
        print(f"  Number of tiles: {len(embeddings_array)}")
        
        index = faiss.IndexFlatIP(embed_dim)
        index.add(embeddings_array)
        
        # Save index and metadata
        index_path = output_dir / "skyclip.index"
        meta_path = output_dir / "skyclip_meta.json"
        
        faiss.write_index(index, str(index_path))
        
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "embed_dim": embed_dim,
                "n_tiles": len(meta),
                "n_crops_per_tile": 1,
                "tiles": meta,
                "note": "Minimal index built for testing (50 tiles)"
            }, f, indent=2)
        
        elapsed_total = time.time() - t0
        print(f"✅ Index built successfully!")
        print(f"  Index file: {index_path}")
        print(f"  Metadata: {meta_path}")
        print(f"  Total time: {elapsed_total:.1f}s")
        print(f"  Average: {elapsed_total/len(embeddings):.2f}s/tile")
        
        return True
        
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("  Install with: pip install faiss-cpu")
        return False
    except Exception as e:
        print(f"❌ Index building failed: {e}")
        return False

if __name__ == "__main__":
    success = build_minimal_index()
    if success:
        print("\n🎉 Minimal FAISS index ready!")
        print("  You can now test vision-based queries")
    else:
        print("\n💡 Tips:")
        print("  - Ensure SkyCLIP model weights are available")
        print("  - Check that processed tiles exist") 
        print("  - Install faiss-cpu if missing")