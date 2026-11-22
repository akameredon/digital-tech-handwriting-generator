# TrOCR smoke benchmark

Date of run: 2026-11-22

Provider: `microsoft/trocr-small-handwritten`

Runtime: CPU, 2 PyTorch threads, local sandbox

The provider loaded the real model and produced a transcription for three locally generated printed-text images. The run measured zero CER and zero WER on those fixtures. This is an execution smoke test only, not evidence of handwriting accuracy: the fixtures were generated with a system font and do not represent teacher notebook photographs.

The first inference included model initialization and was substantially slower than subsequent inferences. The benchmark records per-case latency and peak resident-memory increase so cold-start and warm-request behavior remain visible. Confidence was below the review threshold for two of the three cases, which correctly produced a review rate of 66.7% rather than silently treating exact text as certainty.

No real teacher handwriting dataset is present in the repository. A production readiness decision still requires consented real pages, human ground-truth transcriptions, and a benchmark run against the target deployment environment.
