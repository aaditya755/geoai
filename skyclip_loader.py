"""
skyclip_loader.py — SkyCLIP model loader for GeoLens AI.

Loads the SkyCLIP CLIP-based model pretrained on SkyScript (arXiv:2312.12856).
Returns image and text encoders ready for embedding.

Architecture:
- SkyCLIP is released in two sizes:
    ViT-B/32  (embed_dim=512)  — CPU-feasible for dev; checkpoint ~1.5 GB
    ViT-L/14  (embed_dim=768)  — requires GPU for indexing at scale; checkpoint ~4.4 GB
- The architecture is standard OpenAI CLIP, continually pretrained on SkyScript.
- Weights are loaded by: clip.load(arch) → patch with SkyCLIP state_dict.
- SKYCLIP_ARCH env var controls which architecture is used (default: ViT-B/32).

Loading:
- Reads weights from SKYCLIP_WEIGHTS env var path if set.
- Default path: data/embeddings/SkyCLIP_ViT_B32_top50pct/<weights_file>.pt
- Falls back to HuggingFace (wangzhecheng/SkyCLIP) if no local file found.
- GPU used if available; CPU fallback for CPU-only environments.

Domain note:
- SkyCLIP was trained on SkyScript — a globally diverse aerial imagery dataset.
- SpaceNet Rio uses WorldView-3 imagery at ~0.3–0.5 m/px.
- Cross-dataset domain gap is unknown until check1_skyclip.py is run.
- Do not assume good similarity scores on SpaceNet imagery without measuring.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

import torch
import numpy as np

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SKYCLIP_WEIGHTS_ENV = "SKYCLIP_WEIGHTS"
SKYCLIP_ARCH_ENV = "SKYCLIP_ARCH"  # "ViT-B/32" or "ViT-L/14"

# Default paths where the download script places extracted weights
_DEFAULT_WEIGHT_GLOBS = [
    "data/embeddings/**/*.pt",
    "data/embeddings/**/*.bin",
    "data/embeddings/*.pt",
]

# Architecture → embed dimension mapping (verified from OpenAI CLIP)
ARCH_EMBED_DIM = {
    "ViT-B/32": 512,
    "ViT-B/16": 512,
    "ViT-L/14": 768,
    "ViT-L/14@336px": 768,
}

SKYCLIP_HF_REPO = "wangzhecheng/SkyCLIP"


def get_device() -> torch.device:
    """Return CUDA if available, else CPU."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _find_default_weights(root: Path) -> Optional[Path]:
    """Scan default locations for a .pt weights file."""
    import glob
    for pattern in _DEFAULT_WEIGHT_GLOBS:
        matches = sorted(root.glob(pattern))
        if matches:
            return matches[0]
    return None


def _infer_arch_from_path(weights_path: str) -> str:
    """
    Infer CLIP architecture from the checkpoint filename.
    Returns "ViT-B/32" or "ViT-L/14" based on the filename.
    Defaults to "ViT-B/32" when ambiguous.
    """
    name = Path(weights_path).name.lower()
    if "l14" in name or "vit_l" in name or "vit-l" in name:
        return "ViT-L/14"
    if "b32" in name or "vit_b32" in name or "vit-b32" in name:
        return "ViT-B/32"
    if "b16" in name or "vit_b16" in name or "vit-b16" in name:
        return "ViT-B/16"
    # Default
    return "ViT-B/32"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_skyclip(weights_path: Optional[str] = None) -> Tuple[object, object, object]:
    """
    Load the SkyCLIP model.

    Parameters
    ----------
    weights_path : path to local .pt weights file, or None to use
                   SKYCLIP_WEIGHTS env var, or None to scan default locations.

    Returns
    -------
    (model, preprocess, tokenizer)
      model      : CLIP model with SkyCLIP weights
      preprocess : torchvision transform for 224×224 crops (standard CLIP)
      tokenizer  : clip.tokenize function

    Raises
    ------
    RuntimeError if weights cannot be found or loaded.
    """
    import clip

    device = get_device()
    root = Path(__file__).parent

    # Resolve weights path: argument → env var → default scan
    resolved_path = (
        weights_path
        or os.environ.get(SKYCLIP_WEIGHTS_ENV)
        or (str(_find_default_weights(root)) if _find_default_weights(root) else None)
    )

    # Determine architecture
    arch_override = os.environ.get(SKYCLIP_ARCH_ENV)
    if resolved_path and Path(resolved_path).exists():
        arch = arch_override or _infer_arch_from_path(resolved_path)
        embed_dim = ARCH_EMBED_DIM.get(arch, 512)

        print(f"[skyclip_loader] Loading {arch} (embed_dim={embed_dim}) on {device}")
        print(f"[skyclip_loader] Weights: {resolved_path}")

        model, preprocess = clip.load(arch, device=device)
        state = torch.load(resolved_path, map_location=device, weights_only=False)  # SkyCLIP uses numpy scalars

        # SkyCLIP checkpoint may be nested under "state_dict"
        sd = state.get("state_dict", state)
        # Strip 'module.' prefix added by DataParallel if present
        sd = {k.replace("module.", ""): v for k, v in sd.items()}
        model.load_state_dict(sd, strict=False)
        model.eval()

        # Store embed_dim as an attribute for callers to inspect
        model._geolens_embed_dim = embed_dim
        model._geolens_arch = arch

        print(f"[skyclip_loader] Model ready. embed_dim={embed_dim}")
        tokenizer = clip.tokenize
        return model, preprocess, tokenizer

    else:
        # Attempt to load from HuggingFace
        try:
            from transformers import CLIPModel, CLIPProcessor
            model = CLIPModel.from_pretrained(SKYCLIP_HF_REPO).to(device)
            preprocess = CLIPProcessor.from_pretrained(SKYCLIP_HF_REPO)
            model._geolens_embed_dim = 512
            model._geolens_arch = "ViT-B/32 (HuggingFace)"
            print(f"[skyclip_loader] Loaded from HuggingFace ({SKYCLIP_HF_REPO})")
            return model, preprocess, None
        except Exception as hf_err:
            raise RuntimeError(
                f"SkyCLIP weights not found.\n"
                f"  Checked: {resolved_path!r}\n"
                f"  Default scan: data/embeddings/**/*.pt\n"
                f"  Set SKYCLIP_WEIGHTS env var to the .pt file path.\n"
                f"  Run: python scripts/download_datasets.py\n"
                f"  HuggingFace fallback error: {hf_err}"
            ) from hf_err


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def get_embed_dim(model) -> int:
    """Return the embedding dimension for a loaded SkyCLIP model."""
    # Check attribute set by load_skyclip
    if hasattr(model, "_geolens_embed_dim"):
        return model._geolens_embed_dim
    # Fallback: probe from model
    try:
        return model.visual.output_dim
    except AttributeError:
        return 512  # conservative default for ViT-B/32


