# GeoLens AI - End-to-End System Audit

Generated: 2026-10-09  
Target Query: "Find buildings within 200 metres of a park"

## Executive Summary

**CRITICAL FINDING**: The GeoLens AI system has a fundamental architecture mismatch. It performs semantic image retrieval (SkyCLIP) but returns tile footprints as if they were object detections. There is no actual object detection pipeline implemented.

## Component Audit

| Component | Required Behaviour | Actual Implementation | Status | Root Cause / Next Action |
|---|---|---|---|---|
| **Frontend Query Input** | Submit natural language to /chat | React frontend exists | UNVERIFIED | Need to test frontend integration |  
| **Environment Loading** | Load .env with dotenv | ✅ `load_dotenv()` in app.py | WORKING | Confirmed working |
| **LLM Planning** | Convert query to schema-validated JSON | OpenRouter with openrouter/free model | WORKING | Real LLM calls successful, no fallback |
| **Concept Registry** | Load concepts.yaml for 12 concepts | ✅ Loaded successfully | WORKING | All concepts loaded |
| **OSM Data Loading** | Load vector layers (road/building/park) | ✅ 3 layers loaded | WORKING | 5 roads, 8 buildings, 3 parks |
| **SkyCLIP Model Loading** | Load ViT-B/32 for semantic retrieval | ✅ Model loads on CPU | WORKING | 512-dim embeddings, loads successfully |
| **FAISS Index** | Semantic image retrieval index | ✅ 50 tiles indexed | WORKING | Returns ranked candidates by similarity |
| **Tile Footprints** | Geographic metadata for tiles | ✅ 20 tiles with CRS data | WORKING | Valid EPSG:32723 geometries |
| **Vision Grounding** | Ground concepts to image candidates | ✅ Returns 50 SkyCLIP candidates | PARTIALLY WORKING | **CRITICAL**: Returns tile footprints, not detections |
| **Object Detection** | Detect buildings/objects in retrieved tiles | ❌ NOT IMPLEMENTED | NOT IMPLEMENTED | **BLOCKER**: No detection pipeline exists |
| **Georeferencing** | Convert pixel coords to map coordinates | ❌ NOT IMPLEMENTED | NOT IMPLEMENTED | Uses tile footprints instead |
| **Spatial Filtering** | Apply distance/intersection operations | ✅ GeoPandas operations work | WORKING | Processes geometries correctly |
| **Results Assembly** | Format response with valid geometries | ✅ Returns JSON structure | PARTIALLY WORKING | Contains tile footprints as "results" |
| **Map Rendering** | Display results on interactive map | Unknown (frontend not tested) | UNVERIFIED | Need frontend integration test |
| **Export** | Export results as GeoJSON/CSV | /export endpoint exists | UNVERIFIED | Need to test with real results |

## Critical Architecture Problem

### Issue: Tile Footprints Masquerading as Object Detections

**What Should Happen**: 
1. SkyCLIP retrieves semantically relevant image tiles
2. Object detection model (OWLv2/Grounding DINO) detects buildings within those tiles  
3. Detection pixel coordinates converted to map coordinates
4. Spatial filtering applies to actual building polygons

**What Actually Happens**:
1. SkyCLIP retrieves 50 relevant tiles ✅
2. System returns tile footprint geometries as "building detections" ❌
3. Spatial filtering operates on tile polygons, not building polygons ❌
4. Results show entire tile areas, not individual buildings ❌

**Evidence from "Show all parks" query**:
```json
{
  "candidates": [
    {
      "tile_id": "3band_AOI_1_RIO_img10",
      "score": 0.272, 
      "concept_id": "park", 
      "geometry_wkt": "POLYGON ((625798.90... [TILE FOOTPRINT]"
    }
  ],
  "results": [
    {
      "tile_id": "3band_AOI_1_RIO_img10", 
      "concept_id": "park",
      "geometry_wkt": "POLYGON ((625798.90... [SAME TILE FOOTPRINT]"
    }
  ]
}
```

The system reports "park" detections but returns tile-sized polygons (~200m x 200m), not actual park boundaries.

## Stage-by-Stage Analysis

### Stage A: Query and Planning ✅ WORKING
- **LLM Provider**: OpenRouter with `openrouter/free` model working
- **Schema Validation**: Plans pass Pydantic validation  
- **Concept Mapping**: Correctly identifies `building` target and `park` reference
- **No Fallback**: Real LLM generates plans, no rule-based fallback

### Stage B: Data and Retrieval ✅ WORKING  
- **SkyCLIP**: Successfully loads ViT-B/32 model and generates embeddings
- **FAISS Index**: Returns 50 semantically ranked tiles for "park" queries
- **Tile Metadata**: Valid geographic footprints in EPSG:32723
- **OSM Data**: 3 layers loaded with valid geometries

