"""
Filesystem helpers implementing the Pointer & Receipt Pattern.

Large artifacts (specs, intermediate pass outputs, receipts) live on disk; only URIs and SHA-256 digests
travel between pipeline stages. The artifacts root is resolved at call time so tests (and CI) can redirect it
with ``MODERNIZATION_ARTIFACTS_DIR``.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Union

PathLike = Union[str, "os.PathLike[str]"]


def artifacts_root() -> Path:
    return Path(os.getenv("MODERNIZATION_ARTIFACTS_DIR", "artifacts"))


def receipts_dir() -> Path:
    return artifacts_root() / "receipts"


def specs_dir() -> Path:
    return artifacts_root() / "generated_specs"


def target_code_dir() -> Path:
    return artifacts_root() / "target_code"


def issues_dir() -> Path:
    return artifacts_root() / "issues"


def architecture_profiles_dir() -> Path:
    return artifacts_root() / "architecture_profiles"


def sha256_file(path: PathLike) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_text(path: PathLike, text: str) -> Path:
    """Write via temp file + ``os.replace`` so readers never observe a half-written artifact/receipt."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target


def resolve_artifact_uri(uri: str) -> Path:
    """
    Resolve an ``ArtifactPointer.uri`` to a local file.

    Absolute URIs are used as-is. Relative URIs are tried against the cwd and then against the parent of the
    artifacts root (so ``artifacts/generated_specs/x.json`` resolves from any working directory when
    ``MODERNIZATION_ARTIFACTS_DIR`` is set).
    """
    candidate = Path(uri)
    if candidate.is_absolute():
        return candidate
    for base in (Path.cwd(), artifacts_root().resolve().parent):
        resolved = base / candidate
        if resolved.exists():
            return resolved
    return Path.cwd() / candidate
