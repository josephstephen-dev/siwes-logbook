import io
import os
import uuid

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024


def _dir():
    path = current_app.config.get("UPLOAD_DIR") or os.path.join(current_app.instance_path, "uploads")
    os.makedirs(path, exist_ok=True)
    return path


def path_for(name):
    return os.path.join(_dir(), os.path.basename(name))


def save_image(storage):
    """Only real JPG/PNG images get through; they are re-encoded, which drops hidden data."""
    data = storage.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Each image must be 5 MB or less.")
    try:
        Image.open(io.BytesIO(data)).verify()
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.load()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise ValueError("Upload a JPG or PNG photo.")
    if fmt not in ("JPEG", "PNG"):
        raise ValueError("Upload a JPG or PNG photo.")
    img = ImageOps.exif_transpose(img)
    img.thumbnail((2000, 2000))
    name = uuid.uuid4().hex + (".png" if fmt == "PNG" else ".jpg")
    if fmt == "JPEG":
        img.convert("RGB").save(path_for(name), "JPEG", quality=85)
    else:
        img.save(path_for(name), "PNG")
    return name, os.path.getsize(path_for(name))


def remove(name):
    try:
        os.remove(path_for(name))
    except FileNotFoundError:
        pass