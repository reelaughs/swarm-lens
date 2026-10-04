# SwarmLens

Stage 1 provides a restartable, episode-generic ingestion and validation layer
for the AI Village dataset. It deliberately does not implement topic modeling,
embeddings, changepoint detection, an LLM pipeline, or a UI.

Create a local environment and install the package with its test dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Build an episode by exact village-goal text:

```powershell
.\.venv\Scripts\python.exe scripts/build_episode.py --goal "Perform novel research!"
```

Or select the same authoritative interval by goal UUID:

```powershell
.\.venv\Scripts\python.exe scripts/build_episode.py --goal-id ee7a006d-c196-4824-b804-ead8e9632228
```

Outputs are written to:

```text
data/processed/episodes/<safe-goal-slug>/events.parquet
outputs/episodes/<safe-goal-slug>/ingestion_validation.md
```

The goal text and timestamps are always resolved from
`data/raw/village_goals.jsonl.gz`; the command contains no episode-specific
timestamps or ingestion branches.

## Stage 2: population-level turning points

Stage 2 reads but never modifies a canonical episode dataset. Its parameters
are centralized in `configs/turning_points.toml`.

```powershell
.\.venv\Scripts\python.exe scripts/detect_turning_points.py `
  --episode run-your-own-youtube-channel
```

Fitted TF-IDF/NMF models and derived window features are cached under
`data/interim/episodes/<episode>/turning_points/`. Reports, tables, evidence
IDs, and diagnostic plots are written under
`outputs/episodes/<episode>/turning_points/`.

Export context packets for manual adjudication without rerunning the detector:

```powershell
.\.venv\Scripts\python.exe scripts/export_candidate_context.py `
  --episode run-your-own-youtube-channel `
  --before-minutes 90 `
  --after-minutes 90
```

Build the compact deterministic orientation briefs from those full packets and
the cached NMF document weights:

```powershell
.\.venv\Scripts\python.exe scripts/export_candidate_brief.py `
  --episode run-your-own-youtube-channel
```
