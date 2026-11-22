"""Synthetic-only coverage for the local experimental PDF command."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

import cv2
import pytest

from test_calibration_sheet import _make_calibration_image
from ingestion.calibration_sheet import (CELL_HEIGHT, CELL_WIDTH, GRID_COLUMNS, GRID_LEFT,
                                         GRID_TOP, PAGE_HEIGHT, PAGE_WIDTH, MAX_IMAGE_BYTES)
from curriculum.sample_notes import prepared_lesson_index
from scripts import experimental_writer_pdf as cli


@pytest.fixture(scope="module")
def worksheet(tmp_path_factory):
    # Start with the existing synthetic fixture, adding eight simple nonhuman
    # marks into labeled cells A-H. No teacher sample is stored in the repo.
    image = _make_calibration_image(filled=False)
    height, width = image.shape[:2]
    px = lambda x: round(x / PAGE_WIDTH * width)
    py = lambda y: round((PAGE_HEIGHT - y) / PAGE_HEIGHT * height)
    start = (GRID_COLUMNS - 13) // 2
    for col in range(start, start + 8):
        x = px(GRID_LEFT + (col + 0.5) * CELL_WIDTH)
        cv2.line(image, (x, py(GRID_TOP - CELL_HEIGHT * 0.36)),
                 (x, py(GRID_TOP - CELL_HEIGHT * 0.76)), (20, 25, 30), 3)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    path = tmp_path_factory.mktemp("synthetic") / "sheet.png"
    path.write_bytes(encoded.tobytes())
    return path


def arguments(worksheet, text, output, *extra):
    return ["--worksheet", str(worksheet), "--text-file", str(text), "--output", str(output),
            "--confirm-labels", "--acknowledge-experimental", *map(str, extra)]


def assert_no_temporary_files(directory):
    assert not list(directory.glob(".experimental-writer-*"))


def test_end_to_end_exact_accounting_image_only_a4_and_private_report(tmp_path, worksheet, capsys, monkeypatch):
    text = "AB C\tD\nE FA\nB"
    text_file = tmp_path / "PRIVATE_SOURCE_NAME.txt"
    text_file.write_bytes(text.encode("utf-8"))
    output, report = tmp_path / "result.pdf", tmp_path / "result.json"
    observed = {}
    render = cli.TeacherStrokeGenerator.render

    def spy(self, value, *, seed=0):
        observed["text"] = value
        result = render(self, value, seed=seed)
        observed["placements"] = [(p.offset, p.character) for p in result.placements]
        return result

    monkeypatch.setattr(cli.TeacherStrokeGenerator, "render", spy)
    assert cli.main(arguments(worksheet, text_file, output, "--report", report)) == 0
    captured = capsys.readouterr()
    assert "EXPERIMENTAL" in captured.err and "image-only" in captured.err
    assert "not selectable or accessible" in captured.err
    assert captured.out == "Created PDF: 'result.pdf'\n"
    assert str(tmp_path) not in captured.out and text not in captured.out
    assert output.read_bytes().startswith(b"%PDF-")
    assert observed["text"] == text
    assert observed["placements"] == [(i, c) for i, c in enumerate(text) if c not in " \t\n"]
    data = json.loads(report.read_text())
    accounting = data["accounting"]
    assert data["experimental"] and data["image_only"] and data["page_count"] == 1
    assert data["worksheet_available_glyphs"] == 8 and data["synthetic_joins"] == 0
    assert accounting["source_codepoints"] == len(text)
    assert accounting["placed_glyphs"] + accounting["layout_codepoints"] == len(text)
    assert accounting["placement_offsets_by_page"] == [[i for i, c in enumerate(text) if c not in " \t\n"]]
    assert accounting["layout_offsets"] == {"space": [2, 8], "tab": [4], "lf": [6, 11]}
    raw_report = report.read_text()
    assert str(worksheet) not in raw_report and str(text_file) not in raw_report and text not in raw_report
    assert_no_temporary_files(tmp_path)
    # Poppler is optional for contributors; it is not a Python dependency.
    if shutil.which("pdfinfo") and shutil.which("pdftotext") and shutil.which("pdfimages"):
        info = subprocess.check_output(["pdfinfo", str(output)], text=True)
        assert re.search(r"Page size:\s+595\.\d+ x 841\.\d+ pts \(A4\)", info)
        extracted = subprocess.check_output(["pdftotext", str(output), "-"], text=True)
        assert not extracted.strip()
        images = subprocess.check_output(["pdfimages", "-list", str(output)], text=True)
        assert re.search(r"\b1240\s+1754\b", images)


def test_multipage_keeps_every_character_and_includes_all_images(tmp_path, worksheet):
    text = "AB C\n" * 40 + "DE"
    src, pdf, report = tmp_path / "text.txt", tmp_path / "pages.pdf", tmp_path / "pages.json"
    src.write_bytes(text.encode())
    assert cli.main(arguments(worksheet, src, pdf, "--report", report, "--seed", "41")) == 0
    data = json.loads(report.read_text())
    assert 2 <= data["page_count"] <= cli.MAX_PAGES
    actual_offsets = [x for page in data["accounting"]["placement_offsets_by_page"] for x in page]
    assert actual_offsets == [i for i, c in enumerate(text) if c not in " \t\n"]
    assert len(re.findall(rb"/Type\s*/Page\b", pdf.read_bytes())) == data["page_count"]
    if shutil.which("pdfimages"):
        images = subprocess.check_output(["pdfimages", "-list", str(pdf)], text=True)
        assert len(re.findall(r"\b1240\s+1754\b", images)) == data["page_count"]
    assert_no_temporary_files(tmp_path)


def test_unsupported_offsets_are_exact_and_no_output_or_report(tmp_path, worksheet, capsys):
    src, pdf, report = tmp_path / "source.txt", tmp_path / "result.pdf", tmp_path / "result.json"
    src.write_bytes("A💡B💡\r".encode("utf-8"))
    assert cli.main(arguments(worksheet, src, pdf, "--report", report)) == 1
    err = capsys.readouterr().err
    assert "💡" in err and "(1, 3)" in err
    assert "\\r" in err and "(4,)" in err
    assert "missing_trajectory" in err and "unsupported_whitespace_or_control" in err
    assert not pdf.exists() and not report.exists()
    assert_no_temporary_files(tmp_path)


@pytest.mark.parametrize("flag", ["--confirm-labels", "--acknowledge-experimental"])
def test_each_opt_in_flag_is_required(tmp_path, worksheet, capsys, flag):
    src, pdf = tmp_path / "text.txt", tmp_path / "result.pdf"
    src.write_text("A")
    args = arguments(worksheet, src, pdf)
    args.remove(flag)
    with pytest.raises(SystemExit) as caught:
        cli.main(args)
    assert caught.value.code == 2 and flag in capsys.readouterr().err
    assert not pdf.exists()


@pytest.mark.parametrize("source", [b"", b" \t\n", b"\xff", b"A" * (cli.MAX_TEXT_BYTES + 1),
                                    b"A" * (cli.MAX_TEXT_CHARACTERS + 1)])
def test_invalid_blank_or_oversized_text_never_creates_output(tmp_path, worksheet, capsys, source):
    src, pdf = tmp_path / "text.txt", tmp_path / "result.pdf"
    src.write_bytes(source)
    assert cli.main(arguments(worksheet, src, pdf)) == 1
    assert "ERROR" in capsys.readouterr().err
    assert not pdf.exists()
    assert_no_temporary_files(tmp_path)


def test_missing_nonregular_invalid_blank_and_oversized_worksheet(tmp_path, worksheet, capsys):
    src, pdf = tmp_path / "text.txt", tmp_path / "result.pdf"
    src.write_text("A")
    blank = tmp_path / "blank.png"
    ok, encoded = cv2.imencode(".png", _make_calibration_image(filled=False))
    assert ok
    blank.write_bytes(encoded.tobytes())
    invalid, empty, oversized = tmp_path / "invalid.png", tmp_path / "empty.png", tmp_path / "big.png"
    invalid.write_bytes(b"not an image")
    empty.write_bytes(b"")
    with oversized.open("wb") as f:
        f.truncate(MAX_IMAGE_BYTES + 1)
    for image in (tmp_path / "missing.png", tmp_path, invalid, empty, oversized, blank):
        assert cli.main(arguments(image, src, pdf)) == 1
        assert "ERROR" in capsys.readouterr().err
        assert not pdf.exists()
    assert_no_temporary_files(tmp_path)


def test_existing_pdf_report_and_dangling_symlink_are_never_overwritten(tmp_path, worksheet, capsys):
    src, pdf, report = tmp_path / "text.txt", tmp_path / "out.pdf", tmp_path / "out.json"
    src.write_text("A")
    pdf.write_bytes(b"original pdf")
    assert cli.main(arguments(worksheet, src, pdf, "--report", report)) == 1
    assert pdf.read_bytes() == b"original pdf" and not report.exists()
    pdf.unlink()
    report.write_bytes(b"original report")
    assert cli.main(arguments(worksheet, src, pdf, "--report", report)) == 1
    assert report.read_bytes() == b"original report" and not pdf.exists()
    report.unlink()
    pdf.symlink_to(tmp_path / "missing-target")
    assert cli.main(arguments(worksheet, src, pdf)) == 1
    assert pdf.is_symlink() and not (tmp_path / "missing-target").exists()
    assert "refusing to overwrite" in capsys.readouterr().err
    assert_no_temporary_files(tmp_path)


def test_atomic_race_preserves_competing_destination_and_rolls_back_report(tmp_path, worksheet, monkeypatch):
    src, pdf, report = tmp_path / "text.txt", tmp_path / "out.pdf", tmp_path / "out.json"
    src.write_text("A")
    real_link = os.link
    def race(source, destination):
        if Path(destination) == pdf:
            pdf.write_bytes(b"created by another process")
            raise FileExistsError("destination appeared")
        return real_link(source, destination)
    monkeypatch.setattr(cli.os, "link", race)
    assert cli.main(arguments(worksheet, src, pdf, "--report", report)) == 1
    assert pdf.read_bytes() == b"created by another process"
    assert not report.exists()
    assert_no_temporary_files(tmp_path)


def test_pdf_generation_failure_creates_nothing(tmp_path, worksheet, monkeypatch):
    src, pdf, report = tmp_path / "text.txt", tmp_path / "out.pdf", tmp_path / "out.json"
    src.write_text("A")
    def fail(_pages):
        raise ValueError("injected PDF failure")
    monkeypatch.setattr(cli, "_pdf_bytes", fail)
    assert cli.main(arguments(worksheet, src, pdf, "--report", report)) == 1
    assert not pdf.exists() and not report.exists()
    assert_no_temporary_files(tmp_path)


def test_curriculum_lookup_reads_existing_note_exactly_and_missing_coverage_is_reported(tmp_path, worksheet, capsys):
    key = ("SS1", "First Term", 2)
    path = prepared_lesson_index()[key]
    args = SimpleNamespace(text_file=None, class_level=key[0], term=key[1], week=key[2])
    text, kind = cli._source_text(args)
    assert kind == "prepared_lesson" and text == path.read_bytes().decode("utf-8")
    pdf = tmp_path / "lesson.pdf"
    result = cli.main(["--worksheet", str(worksheet), "--class", key[0], "--term", key[1],
                       "--week", str(key[2]), "--output", str(pdf),
                       "--confirm-labels", "--acknowledge-experimental"])
    err = capsys.readouterr().err
    assert result == 1 and "missing_trajectory" in err and "at (" in err
    assert not pdf.exists()


def test_missing_lesson_and_mutually_exclusive_or_incomplete_selectors(tmp_path, worksheet, capsys):
    src, pdf = tmp_path / "text.txt", tmp_path / "out.pdf"
    src.write_text("A")
    common = ["--worksheet", str(worksheet), "--output", str(pdf), "--confirm-labels", "--acknowledge-experimental"]
    assert cli.main(common + ["--class", "SS1", "--term", "First Term", "--week", "1"]) == 1
    assert "No curriculum-matched prepared lesson" in capsys.readouterr().err
    for source in (["--class", "SS1"], ["--class", "SS1", "--term", "First Term"],
                   ["--text-file", str(src), "--week", "1"],
                   ["--text-file", str(src), "--class", "SS1", "--term", "First Term", "--week", "2"],
                   ["--class", "SS9", "--term", "First Term", "--week", "1"],
                   ["--class", "SS1", "--term", "First Term", "--week", "14"]):
        with pytest.raises(SystemExit) as caught:
            cli.main(common + source)
        assert caught.value.code == 2
    assert not pdf.exists()


def test_direct_cli_runs_outside_repo_and_does_not_disclose_paths(tmp_path, worksheet):
    src, pdf = tmp_path / "private.txt", tmp_path / "safe.pdf"
    src.write_text("AB")
    cmd = [sys.executable, str(Path(cli.__file__).resolve()), *arguments(worksheet, src, pdf)]
    run = subprocess.run(cmd, cwd=tmp_path, text=True, capture_output=True, check=False)
    assert run.returncode == 0, run.stderr
    assert run.stdout == "Created PDF: 'safe.pdf'\n" and str(tmp_path) not in run.stdout
    assert "image-only" in run.stderr and pdf.exists()


def test_existing_supported_curriculum_lesson_renders_verbatim(tmp_path):
    # This existing lesson happens to use only worksheet characters. The
    # fixture contains synthetic computer-drawn marks, not a teacher sample.
    ok, encoded = cv2.imencode(".png", _make_calibration_image())
    assert ok
    image, pdf, report = tmp_path / "full.png", tmp_path / "lesson.pdf", tmp_path / "lesson.json"
    image.write_bytes(encoded.tobytes())
    key = ("SS2", "Third Term", 9)
    source = prepared_lesson_index()[key].read_bytes().decode("utf-8")
    status = cli.main(["--worksheet", str(image), "--class", key[0], "--term", key[1],
                       "--week", str(key[2]), "--output", str(pdf), "--report", str(report),
                       "--confirm-labels", "--acknowledge-experimental"])
    assert status == 0 and pdf.read_bytes().startswith(b"%PDF-")
    data = json.loads(report.read_text())
    assert data["source_kind"] == "prepared_lesson"
    assert data["accounting"]["source_codepoints"] == len(source)
    offsets = [n for page in data["accounting"]["placement_offsets_by_page"] for n in page]
    assert offsets == [i for i, ch in enumerate(source) if ch not in " \t\n"]
    assert source not in report.read_text() and str(image) not in report.read_text()


def test_page_budget_failure_never_truncates_or_creates_output(tmp_path, worksheet, capsys):
    src, pdf, report = tmp_path / "text.txt", tmp_path / "out.pdf", tmp_path / "out.json"
    src.write_text("A" + "\n" * 245)
    assert cli.main(arguments(worksheet, src, pdf, "--report", report)) == 1
    assert "page count" in capsys.readouterr().err
    assert not pdf.exists() and not report.exists()
    assert_no_temporary_files(tmp_path)


def test_renderer_accounting_failure_is_not_silently_published(tmp_path, worksheet, monkeypatch, capsys):
    from dataclasses import replace
    src, pdf = tmp_path / "text.txt", tmp_path / "out.pdf"
    src.write_text("AB")
    render = cli.TeacherStrokeGenerator.render
    def omit(self, text, *, seed=0):
        result = render(self, text, seed=seed)
        return replace(result, placements=result.placements[:-1])
    monkeypatch.setattr(cli.TeacherStrokeGenerator, "render", omit)
    assert cli.main(arguments(worksheet, src, pdf)) == 1
    assert "accounting failed" in capsys.readouterr().err
    assert not pdf.exists()
    assert_no_temporary_files(tmp_path)


def test_jpg_worksheet_is_supported(tmp_path, worksheet):
    jpeg = tmp_path / "scan.jpg"
    ok, encoded = cv2.imencode(".jpg", cv2.imread(str(worksheet)), [cv2.IMWRITE_JPEG_QUALITY, 98])
    assert ok
    jpeg.write_bytes(encoded.tobytes())
    text, pdf = tmp_path / "text.txt", tmp_path / "out.pdf"
    text.write_text("AB")
    assert cli.main(arguments(jpeg, text, pdf)) == 0
    assert pdf.read_bytes().startswith(b"%PDF-")


@pytest.mark.parametrize("flag,abbreviation", [
    ("--confirm-labels", "--confirm"),
    ("--acknowledge-experimental", "--acknowledge"),
])
def test_opt_in_flags_cannot_be_abbreviated(tmp_path, worksheet, flag, abbreviation):
    src, pdf = tmp_path / "text.txt", tmp_path / "out.pdf"
    src.write_text("A")
    args = arguments(worksheet, src, pdf)
    args[args.index(flag)] = abbreviation
    with pytest.raises(SystemExit) as caught:
        cli.main(args)
    assert caught.value.code == 2 and not pdf.exists()


def test_interruption_during_publication_rolls_back_both_outputs(tmp_path, worksheet, monkeypatch):
    src, pdf, report = tmp_path / "text.txt", tmp_path / "out.pdf", tmp_path / "out.json"
    src.write_text("A")
    real_link = os.link
    def interrupted(source, destination):
        real_link(source, destination)
        if Path(destination) == pdf:
            raise KeyboardInterrupt()
    monkeypatch.setattr(cli.os, "link", interrupted)
    with pytest.raises(KeyboardInterrupt):
        cli.main(arguments(worksheet, src, pdf, "--report", report))
    assert not pdf.exists() and not report.exists()
    assert_no_temporary_files(tmp_path)


def test_prepared_index_rejects_oversized_note_before_indexing(tmp_path, monkeypatch):
    root = tmp_path / "project"
    (root / "samples").mkdir(parents=True)
    (root / "samples" / "large.md").write_bytes(b"x" * (cli.MAX_TEXT_BYTES + 1))
    monkeypatch.setattr(cli, "ROOT", root)
    def forbidden(_root):
        pytest.fail("index read an unbounded curriculum file")
    monkeypatch.setattr(cli, "prepared_lesson_index", forbidden)
    args = SimpleNamespace(text_file=None, class_level="SS1", term="First Term", week=1)
    with pytest.raises(ValueError, match="size limit"):
        cli._source_text(args)
