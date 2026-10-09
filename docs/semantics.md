# GeoLens AI — Spatial and Plan Semantics

Source of truth: `docs/GEOAI05_SPEC_v2.md`  
This file documents the exact meaning of every concept kind, relation type,
and proposed field. It exists so that the UI, the planner, the spatial engine,
and any future contributor share one unambiguous definition.

---

## 1. Concept kinds

### `instance`

The target object is detected **visually** from aerial imagery using the
SkyCLIP model. A FAISS index search retrieves the top-K tiles whose
mean-pooled multi-crop embedding is most similar to the concept's text prompt.

- Detection is probabilistic. Score is cosine similarity in CLIP embedding
  space; it is NOT a classification confidence.
- Results may include false positives, especially for visually ambiguous
  concepts (e.g. small rooftop features at ~0.5 m/px).
- Where the concept also has an OSM key, an OSM fallback is attempted when
  the vision path returns zero results.

### `osm_only`

The target object is retrieved **deterministically** from OpenStreetMap vector
data. No vision model is called. The OSM GeoDataFrame is filtered by
`(osm_key, osm_value)` as declared in `concepts.yaml`.

- Results reflect what is mapped in OSM for the tile bounding box at the time
  of the last `data_prep.py` run. They do not reflect real-time OSM edits.
- OSM coverage in Rio de Janeiro varies by neighbourhood and feature type.
  Not all roads, buildings, or parks are mapped.
- `osm_only` results have `score = 1.0` (deterministic lookup, not a
  similarity score). Do not interpret this as "100% confidence".

---

## 2. Relation types

All spatial operations are performed in **EPSG:32723** (UTM Zone 23S,
metres). This projection is standard for Rio de Janeiro but should be
confirmed against SpaceNet tile CRS metadata (unverified assumption #5 in
`design.md §8`).

### `dwithin`

```
dwithin(candidates, reference, distance_m)
```

Returns only those candidates whose geometry is within `distance_m` **metres**
of **any** geometry in the reference layer. "Within" is a closed predicate:
a candidate exactly at `distance_m` is included.

- Measured by `shapely.geometry.distance()` after reprojecting both layers to
  EPSG:32723. This is the straight-line (Euclidean) distance in the projected
  plane, not geodesic.
- Adds a `measured_distance_m` column with the actual minimum distance to the
  nearest reference geometry. Values are finite and ≥ 0.
- `distance_m` must be a non-negative number. A value of 0 means "touching or
  overlapping".

### `intersects`

```
intersects(candidates, reference)
```

Returns only those candidates whose geometry **intersects** any geometry in
the reference layer. Two geometries intersect if they share any point
(including boundary touches).

- Sets `measured_distance_m = 0.0` for all matches (they touch or overlap).
- Uses `shapely.geometry.intersects()` after reprojection.

---

## 3. PROPOSED fields (feature-flagged — not yet approved for production)

Both fields below are gated behind environment-variable feature flags.
**No production code path may depend on them until the team formally approves
their schema and semantics.**

### `relations[].negate` — flag: `FEATURE_NEGATE`

```
negate(inner_result, all_candidates)
```

Returns all candidates from `all_candidates` that are **not present** in
`inner_result`, where presence is determined by the compound key
`(tile_id, bbox)`.

**Explicit limitation:** Negate operates on the output of a spatial
predicate. It does NOT mean "objects that are provably absent from the
area". Missing data, low SkyCLIP scores, or out-of-coverage OSM areas are
not evidence of absence. A negate result must be interpreted as
"candidates that did not satisfy the inner relation in the available data",
not as "objects confirmed to not be near the reference".

This distinction must be visible in the UI: negate results should carry a
label such as "Not matching [relation] — based on available data only."

### `target.filters.min_area_m2` — flag: `FEATURE_MIN_AREA`

Filters the candidate set to include only objects whose area (computed from
the geometry column in EPSG:32723) is ≥ `min_area_m2` square metres.

**Requirements for correct use:**
- The candidate GeoDataFrame must have a valid geometry column in a projected
  CRS (EPSG:32723) before this filter is applied.
- Area is computed as `geometry.area` in square metres. For point or line
  geometries this is 0; those candidates are excluded when `min_area_m2 > 0`.
- `min_area_m2` must be ≥ 0. A value of 0 is a no-op.
- Tile-level bounding boxes are **not** the same as object footprints. If the
  geometry column contains tile footprints rather than individual building
  polygons, the area filter applies to tile footprints, not building areas.
  This limitation must be documented in any result that uses this filter.

---

## 4. Negation and missing data — explicit warning

**Do not interpret a negate result as proof of absence.**

Example: "swimming pools NOT within 100 m of a road" means the spatial
engine found no pool candidates within 100 m of the reference roads layer
**in the available indexed tiles and OSM data**. It does NOT mean those
pools are confirmed to be absent from those tiles. Possible causes of a
false "not near road" result include:

- Pool candidate was not retrieved by SkyCLIP (low similarity score, missed
  in top-K).
- Road is not mapped in the OSM extract for that area.
- Tile was not indexed (partial index coverage).

Any UI presenting negate results must include a disclaimer to this effect.

---

## 5. Area units

All areas used in `min_area_m2` and reported in `area_m2` are in
**square metres**, computed from geometries projected in EPSG:32723.
Do not use pixel areas or WGS84 degree-squared areas for this computation.

---

## 6. Backward compatibility

Existing plans without `negate` or `min_area_m2` fields remain valid.
The schema accepts these fields as optional and defaults them to `false`
and `null` respectively. Existing code that does not set these fields
continues to work unchanged.
