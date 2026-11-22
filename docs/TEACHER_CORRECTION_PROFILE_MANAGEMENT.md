# Teacher correction and profile management

`model/profile_management.py` implements Rank 11. `WriterProfileStore` saves reusable handwriting identities with atomic file replacement, version numbers, approval state, and an append-only correction history.

A teacher can correct a mislabeled trajectory, which increments the profile version, records the old and new labels with a timestamp and reason, and returns the profile to an unapproved state. The profile must be explicitly approved again before reuse. Profiles can be listed, loaded, and reused across generated lessons.

```python
from model.profile_management import ManagedWriterProfile, WriterProfileStore

store = WriterProfileStore("profiles")
managed = store.load("Mrs Okafor")
store.correct_label(managed, "q", "g", "teacher reviewed ambiguous scan")
store.approve(managed)
store.save(managed)
```

Unknown profiles and unknown labels fail explicitly; the store never silently creates a trajectory from a correction request.
