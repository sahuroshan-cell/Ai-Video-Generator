"""Crop an uploaded image down to a single clean face for Wav2Lip.

Handles the common case where the upload is a multi-face character sheet
(expression grids, turnaround views, etc.) by running the same face
detector Wav2Lip uses, keeping the highest-confidence face, compositing
away transparency, and padding out to include some shoulder/hair context.
"""
import os
import sys

import cv2
import numpy as np

from render_pipeline import WAV2LIP_DIR

sys.path.insert(0, WAV2LIP_DIR)
import face_detection  # noqa: E402  (Wav2Lip's bundled S3FD detector)

_detector = None


def _get_detector():
    global _detector
    if _detector is None:
        _detector = face_detection.FaceAlignment(face_detection.LandmarksType._2D, flip_input=False, device="cpu")
    return _detector


class NoFaceFound(RuntimeError):
    pass


def prepare_face(src_path, out_path, pad_left=15, pad_right=70, pad_top=70, pad_bottom=160):
    img = cv2.imread(src_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise NoFaceFound(f"could not read image: {src_path}")

    if img.ndim == 3 and img.shape[2] == 4:
        bgr, alpha = img[:, :, :3], img[:, :, 3:4] / 255.0
        bg = np.full_like(bgr, 235)
        composited = (bgr * alpha + bg * (1 - alpha)).astype("uint8")
    else:
        composited = img[:, :, :3] if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    rgb = cv2.cvtColor(composited, cv2.COLOR_BGR2RGB)
    box = _get_detector().get_detections_for_batch(np.array([rgb]))[0]
    if box is None:
        raise NoFaceFound("no face detected in the uploaded image")

    x1, y1, x2, y2 = [int(v) for v in box]
    h, w = composited.shape[:2]
    crop = composited[max(0, y1 - pad_top):min(h, y2 + pad_bottom),
                       max(0, x1 - pad_left):min(w, x2 + pad_right)]
    cv2.imwrite(out_path, crop)
    return out_path
