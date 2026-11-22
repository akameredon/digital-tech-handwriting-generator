# Local HTR benchmarking

The project keeps the handwriting-recognition model behind the existing `HTRProvider` contract. The base application does not install PyTorch or Transformers, and no model is downloaded during an API request.

## Install the optional provider

```bash
pip install -e '.[htr,test]'
```

Provision the model during an explicit build or benchmark step. The default benchmark mode is local-cache-only:

```bash
python scripts/benchmark_htr.py samples/htr_manifest.jsonl \
  --model microsoft/trocr-small-handwritten \
  --threads 2 \
  --output htr-report.json
```

Use `--allow-download` only when provisioning a controlled environment. Do not enable it in a request-serving process.

## Manifest format

One JSON object per line:

```json
{"case_id":"page-01-line-01","image_path":"samples/lines/page-01-line-01.png","reference":"A handwritten line"}
```

The benchmark reports character error rate (CER), word error rate (WER), mean and p95 latency, peak resident-memory increase, confidence-based review rate, and per-case results. Reference transcriptions must be created by a human and must not be inferred from the provider output.

## Scope boundary

TrOCR recognizes line crops. It does not solve page segmentation, character bounding boxes, or text-to-glyph alignment. Those remain separate pipeline stages and must be measured independently. A model that produces text is not evidence that its character positions are safe for font compilation.

Low confidence is reported for review. The system never substitutes a fake provider, silently downloads a model, or treats a missing confidence estimate as certainty.