def embed_text(model, tokenizer, text: str, device: Optional[torch.device] = None) -> np.ndarray:
    """
    Embed a text prompt using SkyCLIP's text encoder.

    Returns a 1-D numpy array of shape (embed_dim,), L2-normalised.
    Works with both ViT-B/32 (512) and ViT-L/14 (768).
    """
    device = device or get_device()
    with torch.no_grad():
        tokens = tokenizer([text]).to(device)
        features = model.encode_text(tokens)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.cpu().numpy().squeeze()


def embed_crops(
    model,
    preprocess,
    crops: list,
    device: Optional[torch.device] = None,
    batch_size: int = 32,
) -> np.ndarray:
    """
    Embed a list of image crops using SkyCLIP's image encoder.

    Parameters
    ----------
    crops      : list of PIL.Image or np.ndarray — each is a 224×224 crop
    device     : torch device (auto-detected if None)
    batch_size : images per forward pass (reduce if OOM)

    Returns
    -------
    2-D numpy array of shape (N, embed_dim), L2-normalised.
    Works with both ViT-B/32 (512) and ViT-L/14 (768).
    """
    from PIL import Image

    device = device or get_device()
    all_features = []

    for i in range(0, len(crops), batch_size):
        batch = crops[i : i + batch_size]
        pil_batch = [
            Image.fromarray(c) if isinstance(c, np.ndarray) else c
            for c in batch
        ]
        tensors = torch.stack([preprocess(img) for img in pil_batch]).to(device)
        with torch.no_grad():
            features = model.encode_image(tensors)
            features = features / features.norm(dim=-1, keepdim=True)
        all_features.append(features.cpu().numpy())

    return np.vstack(all_features)


def make_crops(
    tile_array: np.ndarray,
    crop_size: int = 224,
    n_crops: int = 3,
) -> list:
    """
    Generate overlapping crops from a tile array for multi-crop indexing.

    Produces n_crops evenly-spaced crops across the tile.
    Minimum tile size must be >= crop_size.

    Returns a list of PIL Images.
    """
    from PIL import Image

    h, w = tile_array.shape[:2]
    if h < crop_size or w < crop_size:
        # Pad if tile is smaller than crop_size
        pad_h = max(0, crop_size - h)
        pad_w = max(0, crop_size - w)
        tile_array = np.pad(
            tile_array,
            ((0, pad_h), (0, pad_w), (0, 0)),
            mode="reflect",
        )
        h, w = tile_array.shape[:2]

    crops = []
    # Positions: top-left, centre, bottom-right (and intermediate for n_crops > 3)
    y_positions = np.linspace(0, h - crop_size, n_crops, dtype=int)
    x_positions = np.linspace(0, w - crop_size, n_crops, dtype=int)

    for y in y_positions:
        for x in x_positions[:1]:  # one column for default 3-crop strategy
            crop = tile_array[y : y + crop_size, x : x + crop_size]
            crops.append(Image.fromarray(crop))

    return crops
