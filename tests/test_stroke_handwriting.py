from pathlib import Path

from PIL import Image

from renderer.stroke_handwriting import HandwritingRenderer, WriterProfile


def test_unseen_text_renders_without_font_dependencies(tmp_path):
    output = tmp_path / "unseen.png"
    text = "Synchronization, zigzag, and 2048!"
    image = HandwritingRenderer(seed=123).render(text)
    image.save(output)
    assert output.exists()
    assert Image.open(output).size == (1600, 330)


def test_seed_reproduces_for_quality_assurance():
    text = "A different realization every time."
    first = HandwritingRenderer(seed=22).render(text).tobytes()
    repeat = HandwritingRenderer(seed=22).render(text).tobytes()
    different = HandwritingRenderer(seed=23).render(text).tobytes()
    assert first == repeat
    assert first != different


def test_profile_round_trip_and_custom_trajectory(tmp_path):
    path = tmp_path / "teacher.json"
    profile = WriterProfile(name="teacher-a", slant=0.2)
    profile.strokes["x"] = [[(0.0, 0.0), (1.0, 1.0)]]
    profile.save(path)
    loaded = WriterProfile.load(path)
    assert loaded.name == "teacher-a"
    assert loaded.slant == 0.2
    assert loaded.glyph("x") == [[(0.0, 0.0), (1.0, 1.0)]]
