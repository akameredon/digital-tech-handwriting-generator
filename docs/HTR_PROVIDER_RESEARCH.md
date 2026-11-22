# HTR provider research

Kraken documentation states that its recognition record includes the character prediction, approximate character cuts, and confidences. Kraken exposes these through `record.prediction`, `record.cuts`, and `record.confidences`. Its current feature documentation also lists word bounding boxes and character cuts.

Source: [Kraken API documentation](https://kraken.re/3.0/api.html)

Source: [Kraken 6.0 documentation](https://kraken.re/6.0.0/index.html)

Implementation consequence: line-level TrOCR remains suitable for transcription benchmarking but cannot satisfy character-to-glyph alignment alone. A Kraken adapter can satisfy the geometry-aware provider contract when a compatible recognition model is explicitly provisioned and its cuts are mapped to the line crop coordinates.
