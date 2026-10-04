"""Secure staging and extraction for the one supported AI Village ZIP format."""

from __future__ import annotations

import hashlib
import gzip
import os
import shutil
import stat
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Callable, TypeVar


REQUIRED_MEMBERS = frozenset(
    {
        "agents.jsonl.gz",
        "village_goals.jsonl.gz",
        "agent_goals.jsonl.gz",
        "chat_messages.jsonl.gz",
        "computer_use_sessions.jsonl.gz",
        "events.jsonl.gz",
        "CHANGELOG.md",
    }
)
OPTIONAL_MEMBERS = frozenset({"SCHEMA.md"})
ALLOWED_MEMBERS = REQUIRED_MEMBERS | OPTIONAL_MEMBERS


class BundleValidationError(ValueError):
    """Raised before an uploaded bundle is promoted to permanent storage."""


@dataclass(frozen=True)
class UploadLimits:
    # The published AI Village bundle is about 421 MiB compressed and 1.3 GiB
    # uncompressed for the seven required files.
    max_upload_bytes: int = 768 * 1024 * 1024
    max_member_count: int = 16
    max_total_compressed_bytes: int = 768 * 1024 * 1024
    max_total_uncompressed_bytes: int = 3 * 1024 * 1024 * 1024
    max_member_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024
    max_compression_ratio: float = 250.0
    max_total_gzip_uncompressed_bytes: int = 3 * 1024 * 1024 * 1024
    max_gzip_member_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024
    max_gzip_compression_ratio: float = 250.0
    max_jsonl_line_bytes: int = 16 * 1024 * 1024
    copy_chunk_bytes: int = 1024 * 1024


@dataclass(frozen=True)
class StagedUpload:
    dataset_id: str
    staging_dir: Path
    archive_path: Path
    compressed_bytes: int
    archive_sha256: str


T = TypeVar("T")


def stage_upload(
    stream: BinaryIO,
    *,
    dataset_id: str,
    uploads_root: Path,
    limits: UploadLimits,
) -> StagedUpload:
    """Copy an upload to an isolated staging directory with a hard byte cap."""

    uploads_root = Path(uploads_root)
    staging_root = uploads_root / ".staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    staging_dir = staging_root / f"{dataset_id}-{uuid.uuid4().hex}"
    staging_dir.mkdir(parents=False, exist_ok=False)
    archive_path = staging_dir / "upload.zip"
    digest = hashlib.sha256()
    total = 0
    try:
        with archive_path.open("wb") as target:
            while chunk := stream.read(limits.copy_chunk_bytes):
                total += len(chunk)
                if total > limits.max_upload_bytes:
                    raise BundleValidationError(
                        f"upload exceeds compressed limit of {limits.max_upload_bytes} bytes"
                    )
                digest.update(chunk)
                target.write(chunk)
        if total == 0:
            raise BundleValidationError("uploaded ZIP is empty")
        return StagedUpload(dataset_id, staging_dir, archive_path, total, digest.hexdigest())
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def _validated_members(archive: zipfile.ZipFile, limits: UploadLimits) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > limits.max_member_count:
        raise BundleValidationError(
            f"ZIP contains {len(members)} members; maximum is {limits.max_member_count}"
        )
    seen: set[str] = set()
    files: list[zipfile.ZipInfo] = []
    compressed_total = 0
    uncompressed_total = 0
    for member in members:
        raw_name = member.filename.replace("\\", "/")
        path = PurePosixPath(raw_name)
        if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
            raise BundleValidationError(f"unsafe or nested ZIP member path: {member.filename!r}")
        name = path.name
        if member.is_dir():
            raise BundleValidationError(f"directory members are not supported: {member.filename!r}")
        if name in seen:
            raise BundleValidationError(f"duplicate ZIP member path: {name!r}")
        seen.add(name)
        if name not in ALLOWED_MEMBERS:
            raise BundleValidationError(f"unexpected ZIP member: {name!r}")
        if member.flag_bits & 0x1:
            raise BundleValidationError(f"encrypted ZIP member is not supported: {name!r}")
        unix_mode = (member.external_attr >> 16) & 0xFFFF
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise BundleValidationError(f"symbolic links are not supported: {name!r}")
        if member.file_size > limits.max_member_uncompressed_bytes:
            raise BundleValidationError(f"ZIP member {name!r} exceeds its uncompressed size limit")
        ratio = member.file_size / max(member.compress_size, 1)
        if ratio > limits.max_compression_ratio:
            raise BundleValidationError(
                f"ZIP member {name!r} has suspicious compression ratio {ratio:.1f}"
            )
        compressed_total += member.compress_size
        uncompressed_total += member.file_size
        files.append(member)
    missing = sorted(REQUIRED_MEMBERS - seen)
    if missing:
        raise BundleValidationError(f"ZIP is missing required members: {missing}")
    if compressed_total > limits.max_total_compressed_bytes:
        raise BundleValidationError("ZIP compressed payload exceeds configured limit")
    if uncompressed_total > limits.max_total_uncompressed_bytes:
        raise BundleValidationError("ZIP uncompressed payload exceeds configured limit")
    return files


