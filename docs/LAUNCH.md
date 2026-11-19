# Launch checklist — D.Lesson Studio v1.1.0

## Pre-flight (local or CI)

```bash
python -m pytest tests/ -q
# optional if Node available:
cd frontend && npm ci && npm run build && cd ..
```

Docker image builds the frontend itself (see Dockerfile). Render uses Docker.

## Deploy

1. Commit all changes on a branch (e.g. `release/1.1.0`).
2. Push and open PR → confirm GitHub Actions green.
3. Merge to `main`.
4. Render auto-deploys (`render.yaml` → `autoDeployTrigger: checksPass`).
5. Confirm:
   - `GET https://d-lesson-studio.onrender.com/health` → version `1.1.0`
   - Homepage loads teacher flow
   - Pick SS1 / First Term / Week 1 → note appears
   - Upload isolated-character sample → PDF downloads

## Teacher sample sheet

- In-app tips on the upload step
- Printable guide: `/sample-sheet-guide.png`
- Rule: separate characters only; no sentences on the sample page

## Evidence already produced

- Curriculum: prepared notes for instructional weeks
- Tests: pytest suite under `tests/`

## After launch (day 1)

- Watch Render logs for 422 spikes (bad photos)
- Collect 2–3 teacher samples; refine heuristics if needed
