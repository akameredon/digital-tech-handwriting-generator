"""End-to-end test for the strict six-row browser handwriting export."""
import asyncio
from io import BytesIO
from pathlib import Path
import cv2
import numpy as np
from fastapi.responses import FileResponse
from ingestion.preprocessor import DEFAULT_SAMPLE_ROWS


def test_handwriting_export_runs_real_preprocessor_font_compiler_and_pdf_renderer(monkeypatch, tmp_path):
    import main

    # Isolated filled blobs — one component per sample cell (matches strict row mapping)
    image = np.full((700, 1250), 255, dtype=np.uint8)
    for row_index, row_text in enumerate(DEFAULT_SAMPLE_ROWS):
        for column, character in enumerate(row_text):
            x0 = 18 + column * 80
            y0 = 30 + row_index * 105
            cv2.rectangle(image, (x0, y0), (x0 + 28, y0 + 36), 0, -1)
    success, encoded = cv2.imencode(".png", image)
    assert success

    class FakeUpload:
        content_type = "image/png"
        def __init__(self):
            self.file = BytesIO(encoded.tobytes())
        def close(self):
            self.file.close()

    temp_dirs = []
    def make_temp_dir(prefix):
        temp_dir = tmp_path / f"real-handwriting-run-{len(temp_dirs)}"
        temp_dir.mkdir()
        temp_dirs.append(temp_dir)
        return str(temp_dir)
    monkeypatch.setattr(main.tempfile, "mkdtemp", make_temp_dir)

    for _ in range(2):
        response = main.export_handwriting_pdf(
            class_level="SS2", term="Second Term", week=2, sample=FakeUpload()
        )
        assert isinstance(response, FileResponse)
        assert response.media_type == "application/pdf"
        assert Path(response.path).is_file()
        assert Path(response.path).stat().st_size > 500
        if response.background:
            asyncio.run(response.background())
    assert all(not temp_dir.exists() for temp_dir in temp_dirs)
