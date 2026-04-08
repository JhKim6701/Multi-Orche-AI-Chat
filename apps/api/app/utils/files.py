from pathlib import Path
import re


FILENAME_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    cleaned = FILENAME_SAFE.sub("_", filename).strip("._")
    return cleaned or "upload.bin"


def safe_join(base: Path, *parts: str) -> Path:
    candidate = (base.joinpath(*parts)).resolve()
    if not str(candidate).startswith(str(base.resolve())):
        raise ValueError("path traversal detected")
    return candidate
