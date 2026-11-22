# Natural handwriting validation

Workstream 4 adds a reproducible, dataset-driven validation harness for the complete natural-page path. It runs page intake, line recognition, geometry-gated glyph alignment, and labelled-text scoring as one report.

## Manifest

Use JSONL with one case per line:

```json
{"case_id":"teacher-page-01","image_path":"pages/page-01.jpg","reference_text":"Hello class","real_data":true}
```

`reference_text` must be a human transcription. `real_data` must be set to `true` only for an actually labelled teacher page. Synthetic fixtures should set it to `false`.

## Run

```bash
HTR_PROVIDER=kraken HTR_KRAKEN_MODEL=/models/teacher.mlmodel \
  python scripts/validate_natural_handwriting.py validation.jsonl \
  --provider kraken --output validation-report.json
```

The report includes CER, WER, page review rate, geometry candidate rate, per-page review counts, and pass/fail status. A synthetic report can validate the harness, but the CLI exits with status `2` unless the manifest is explicitly all-real labelled data and every case passes the configured CER/WER and alignment gates.

This does not fabricate a ground truth dataset. Until real teacher pages and transcriptions are supplied, production handwriting quality remains unverified.
