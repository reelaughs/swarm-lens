# SwarmLens

**From agent events to an evidence-grounded incident map.**

SwarmLens is a retrospective investigation tool for multi-agent AI systems.

It asks, "What changed the swarm?"

Instead of asking an investigator to read thousands of agent messages and actions, SwarmLens identifies candidate behavioral turning points, reconstructs the evidence around them, and produces auditable, source-grounded hypotheses about what may have changed.

Built for the *AI Swarm Dynamics Hackathon*

Demo video can be accessed through https://app.trupeer.ai/view/OjtoVIba7/swarm-lens
Prototype here: https://reelaughs.github.io/swarm-lens (Dataset upload is available when running SwarmLens locally. This hosted demo uses precomputed investigations.) 

---

## Why SwarmLens?

When large populations of autonomous agents interact, the bottleneck is not simply token processing. It is *sensemaking*.

An investigator needs to understand:

- What is going on?
- What changed?
- When did the collective begin behaving differently?
- Which events or interactions may have contributed?
- What evidence supports that interpretation?
- What might the current explanation be missing?

Search helps when we already know what to look for.

But incident investigation also has an **unknown-unknown problem**: important behaviors may not be known in advance, so they cannot simply be queried with a predefined classifier or search term.

SwarmLens therefore treats swarm investigation as a problem of progressive forensic compression: Reduce a large stream of agent activity to a small number of things a human should inspect, while preserving a path back to the underlying evidence.

---

## What the prototype does

The repository includes two precomputed AI Village investigations:

| Village goal | Authoritative interval | Canonical records | Turning-point candidates |
| --- | --- | ---: | ---: |
| `Perform novel research!` | 11–18 May 2026 | 6,916 | 5 |
| `Connect your worlds into a 3D universe!` | 4–11 May 2026 | 5,959 | 5 |

It also supports reusable local upload and runtime analysis for an AI Village-compatible ZIP bundle.

SwarmLens then:

1. **Canonicalizes episode data** into a consistent event representation.
2. **Detects candidate behavioral transitions** using deterministic analytical signals.
3. **Ranks candidates by behavioral change**, not by claimed importance.
4. **Reconstructs a bounded forensic neighborhood** around each candidate.
5. **Supplies only that bounded evidence to the language model.**
6. **Generates a source-grounded interpretation** of the candidate.
7. **Validates the interpretation locally**, including checking that referenced evidence belongs to the supplied evidence bundle.
8. **Packages the result into an investigator-facing incident map.**

The goal is not to declare that a candidate caused a swarm-level change. Rather, the model interpretation remains a hypothesis for investigation, not an assertion of causality or importance. The final judgement is left up to the user. 

---

## Pipeline

```text
Raw AI Village / uploaded data
        ↓
Canonical event layer
        ↓
Deterministic behavioral-change detection
        ↓
Ranked turning-point candidates
        ↓
Bounded forensic evidence reconstruction
        ↓
Evidence-constrained LLM interpretation
        ↓
Local validation
        ↓
Investigator-facing incident map
        ↓
Raw supporting evidence
```

## Investigation workflow

The investigator can move through:

> overview → anomaly → hypothesis → evidence → revised overview

rather than simply asking an LLM to summarize an entire corpus.

## Why separate detection from interpretation?

SwarmLens deliberately separates two tasks.

### Detection

A deterministic analysis layer identifies where swarm behavior appears to change, without requiring the investigator to know in advance what to search for.

### Interpretation

Only after a candidate turning point has been reconstructed does the language model receive a bounded evidence bundle and propose an interpretation.

Evidence references must come from that candidate's allowlisted evidence bundle, and model outputs are locally validated before acceptance.

The interpretation is therefore a hypothesis for investigation, not an assertion of causality, importance, harmfulness, or collusion.

## Validation /= a rubber stamp

In the final runtime interpretation pass, all five detected candidates ultimately produced validated interpretations.

One initial interpretation was rejected because it claimed persistent role specialization without sufficient provenance-backed evidence. SwarmLens requested a repair rather than accepting the unsupported claim.

AI interpretation is useful, but it is not automatically trusted.

## Incident map

SwarmLens presents candidate turning points on a temporal incident map. Investigators can inspect:

- where a candidate occurs in the episode;
- the behavioral-change signals associated with it;
- its bounded forensic neighborhood;
- the proposed interpretation;
- confidence and uncertainty;
- and the underlying source evidence.

Rank is not the same thing as importance. A highly ranked candidate means the detector observed comparatively strong behavioral change. It does not establish that the event was the most causally or substantively important event in the episode.

## Design principle: epistemic compression

Again, the goal is not merely to summarize logs but epistemic compression; preserve the small fraction of information needed to understand an incident without hiding how the resulting story was constructed.

SwarmLens aims to reduce investigative cognitive burden without replacing the underlying evidence with an opaque AI-generated narrative.

## Current scope

This is a weekend research prototype, not a complete swarm-forensics system.

The repository includes two precomputed AI Village examples and supports reusable local upload/runtime analysis through the current AI Village ZIP adapter.

The current system focuses on:

- retrospective analysis;
- candidate behavioral turning points;
- deterministic ranking;
- bounded evidence reconstruction;
- evidence-grounded interpretation;
- provenance-aware validation;
- and investigator-facing presentation.

It does not establish:

- causal relationships between events;
- whether a detected transition is harmful or benign;
- whether a candidate represents collusion;
- complete recovery of every important event;
- or real-time swarm monitoring.

## Research question

Can behavior-aware incident reconstruction surface important turning points in a multi-agent incident while requiring substantially less human review than reading or flatly summarizing the underlying activity?

Natural follow-up evaluation would measure:

- recovery of independently documented incident-critical events;
- unsupported or misleading interpretations;
- number of raw records a human must inspect;
- time-to-understanding;
- and whether investigators discover important events they did not know to search for in advance.

## Running locally

SwarmLens requires Python 3.11 or newer and Node.js with npm.

Install the Python package and frontend dependencies from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
cd frontend
npm install
cd ..
```

Start the local analysis API in one terminal:

```powershell
.\.venv\Scripts\python.exe scripts\serve.py
```

Start the frontend in another terminal:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173/` to explore the precomputed investigations or upload a supported AI Village ZIP bundle.

Precomputed investigations do not require an API key. To approve evidence-constrained model interpretation for a new runtime analysis, copy `.env.example` to `.env` and configure `OPENAI_API_KEY`. The local `.env` file is ignored by Git.

The frontend uses History API routes. Production hosting must rewrite unknown application paths to `index.html` so direct investigation URLs continue to work.



The hackathon asks what tools we would wish we had when investigating the next large-scale autonomous-agent incident.

SwarmLens explores one answer: Don't show the investigator everything. Show them what changed, give them what they need to know in a focused manner in order to help them verify why and leave them with the power and clarity for the final conclusions. 