def install_zip_bundle(
    staged: StagedUpload,
    *,
    uploads_root: Path,
    limits: UploadLimits,
    validate_extracted: Callable[[Path], T],
) -> tuple[Path, T]:
    """Validate/extract a ZIP, then atomically promote it after semantic inspection."""

    extracted = staged.staging_dir / "extracted"
    extracted.mkdir()
    try:
        try:
            archive = zipfile.ZipFile(staged.archive_path)
        except zipfile.BadZipFile as error:
            raise BundleValidationError("upload is not a valid ZIP archive") from error
        with archive:
            members = _validated_members(archive, limits)
            total_written = 0
            for member in members:
                destination = extracted / member.filename
                written = 0
                with archive.open(member, "r") as source, destination.open("xb") as target:
                    while chunk := source.read(limits.copy_chunk_bytes):
                        written += len(chunk)
                        total_written += len(chunk)
                        if written > limits.max_member_uncompressed_bytes:
                            raise BundleValidationError(
                                f"ZIP member {member.filename!r} expanded beyond its limit"
                            )
                        if total_written > limits.max_total_uncompressed_bytes:
                            raise BundleValidationError("ZIP expanded beyond the total configured limit")
                        target.write(chunk)
                if written != member.file_size:
                    raise BundleValidationError(
                        f"ZIP member {member.filename!r} size disagrees with its directory entry"
                    )

        _validate_nested_gzip(extracted, limits)
        inspection = validate_extracted(extracted)
        permanent = Path(uploads_root) / staged.dataset_id
        if permanent.exists():
            raise BundleValidationError(f"generated dataset directory already exists: {staged.dataset_id}")
        promotion = staged.staging_dir / "promotion"
        promotion.mkdir()
        os.replace(extracted, promotion / "raw")
        os.replace(staged.archive_path, promotion / "upload.zip")
        os.replace(promotion, permanent)
        shutil.rmtree(staged.staging_dir, ignore_errors=True)
        return permanent, inspection
    except Exception:
        shutil.rmtree(staged.staging_dir, ignore_errors=True)
        raise


def _validate_nested_gzip(raw_dir: Path, limits: UploadLimits) -> None:
    """Bound the second decompression layer before JSON parsing begins."""

    total = 0
    for name in sorted(value for value in REQUIRED_MEMBERS if value.endswith(".jsonl.gz")):
        path = raw_dir / name
        expanded = 0
        try:
            with gzip.open(path, "rb") as stream:
                while line := stream.readline(limits.max_jsonl_line_bytes + 1):
                    if len(line) > limits.max_jsonl_line_bytes:
                        raise BundleValidationError(
                            f"{name} contains a JSONL record larger than the configured line limit"
                        )
                    expanded += len(line)
                    total += len(line)
                    if expanded > limits.max_gzip_member_uncompressed_bytes:
                        raise BundleValidationError(f"{name} exceeds its gzip expansion limit")
                    if total > limits.max_total_gzip_uncompressed_bytes:
                        raise BundleValidationError("gzip members exceed the total expansion limit")
        except (gzip.BadGzipFile, EOFError, OSError) as error:
            raise BundleValidationError(f"{name} is not a valid gzip stream") from error
        ratio = expanded / max(path.stat().st_size, 1)
        if ratio > limits.max_gzip_compression_ratio:
            raise BundleValidationError(
                f"{name} has suspicious gzip compression ratio {ratio:.1f}"
            )
