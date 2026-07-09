"""End-to-end image job dispatch through process_image (DB + registry)."""
import json
import os
import shutil

import pytest

from app.db.enums import ImageOperation, ImageStatus
from app.db.models.image import Image
from app.workers.image_processor import process_image


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_image_to_shorts_job_completes(db, tmp_path):
    from PIL import Image as PILImage

    paths = []
    for i in range(2):
        p = tmp_path / f"src{i}.png"
        PILImage.new("RGB", (640, 480), (i * 100, 80, 160)).save(p)
        paths.append(str(p))

    img = Image(operation=ImageOperation.image_to_shorts, status=ImageStatus.pending,
                input_paths=json.dumps(paths))
    db.add(img)
    db.commit()
    db.refresh(img)

    process_image(img.id)

    db.refresh(img)
    assert img.status == ImageStatus.completed
    assert img.output_path and img.output_path.endswith(".mp4")
    assert os.path.exists(img.output_path)
    shutil.rmtree(os.path.dirname(img.output_path), ignore_errors=True)
