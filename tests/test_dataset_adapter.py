from __future__ import annotations

import io
import gzip
import zipfile
from pathlib import Path

import pytest

from swarm_lens.datasets.ai_village import AIVillageAdapter
from swarm_lens.datasets.secure_upload import (
    BundleValidationError,
    UploadLimits,
    install_zip_bundle,
    stage_upload,
)

from upload_fixtures import make_ai_village_raw, zip_raw


ROOT = Path(__file__).resolve().parents[1]


def adapter() -> AIVillageAdapter:
    return AIVillageAdapter(ROOT / "configs" / "turning_points.toml")


def install(path: Path, uploads: Path, limits: UploadLimits | None = None):
    limits = limits or UploadLimits()
    with path.open("rb") as stream:
        staged = stage_upload(
            stream,
            dataset_id="ds_test",
            uploads_root=uploads,
            limits=limits,
        )
    return install_zip_bundle(
        staged,
        uploads_root=uploads,
        limits=limits,
        validate_extracted=adapter().inspect,
    )


def test_valid_bundle_promotes_only_after_inspection_and_discovers_scopes(tmp_path: Path) -> None:
    raw = make_ai_village_raw(tmp_path)
    archive = zip_raw(raw, tmp_path / "bundle.zip")
    permanent, inspection = install(archive, tmp_path / "uploads")
    assert permanent == tmp_path / "uploads" / "ds_test"
    assert (permanent / "raw" / "events.jsonl.gz").is_file()
    by_id = {scope.scope_id: scope for scope in inspection.scopes}
    assert by_id["goal-runnable"].runnable
    assert not by_id["goal-underpowered"].runnable
    assert "usable agent chat" in by_id["goal-underpowered"].blocking_reason
    assert not by_id["goal-open"].runnable
    assert "still open" in by_id["goal-open"].blocking_reason


def test_missing_required_member_is_rejected_without_promotion(tmp_path: Path) -> None:
    raw = make_ai_village_raw(tmp_path)
    (raw / "events.jsonl.gz").unlink()
    archive = zip_raw(raw, tmp_path / "bundle.zip")
    with pytest.raises(BundleValidationError, match="missing required"):
        install(archive, tmp_path / "uploads")
    assert not (tmp_path / "uploads" / "ds_test").exists()


def test_malformed_jsonl_is_rejected_without_promotion(tmp_path: Path) -> None:
    raw = make_ai_village_raw(tmp_path)
    with gzip.open(raw / "agents.jsonl.gz", "wb") as stream:
        stream.write(b"{this is not valid json}\n")
    archive = zip_raw(raw, tmp_path / "bundle.zip")
    with pytest.raises(Exception, match="invalid JSON"):
        install(archive, tmp_path / "uploads")
    assert not (tmp_path / "uploads" / "ds_test").exists()


@pytest.mark.parametrize("member", ["../events.jsonl.gz", "/events.jsonl.gz", "nested/events.jsonl.gz"])
def test_unsafe_zip_member_paths_are_rejected(tmp_path: Path, member: str) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as value:
        value.writestr(member, b"x")
    with archive.open("rb") as stream:
        staged = stage_upload(
            stream,
            dataset_id="ds_test",
            uploads_root=tmp_path / "uploads",
            limits=UploadLimits(),
        )
    with pytest.raises(BundleValidationError, match="unsafe or nested"):
        install_zip_bundle(
            staged,
            uploads_root=tmp_path / "uploads",
            limits=UploadLimits(),
            validate_extracted=adapter().inspect,
        )


def test_compressed_and_nested_decompressed_limits_are_enforced(tmp_path: Path) -> None:
    raw = make_ai_village_raw(tmp_path)
    archive = zip_raw(raw, tmp_path / "bundle.zip")
    with archive.open("rb") as stream:
        with pytest.raises(BundleValidationError, match="compressed limit"):
            stage_upload(
                stream,
                dataset_id="ds_small",
                uploads_root=tmp_path / "small",
                limits=UploadLimits(max_upload_bytes=16),
            )
    tiny = UploadLimits(max_total_gzip_uncompressed_bytes=128)
    with pytest.raises(BundleValidationError, match="gzip members exceed"):
        install(archive, tmp_path / "uploads", tiny)
