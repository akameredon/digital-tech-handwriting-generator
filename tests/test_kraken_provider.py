"""Tests for the optional Kraken provider's strict character geometry contract."""
from ingestion.kraken_provider import _HocrLineParser, _parse_boxes, _parse_confidences


def test_hocr_parser_reads_text_character_boxes_and_confidence():
    markup = (
        '<span class="ocr_line" x_bboxes="1,2,9,18; 10,2,18,18" '
        'x_conf="0.91 0.72"><span class="ocrx_word">Hi</span></span>'
    )
    parser = _HocrLineParser()
    parser.feed(markup)
    assert parser.text == "Hi"
    assert parser.boxes == [[1, 2, 8, 16], [10, 2, 8, 16]]
    assert parser.confidences == [0.91, 0.72]


def test_hocr_box_parser_does_not_accept_invalid_or_empty_regions():
    assert _parse_boxes("0,0,0,10; 2,2,12,12") == [[2, 2, 10, 10]]


def test_confidences_are_normalized_to_probability_range():
    assert _parse_confidences("91 0.5 120") == [0.91, 0.5, 1.0]
