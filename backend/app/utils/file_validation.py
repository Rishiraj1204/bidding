import os
import re
from pathlib import Path
from typing import Optional, Set, Tuple
from fastapi import HTTPException, UploadFile, status
from backend.app.core.config import settings

# Allowed MIME types for tender and bid document submissions
ALLOWED_MIME_TYPES: Set[str] = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/pjpeg",
    "image/tiff",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

# Allowed file extensions
ALLOWED_EXTENSIONS: Set[str] = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".webp",
    ".doc",
    ".docx",
    ".txt",
}

# Explicitly prohibited dangerous extensions
DISALLOWED_EXTENSIONS: Set[str] = {
    ".exe", ".bat", ".cmd", ".sh", ".bash", ".ps1", ".vbs", ".js", ".mjs",
    ".py", ".pyc", ".pyd", ".bin", ".msi", ".dll", ".so", ".dylib", ".com",
    ".scr", ".jar", ".war", ".php", ".phtml", ".asp", ".aspx", ".jsp",
    ".cgi", ".pl", ".reg", ".app", ".vb", ".wsf", ".action"
}

# Magic bytes dictionary for file header verification
MAGIC_BYTES_SIGNATURES = {
    "application/pdf": [b"%PDF"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/pjpeg": [b"\xff\xd8\xff"],
    "image/tiff": [b"II*\x00", b"MM\x00*"],
    "image/webp": [b"RIFF"],
    # DOCX and modern Office formats are ZIP archives starting with PK
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [b"PK\x03\x04"],
    # Legacy Word format
    "application/msword": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
}


def sanitize_filename(filename: Optional[str]) -> str:
    """
    Sanitize incoming client filename, removing path traversal characters,
    null bytes, and dangerous characters.
    """
    if not filename:
        return "document.pdf"
    
    # Strip null bytes and control chars
    clean_name = filename.replace("\x00", "").strip()
    
    # Extract only the base name (prevents directory traversal e.g. ../../)
    clean_name = Path(clean_name).name
    
    # Remove problematic characters, keep alphanumeric, dots, underscores, dashes, spaces
    clean_name = re.sub(r"[^\w\s\.\-]", "", clean_name).strip()
    
    if not clean_name or clean_name.startswith("."):
        clean_name = f"document_{clean_name}" if clean_name else "document.pdf"
        
    return clean_name[:255]


def validate_file_security(
    content: bytes,
    filename: str,
    content_type: Optional[str] = None,
    max_size_bytes: Optional[int] = None,
) -> Tuple[str, str, int]:
    """
    Perform deep security validation on file content, extension, MIME type,
    and magic bytes.
    
    Returns: (sanitized_filename, validated_mime_type, file_size)
    Raises HTTPException if file fails any validation check.
    """
    file_size = len(content)
    max_size = max_size_bytes or settings.MAX_UPLOAD_SIZE_BYTES

    # 1. Size Validation
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        status_code = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413)
        raise HTTPException(
            status_code=status_code,
            detail=f"File size ({actual_mb:.2f} MB) exceeds maximum allowed limit of {max_mb:.2f} MB.",
        )

    # 2. Filename and Extension Validation
    clean_filename = sanitize_filename(filename)
    ext = Path(clean_filename).suffix.lower()

    if ext in DISALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '{ext}' is prohibited due to security policies.",
        )

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 3. MIME Type Validation
    normalized_mime = (content_type or "").lower().split(";")[0].strip()
    if not normalized_mime or normalized_mime == "application/octet-stream":
        # Fallback to extension-based inference
        if ext == ".pdf":
            normalized_mime = "application/pdf"
        elif ext in {".png"}:
            normalized_mime = "image/png"
        elif ext in {".jpg", ".jpeg"}:
            normalized_mime = "image/jpeg"
        elif ext in {".tif", ".tiff"}:
            normalized_mime = "image/tiff"
        elif ext in {".webp"}:
            normalized_mime = "image/webp"
        elif ext == ".docx":
            normalized_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif ext == ".doc":
            normalized_mime = "application/msword"
        elif ext == ".txt":
            normalized_mime = "text/plain"

    if normalized_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MIME type '{normalized_mime}' is not permitted.",
        )

    # 4. Magic Bytes Content Header Validation
    if normalized_mime in MAGIC_BYTES_SIGNATURES:
        signatures = MAGIC_BYTES_SIGNATURES[normalized_mime]
        matches = any(content.startswith(sig) for sig in signatures)
        if not matches:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File content header does not match declared MIME type '{normalized_mime}'. File may be corrupt or disguised.",
            )

    return clean_filename, normalized_mime, file_size
