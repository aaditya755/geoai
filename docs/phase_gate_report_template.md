# GeoLens AI — Phase Gate Report Template

Use this template after each phase to document actual implementation status.
Fill in real values only. Mark blocked/manual items honestly.

---

## Phase: P___  — [phase name]

**Date:** YYYY-MM-DD  
**Reported by:** [name]

---

## 1. Implementation status

| Task ID | Description | Status | Notes |
|---------|-------------|--------|-------|
| P__.1 | ... | ✅ Done / 🔲 Blocked / [MANUAL] | |
| P__.2 | ... | | |

---

## 2. Tests run and outcomes

| Test file | Command | Outcome | Notes |
|-----------|---------|---------|-------|
| tests/test_types.py | `pytest tests/test_types.py -v` | PASS / FAIL / NOT RUN | |
| tests/test_spatial_engine.py | `pytest tests/test_spatial_engine.py -v` | | |

Paste actual pytest output here (truncated if long):

```
[paste output]
```

---

## 3. Manual prerequisites completed

- [ ] P1.1 — SpaceNet tiles downloaded
- [ ] P3.2 — check1_skyclip.py run on GPU
- [ ] P3.3 — FAISS index built on GPU
- [ ] P4.7 — MISTRAL_API_KEY obtained and integration test run
- [ ] P6.4 — SARVAM_API_KEY obtained and endpoint verified
- [ ] P7.2 — ~100 crops hand-labelled

---

## 4. External API / integration test results

### Mistral API (REQ-015)
- Status: PASSED / FAILED / NOT RUN (blocked — key not available)
- If run: model used, plan returned (schema-valid? yes/no), fallback exercised?

### Sarvam AI translation
- Status: PASSED / FAILED / NOT RUN (endpoint unverified — see translate.py TODO)
- Endpoint URL confirmed: yes/no
- Request schema confirmed: yes/no

### Jev AI ranking
- Status: NOT RUN (stub only — local scorer used)
- Local scorer: PASSED / FAILED

---

## 5. Unresolved assumptions (from design.md §8)

Mark each as confirmed, refuted, or still unverified:

| # | Assumption | Status |
|---|-----------|--------|
| 1 | SpaceNet v1 ~0.5 m/px | unverified / confirmed: ___ m/px |
| 2 | Sarvam AI endpoint URL | unverified / confirmed: ___ |
| 3 | Jev AI API schema | unverified / confirmed |
| 4 | FAISS flat-IP sufficient | unverified / confirmed |
| 5 | EPSG:32723 correct for Rio | unverified / confirmed from tile header |

---

## 6. P3 gate specifics (fill in after P3 only)

### check1_skyclip.py results

| Metric | Value |
|--------|-------|
| Pool crop × pool text similarity | |
| Pool crop × road text similarity | |
| Margin (pool-pool minus pool-road) | |
| Threshold met (> 0.20 pool-pool)? | yes / no |
| Margin met (> 0.02)? | yes / no |
| All assertions passed? | yes / no |

Model/checkpoint used: ___  
Device: ___  
Runtime: ___  
GPU memory peak: ___

### check2_alignment.py results
- Tiles checked: ___
- Passed: ___
- Failed: ___ (list tile IDs)

### check3_tile_meta.py results
- Tiles in index: ___
- Required provenance keys present: yes / no

### Multi-crop retrieval compatibility
- n_crops used: ___
- Compatible with loaded model: yes / no
- Notes: ___

### Concepts not reliably detectable at available resolution
| Concept | Reason |
|---------|--------|
| solar_panel | < 0.5 m/px feature size (unverified) |
| narrow_drain | < 0.5 m/px feature size (unverified) |
| [add more] | |

---

## 7. Decision required (P3 gate only)

☐ (a) Proceed with SkyCLIP-only  
☐ (b) Add OWLv2 agreement (REQ-027 STRETCH)  
☐ (c) Pivot — describe:

**Awaiting user review before proceeding to P4.**

---

## 8. Next permitted phase

Phase P___ may begin after:
- [ ] This report reviewed by user
- [ ] Gate decision recorded above
- [ ] All MUST tests for this phase pass
