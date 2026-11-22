# Handwriting recognition research notes

These findings inform the current implementation boundary. They do not establish that the project can recognize arbitrary natural handwriting.

## Findings

- Kraken provides line-recognition and page segmentation facilities, including character/segment geometry where supported by a model. That geometry is model- and task-dependent; it does not by itself guarantee that a connected ink crop is the correct Unicode glyph for cursive teacher writing. Character crops still need confidence checks and human correction before font compilation.
- TrOCR handwritten is a line-level text recognizer. It does not return character-level bounding boxes or verified text-to-glyph alignment, so another alignment or correction stage would be required.
- Neither candidate was validated against a representative teacher handwriting sample with ground-truth transcription, nor benchmarked for the project's free Render service. Neither is enabled in the production route.
- The optional worksheet added to this project can label only its own known cell positions. It is an explicitly controlled calibration workflow, not an HTR system and not a substitute for the intended natural-page workflow.
- Do not import the referenced handwritten.js implementation without reviewing its dependency tree and security posture; prior dependency review found high and critical advisories in its dependency set.

## Sources

- Kraken inference guide: https://kraken.re/7.1/user_guide/inference.html
- Kraken model guide: https://kraken.re/7.1/user_guide/models.html
- Kraken container implementation: https://raw.githubusercontent.com/mittagessen/kraken/main/kraken/containers.py
- Kraken recognition task implementation: https://raw.githubusercontent.com/mittagessen/kraken/main/kraken/tasks/recognition.py
- TrOCR handwritten model card: https://huggingface.co/microsoft/trocr-base-handwritten
- TrOCR paper: https://arxiv.org/abs/2109.10282
- Reference implementation considered: https://github.com/yashlamba/handwrite
- Reference implementation considered: https://github.com/alias-rahil/handwritten.js

## Decision

Keep a recognizer behind the existing provider boundary in `ingestion/open_handwriting.py`, and enable natural-page conversion only after a real teacher sample is available for evaluation and character alignment can be verified. No recognition model, paid API, extra hosting resource, or production-model download was introduced as part of the worksheet workflow.
