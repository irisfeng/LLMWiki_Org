"""LibreOffice-based office-to-PDF conversion for inline preview.

Runs `libreoffice --headless --convert-to pdf` out-of-process and caches
the result next to the original upload as `{original}.preview.pdf`. The
original file is never replaced — `/download` still returns the .pptx.

Best-effort: all failures are logged and return None, so a broken
conversion never marks the source ingest as failed (preview simply 404s
until the user clicks "重新解析").
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

# Narrow on purpose: .docx is rendered client-side by mammoth (faster, no
# LibreOffice cost), and PDFs are served as-is.
CONVERTIBLE_EXTS = {".ppt", ".pptx", ".doc"}

# LibreOffice timeout — a reasonable PPT takes 3-10s; large decks on a
# 2.8GB VPS can hit 30-60s. Cap at 2 minutes so a pathological deck can't
# pin a Celery worker slot forever.
DEFAULT_TIMEOUT_SEC = 120


def preview_pdf_path(file_path: str) -> str:
    return file_path + ".preview.pdf"


def should_convert(file_path: str) -> bool:
    return os.path.splitext(file_path)[1].lower() in CONVERTIBLE_EXTS


def convert_to_preview_pdf(
    file_path: str, timeout: int = DEFAULT_TIMEOUT_SEC
) -> str | None:
    """Convert a single office file to a cached preview PDF.

    Returns the destination path on success, None on any failure.
    """
    if not should_convert(file_path):
        return None
    if not os.path.exists(file_path):
        logger.warning("preview_pdf: source missing %s", file_path)
        return None

    dst = preview_pdf_path(file_path)

    # Use a throwaway temp dir for LibreOffice output + per-invocation
    # user profile. The user-profile isolation is required because Celery
    # workers run with -c 2 and a shared profile would lock-conflict under
    # concurrent conversions.
    with tempfile.TemporaryDirectory() as td:
        profile_dir = os.path.join(td, "lo-profile")
        cmd = [
            "libreoffice",
            f"-env:UserInstallation=file://{profile_dir}",
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            "--convert-to",
            "pdf",
            "--outdir",
            td,
            file_path,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired:
            logger.error("preview_pdf: libreoffice timed out on %s", file_path)
            return None
        except FileNotFoundError:
            logger.error(
                "preview_pdf: `libreoffice` binary not found — install libreoffice-core in the backend image"
            )
            return None

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", "replace")[:400]
            logger.error(
                "preview_pdf: libreoffice rc=%s on %s stderr=%s",
                result.returncode,
                file_path,
                stderr,
            )
            return None

        stem = os.path.splitext(os.path.basename(file_path))[0]
        produced = os.path.join(td, f"{stem}.pdf")
        if not os.path.exists(produced):
            logger.error(
                "preview_pdf: libreoffice reported success but produced no output for %s",
                file_path,
            )
            return None

        try:
            shutil.move(produced, dst)
        except OSError as e:
            logger.error("preview_pdf: failed to move to %s: %s", dst, e)
            return None

    logger.info("preview_pdf: converted %s -> %s", file_path, dst)
    return dst


def remove_preview_pdf(file_path: str) -> None:
    """Delete the cached preview PDF for file_path, if any. Silent on missing."""
    dst = preview_pdf_path(file_path)
    if os.path.exists(dst):
        try:
            os.remove(dst)
        except OSError as e:
            logger.warning("preview_pdf: failed to remove %s: %s", dst, e)
