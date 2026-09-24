"""File storage behind a tiny interface. Local disk in the POC; swap the class to use S3 etc."""

import shutil
from pathlib import Path

from app.config import get_settings


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, rel: str) -> Path:
        path = (self.root / rel).resolve()
        if self.root not in path.parents:  # blocks ../ tricks
            raise ValueError("Path escapes the storage root")
        return path

    def save(self, rel: str, data: bytes) -> None:
        path = self._path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, rel: str) -> bytes:
        return self._path(rel).read_bytes()

    def delete_dir(self, rel: str) -> None:
        shutil.rmtree(self._path(rel), ignore_errors=True)


def get_storage() -> LocalStorage:
    return LocalStorage(Path(get_settings().upload_dir))
