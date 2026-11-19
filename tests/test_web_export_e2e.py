"""End-to-end test for the additive browser handwriting export route."""

import asyncio
from io import BytesIO
from pathlib import Path

from fastapi.responses import FileResponse




def test_handwriting_export_runs_real_preprocessor_font_compiler_and_pdf_renderer(monkeypatch, tmp_path):
    import cv2
    import numpy as np

    import main

    from io import BytesIO

    image = np.full((600, 720), 255, dtype=np.uint8)
    for index, character in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        row, column = divmod(index, 6)
        cv2.putText(
            image,
            character,
            (column * 120 + 22, row * 120 + 82),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.8,
            0,
            3,
            cv2.LINE_AA
        )
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

    # Two requests in one process must register distinct font faces and both export.
    for _ in range(2):
        response = main.export_handwriting_pdf(
            class_level="SS2",
            term="Second Term",
            week=2,
            sample=FakeUpload()
        )

        assert isinstance(response, FileResponse)
        assert response.media_type == "application/pdf"
        assert Path(response.path).is_file()
        assert Path(response.path).stat().st_size > 1000

        if response.background:
            asyncio.run(response.background())

    assert all(not temp_dir.exists() for temp_dir in temp_dirs)
