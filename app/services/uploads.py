import io
import uuid

from PIL import Image, ImageOps, UnidentifiedImageError

from ..extensions import db
from ..models.stored_file import StoredFile

MAX_BYTES = 4 * 1024 * 1024


def save_image(storage):
    """Only real JPG/PNG images get through. They are re-encoded, which drops hidden data."""
    data = storage.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Each image must be 4 MB or less.")
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
    out = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(out, "JPEG", quality=85)
        ext, mime = ".jpg", "image/jpeg"
    else:
        img.save(out, "PNG")
        ext, mime = ".png", "image/png"
    payload = out.getvalue()
    name = uuid.uuid4().hex + ext
    db.session.add(StoredFile(name=name, mime=mime, data=payload))
    return name, len(payload)


def read(name):
    row = db.session.get(StoredFile, name)
    return row.data if row else None


def remove(name):
    row = db.session.get(StoredFile, name)
    if row:
        db.session.delete(row)