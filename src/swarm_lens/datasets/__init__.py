"""Minimal dataset-adapter boundary for reusable SwarmLens ingestion."""

from .ai_village import AIVillageAdapter
from .base import DatasetAdapter, DatasetInspection, ScopeDescriptor
from .secure_upload import UploadLimits, install_zip_bundle, stage_upload

__all__ = [
    "AIVillageAdapter",
    "DatasetAdapter",
    "DatasetInspection",
    "ScopeDescriptor",
    "UploadLimits",
    "install_zip_bundle",
    "stage_upload",
]
