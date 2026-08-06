import hashlib
from dataclasses import dataclass
from pathlib import Path

_CHUNK_SIZE = 65536


@dataclass(frozen=True)
class FileStat:
    size_bytes: int
    mtime: float


def stat_file(path: Path) -> FileStat:
    """Cheap pre-filter signal: size + mtime, checked before touching content."""
    stat = path.stat()
    return FileStat(size_bytes=stat.st_size, mtime=stat.st_mtime)


def hash_file(path: Path) -> str:
    """Full content hash, used as the authoritative change-detection key
    once the cheap mtime/size pre-filter says a file might have changed."""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
