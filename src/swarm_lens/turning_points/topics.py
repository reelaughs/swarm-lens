"""Separate deterministic TF-IDF/NMF representations for chat and intentions."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import joblib
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

from .config import TopicModelConfig


@dataclass
class TopicRepresentation:
    modality: str
    weights_by_id: dict[str, np.ndarray]
    labels: list[str]
    metadata: dict[str, Any]


def _atomic_joblib(value: Any, path: Path) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        joblib.dump(value, temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _fit_one(
    rows: Sequence[Mapping[str, Any]],
    *,
    modality: str,
    text_field: str,
    config: TopicModelConfig,
    random_seed: int,
    cache_dir: Path,
) -> TopicRepresentation:
    usable = [row for row in rows if isinstance(row.get(text_field), str) and row[text_field].strip()]
    if len(usable) < config.n_components:
        raise ValueError(f"{modality} has only {len(usable)} usable documents for {config.n_components} components")
    texts = [row[text_field] for row in usable]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        stop_words="english",
        ngram_range=(config.ngram_min, config.ngram_max),
        min_df=config.min_df,
        max_df=config.max_df,
        max_features=config.max_features,
        sublinear_tf=True,
        norm="l2",
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9_-]{1,}\b",
    )
    matrix = vectorizer.fit_transform(texts)
    if matrix.shape[1] < config.n_components:
        raise ValueError(f"{modality} vocabulary has only {matrix.shape[1]} features")
    model = NMF(
        n_components=config.n_components,
        init="nndsvda",
        solver="cd",
        beta_loss="frobenius",
        max_iter=config.max_iter,
        random_state=random_seed,
    )
    document_weights = model.fit_transform(matrix)
    sums = document_weights.sum(axis=1)
    normalized = np.divide(
        document_weights,
        sums[:, None],
        out=np.zeros_like(document_weights),
        where=sums[:, None] > 0,
    )
    weights_by_id = {
        row["canonical_event_id"]: normalized[index]
        for index, row in enumerate(usable)
        if sums[index] > 0
    }
    terms = np.asarray(vectorizer.get_feature_names_out())
    labels = []
    for index, component in enumerate(model.components_):
        top_indices = np.argsort(component)[::-1][: config.top_terms]
        labels.append(f"{modality[0].upper()}{index + 1:02d}: " + ", ".join(terms[top_indices]))
    metadata = {
        "modality": modality,
        "documents_total": len(rows),
        "documents_with_text": len(usable),
        "documents_with_nonzero_topics": len(weights_by_id),
        "vocabulary_size": int(matrix.shape[1]),
        "n_components": config.n_components,
        "reconstruction_error": float(model.reconstruction_err_),
        "n_iter": int(model.n_iter_),
        "config": asdict(config),
    }
    _atomic_joblib(vectorizer, cache_dir / f"{modality}_vectorizer.joblib")
    _atomic_joblib(model, cache_dir / f"{modality}_nmf.joblib")
    return TopicRepresentation(modality, weights_by_id, labels, metadata)


def fit_or_load_topics(
    rows: Sequence[Mapping[str, Any]],
    *,
    communication_config: TopicModelConfig,
    intention_config: TopicModelConfig,
    random_seed: int,
    cache_dir: Path,
    cache_identity: dict[str, str],
) -> tuple[TopicRepresentation, TopicRepresentation, bool]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = cache_dir / "metadata.json"
    features_path = cache_dir / "topic_features.parquet"
    labels_path = cache_dir / "topic_labels.json"
    if metadata_path.is_file() and features_path.is_file() and labels_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("cache_identity") == cache_identity:
            feature_rows = pq.read_table(features_path).to_pylist()
            labels = json.loads(labels_path.read_text(encoding="utf-8"))
            by_modality: dict[str, dict[str, np.ndarray]] = {"communication": {}, "intention": {}}
            for row in feature_rows:
                by_modality[row["modality"]][row["canonical_event_id"]] = np.asarray(row["weights"], dtype=float)
            return (
                TopicRepresentation("communication", by_modality["communication"], labels["communication"], metadata["communication"]),
                TopicRepresentation("intention", by_modality["intention"], labels["intention"], metadata["intention"]),
                True,
            )

    chat_rows = [row for row in rows if row["event_kind"] == "chat_message" and row.get("speaker_type") == "agent"]
    session_rows = [row for row in rows if row["event_kind"] == "computer_use_session_goal"]
    communication = _fit_one(
        chat_rows,
        modality="communication",
        text_field="chat_content",
        config=communication_config,
        random_seed=random_seed,
        cache_dir=cache_dir,
    )
    intention = _fit_one(
        session_rows,
        modality="intention",
        text_field="session_goal",
        config=intention_config,
        random_seed=random_seed,
        cache_dir=cache_dir,
    )
    feature_rows = []
    for representation in (communication, intention):
        for canonical_id, weights in representation.weights_by_id.items():
            feature_rows.append(
                {"modality": representation.modality, "canonical_event_id": canonical_id, "weights": weights.tolist()}
            )
    pq.write_table(pa.Table.from_pylist(feature_rows), features_path, compression="zstd")
    labels_path.write_text(
        json.dumps({"communication": communication.labels, "intention": intention.labels}, indent=2),
        encoding="utf-8",
    )
    metadata = {
        "cache_identity": cache_identity,
        "communication": communication.metadata,
        "intention": intention.metadata,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return communication, intention, False
