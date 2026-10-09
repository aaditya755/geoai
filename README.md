# GeoLens AI (GEOAI 05)

Natural-language search over aerial tiles and OpenStreetMap vectors for one municipality (SpaceNet Buildings v1, Rio de Janeiro).

## Quick start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Set environment variables
cp .env.example .env
# Edit .env: set MISTRAL_API_KEY, SARVAM_API_KEY, JEV_API_KEY, DEMO_MODE

# 3. Run data preparation (requires manual data download first — see tasks.md P1.1)
python data_prep.py

# 4. Start the API
uvicorn app:app --reload

# 5. Start the frontend
cd frontend && npm install && npm run dev
```

## Demo mode (no GPU or API keys required)

Set `DEMO_MODE=true` in `.env`. The app serves cached results from `data/fixtures/demo_results.json` and shows a **"Sample data"** banner.

## Manual steps

Some steps require human action and cannot be automated:
- **P1.1** Download SpaceNet Buildings v1 tiles from AWS S3
- **P3.2 / P3.3** Run SkyCLIP embedding on GPU (Colab or Kaggle)
- **P3.GATE** Review check1 results before building Phase 4+
- **P4.7** Obtain MISTRAL_API_KEY and run integration test
- **P6.4** Obtain SARVAM_API_KEY and verify Sarvam AI endpoint
- **P7.2** Hand-label ~100 crops for evaluation hold-out set
- **P7.5** Create demo_results.json from a real successful run

See `tasks.md` for the full task list.

## Project structure

```
geolens/
  docs/GEOAI05_SPEC_v2.md   # Source of truth (placeholder; expand as project develops)
  data_prep.py               # Data preparation pipeline [extend only; do not rewrite]
  planner_agent.py           # LLM planner adapter [extend only; do not rewrite]
  concepts.yaml              # Concept registry
  skyclip_loader.py          # SkyCLIP model loader
  index_tiles.py             # FAISS index builder
  vision.py                  # Vision grounding engine
  spatial_engine.py          # GeoPandas spatial operations
  jev_ranker.py              # Jev AI ranking adapter
  translate.py               # Sarvam AI translation adapter
  app.py                     # FastAPI application
  eval.py                    # Precision@K evaluation
  schemas/plan_schema.json   # JSON Schema for plan validation
  scripts/                   # Alignment and metadata checks
  tests/                     # Pytest test suite
  frontend/                  # Vite + React UI
  data/                      # Git-ignored; see design.md §2 for layout
  .kiro/specs/geolens-demo/  # Kiro spec (requirements, design, tasks)
```

## Honesty rules

- The LLM writes **only** a schema-validated JSON plan. No geometric decisions are made by the LLM.
- All displayed metrics come from code measurement, never from LLM output.
- Unsupported or invisible concepts (solar panels, narrow drains) return a plain "not found / too small to see" message.
- "Equivalent SQL" in the UI is labelled **"Equivalent (not executed)"**.
- All fixture/sample data is labelled **"Sample data"**.

## Attributions

| Dataset / resource | Licence | Reference |
|--------------------|---------|----------|
| SpaceNet Buildings v1, Rio de Janeiro | CC BY-SA 4.0 | Etten et al., arXiv:1807.01232 |
| OpenStreetMap contributors | Open Database Licence (ODbL) | openstreetmap.org/copyright |
| SkyScript | See paper | Wang et al., arXiv:2312.12856 |
