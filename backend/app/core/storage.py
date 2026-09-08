import os
import re
import uuid
import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Optional, Tuple, Union

from fastapi import HTTPException, status
from backend.app.core.config import settings


class StorageProvider(ABC):
    """Abstract storage provider interface for file persistence."""

    @abstractmethod
    def save_file(
        self,
        content: bytes,
        original_filename: str,
        subfolder: str = "documents",
    ) -> Tuple[str, str, int]:
        """
        Persist file content securely.
        Returns: (storage_path_key, sha256_hash, file_size_bytes)
        """
        pass

    @abstractmethod
    def get_file_bytes(self, storage_path_key: str) -> bytes:
        """Retrieve raw file content bytes from storage key."""
        pass

    @abstractmethod
    def delete_file(self, storage_path_key: str) -> bool:
        """Delete stored file by key. Returns True if deleted or already absent."""
        pass

    @abstractmethod
    def file_exists(self, storage_path_key: str) -> bool:
        """Check if file exists for given key."""
        pass

    @abstractmethod
    def get_absolute_path(self, storage_path_key: str) -> Path:
        """Resolve safe absolute path for local files."""
        pass


class LocalStorageProvider(StorageProvider):
    """
    Local filesystem storage provider with path traversal protection
    and non-guessable secure UUID-based storage keys.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or settings.STORAGE_LOCAL_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_extension(self, original_filename: str) -> str:
        """Extract and sanitize file extension to avoid executable execution."""
        ext = Path(original_filename).suffix.lower()
        # Clean extension: only alphanumeric
        clean_ext = re.sub(r"[^a-z0-9]", "", ext)
        if not clean_ext:
            return "dat"
        return clean_ext

    def _resolve_safe_path(self, storage_path_key: str) -> Path:
        """
        Resolve storage key to absolute path and verify it remains
        strictly within the base storage directory (preventing directory traversal).
        """
        # Normalize slashes
        normalized_key = storage_path_key.replace("\\", "/").lstrip("/")
        target_path = (self.base_dir / normalized_key).resolve()

        # Enforce boundary check
        try:
            target_path.relative_to(self.base_dir)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: Path traversal detected.",
            )
        return target_path

    def save_file(
        self,
        content: bytes,
        original_filename: str,
        subfolder: str = "documents",
    ) -> Tuple[str, str, int]:
        """
        Save file content to local disk with unique UUID filename.
        Computes SHA-256 hash during write.
        """
        file_size = len(content)
        sha256_hash = hashlib.sha256(content).hexdigest()

        # Sanitize subfolder and extension
        clean_subfolder = re.sub(r"[^a-zA-Z0-9_\-]", "", subfolder) or "documents"
        clean_ext = self._sanitize_extension(original_filename)

        # Generate unique storage filename (never use original filename as storage key)
        storage_filename = f"{uuid.uuid4().hex}.{clean_ext}"
        storage_key = f"{clean_subfolder}/{storage_filename}"

        target_path = self._resolve_safe_path(storage_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with open(target_path, "wb") as f:
            f.write(content)

        return storage_key, sha256_hash, file_size

    def get_file_bytes(self, storage_path_key: str) -> bytes:
        target_path = self._resolve_safe_path(storage_path_key)
        if not target_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored document file not found on disk.",
            )
        with open(target_path, "rb") as f:
            return f.read()

    def delete_file(self, storage_path_key: str) -> bool:
        target_path = self._resolve_safe_path(storage_path_key)
        if target_path.is_file():
            try:
                target_path.unlink()
                return True
            except OSError:
                return False
        return True

    def file_exists(self, storage_path_key: str) -> bool:
        try:
            target_path = self._resolve_safe_path(storage_path_key)
            return target_path.is_file()
        except HTTPException:
            return False

    def get_absolute_path(self, storage_path_key: str) -> Path:
        return self._resolve_safe_path(storage_path_key)


# Global storage provider instance
_default_storage_provider: Optional[StorageProvider] = None


def get_storage_provider() -> StorageProvider:
    """Dependency / accessor for the active storage provider."""
    global _default_storage_provider
    if _default_storage_provider is None:
        _default_storage_provider = LocalStorageProvider()
    return _default_storage_provider