### Stage C: Vision and Georeferencing ❌ BROKEN
- **Object Detection**: MISSING - No actual detection pipeline implemented
- **Pixel-to-Map Conversion**: MISSING - No coordinate transformation  
- **Detection Validation**: MISSING - No bounding box or polygon validation
- **Output**: Tile footprints returned instead of object detections

### Stage D: Spatial Verification ⚠️ PARTIALLY WORKING
- **Spatial Operations**: GeoPandas engine works correctly with valid geometries
- **Distance Calculations**: Accurate metre-based calculations in EPSG:32723
- **Problem**: Operating on wrong geometric primitives (tiles vs objects)

### Stage E: Frontend Integration ⚠️ UNVERIFIED
- **API Response**: Valid JSON structure returned
- **Export Endpoint**: Exists but not tested with real results
- **Frontend**: Not tested for integration

## Data Asset Analysis

| Asset | Expected | Actual | Status | Impact |
|---|---|---|---|---|
| **SpaceNet Images** | Full Rio dataset | 50 tiles (minimal subset) | INSUFFICIENT | Limited test coverage |
| **SkyCLIP Index** | Embeddings for all tiles | 50 tile embeddings | MINIMAL | Functional but limited |
| **OSM Vector Data** | Real Rio extract | Demo data (5 roads, 8 buildings, 3 parks) | DEMO QUALITY | Spatial relationships artificial |
| **Object Detection Models** | OWLv2/Grounding DINO configured | NOT IMPLEMENTED | MISSING | Complete vision pipeline gap |
| **Tile Footprints** | Geographic metadata | 20 tiles with valid CRS | MINIMAL | Functional for current tiles |

## Test Results: Target Query Analysis

**Query**: "Find buildings within 200 metres of a park"

- **Planning**: ✅ Generates valid plan with building target, park reference, 200m distance
- **Retrieval**: ✅ SkyCLIP returns 50 tile candidates  
- **Detection**: ❌ No building detection performed
- **Spatial**: ❌ Operates on tile footprints instead of buildings
- **Result**: ❌ Empty results array (spatial filtering removes tiles, not buildings)

**Why Results Are Empty**: The system tries to find tile footprints within 200m of park areas, but the demo park geometries and tile footprints don't have the required spatial relationships.

## P3 SkyCLIP Evaluation Status

**NOT EXECUTED** - The system needs working object detection before SkyCLIP evaluation makes sense. SkyCLIP retrieval is working (returns relevant tiles for "park" queries), but without object detection, retrieval quality cannot be properly evaluated.

## Root Cause Summary

1. **Missing Vision Pipeline**: No object detection implementation
2. **Architecture Confusion**: Tile retrieval treated as object detection  
3. **Geometric Mismatch**: Spatial operations on wrong primitives
4. **Demo Data Limitations**: Artificial spatial relationships
5. **Pipeline Incompleteness**: Vision stage not implemented per specification

## Next Actions Required

### P0 Critical Blockers
1. **Implement Object Detection Pipeline** - Add OWLv2/Grounding DINO to detect buildings in retrieved tiles
2. **Add Georeferencing** - Convert detection pixel coordinates to map coordinates  
3. **Fix Result Assembly** - Use detection geometries, not tile footprints
4. **Test Frontend Integration** - Verify complete workflow through UI

### P1 Integration Issues  
1. **Run P3 SkyCLIP Evaluation** - Execute check1 evaluation as required
2. **Expand Test Data** - Use more realistic OSM data and image tiles
3. **Add Detection Validation** - Verify detection quality and geometric validity
4. **Frontend-Backend Testing** - Test complete user workflow

### P2 Quality Improvements
1. **Add Deterministic Spatial Tests** - Test spatial engine with known geometries
2. **Improve Error Handling** - Handle detection failures gracefully  
3. **Export Validation** - Test GeoJSON export with real detections

## Evidence Requirements for Success

To claim end-to-end success, must demonstrate:

1. **Real Object Detection**: Building polygons detected within retrieved tiles
2. **Valid Georeferencing**: Detection coordinates properly transformed to EPSG:32723
3. **Spatial Verification**: Distance calculations on detection geometries, not tiles
4. **Frontend Integration**: Query → plan → retrieval → detection → spatial → map → export
5. **SkyCLIP Evaluation**: P3 check1 results demonstrating retrieval quality

## Current Status: NOT END-TO-END FUNCTIONAL

The system performs semantic image retrieval correctly but has no object detection capability. Results show tile footprints labeled as object detections, making the entire spatial verification meaningless.

**IMMEDIATE ACTION REQUIRED**: Implement the missing object detection pipeline before proceeding with any other improvements.