from renderer.stroke_handwriting import WriterProfile
from model.profile_management import ManagedWriterProfile, WriterProfileStore


def profile():
    return WriterProfile(name="Mrs Okafor", strokes={"a": [[(0.0, 0.0), (1.0, 1.0)]], "b": [[(0.0, 1.0), (1.0, 0.0)]]})


def test_correction_creates_new_version_and_requires_reapproval(tmp_path):
    store = WriterProfileStore(tmp_path)
    managed = ManagedWriterProfile(profile(), approved=True)
    store.save(managed)
    store.correct_label(managed, "a", "c", "teacher confirmed scan label")
    assert managed.version == 2
    assert managed.approved is False
    assert "a" not in managed.profile.strokes and "c" in managed.profile.strokes
    assert managed.corrections[-1].new_label == "c"


def test_profile_is_reusable_after_reload_and_approval(tmp_path):
    store = WriterProfileStore(tmp_path)
    managed = ManagedWriterProfile(profile())
    store.approve(managed)
    path = store.save(managed)
    loaded = store.load("Mrs Okafor")
    assert path.exists()
    assert loaded.approved is True
    assert loaded.profile.glyph("a") == profile().glyph("a")
    assert store.list_profiles()[0]["name"] == "Mrs Okafor"


def test_invalid_correction_and_missing_profile_are_explicit(tmp_path):
    store = WriterProfileStore(tmp_path)
    managed = ManagedWriterProfile(profile())
    try:
        store.correct_label(managed, "z", "x")
    except KeyError:
        pass
    else:
        raise AssertionError("Unknown labels must not be silently added")
    try:
        store.load("missing")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Missing profiles must be explicit")
