# Population-level turning points: Connect your worlds into a 3D universe!

This calibration report ranks changes in collective behavior. It does not assign causal triggers or social-process labels.

## Episode and detector

- Goal ID: `e05585ff-4d5d-4595-b858-cfee8e8f380a`
- Authoritative interval: `[2026-05-04T16:03:38.616000+00:00, 2026-05-11T07:47:04.725000+00:00)` UTC
- Configuration fingerprint: `172e24df5adeb504a70d263632e34ef8491f07f48aeca2da7f27511074a930fe`
- Topic cache reused: `False`
- Minimum valid comparisons for reliable standardization: `10`
- Minimum peak separation: `120` clock minutes
- Participation and action-type signals are complementary views of the same high-level-event stream; they are not statistically independent measurements.

## Windowing diagnostics

| Window | Active / total | Overall-eligible | Adjacent comparisons | Valid aggregates | Inactive gaps | Inactive minutes | Max gap | Reliable |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 30m | 50 / 320 | 40 | 35 | 35 | 6 | 8083 | 3497 | True |
| 60m | 30 / 160 | 20 | 15 | 15 | 5 | 7787 | 3467 | True |
| 90m | 20 / 108 | 15 | 10 | 10 | 6 | 7783 | 3437 | True |

Recommended initial window size: **30 minutes**.
The recommendation rule chooses the smallest profiled window size with enough valid aggregate comparisons, preserving the highest supported temporal resolution.

## Topic representations

- **Communication**: 1731 usable documents, 5000 TF-IDF features, 8 NMF components, reconstruction error 39.265.
- **Intention**: 1110 usable documents, 5000 TF-IDF features, 8 NMF components, reconstruction error 30.318.

## Standardization diagnostics

### 30-minute windows

| Component | Valid raw divergences | Center | Scale | Method | Reliable |
| --- | ---: | ---: | ---: | --- | --- |
| communication | 35 | 0.034 | 0.022 | mad | True |
| intention | 35 | 0.017 | 0.008 | mad | True |
| participation | 35 | 0.060 | 0.026 | mad | True |
| action type | 35 | 0.016 | 0.019 | mad | True |

### 60-minute windows

| Component | Valid raw divergences | Center | Scale | Method | Reliable |
| --- | ---: | ---: | ---: | --- | --- |
| communication | 15 | 0.030 | 0.021 | mad | True |
| intention | 15 | 0.008 | 0.005 | mad | True |
| participation | 15 | 0.034 | 0.014 | mad | True |
| action type | 15 | 0.009 | 0.005 | mad | True |

### 90-minute windows

| Component | Valid raw divergences | Center | Scale | Method | Reliable |
| --- | ---: | ---: | ---: | --- | --- |
| communication | 10 | 0.035 | 0.031 | mad | True |
| intention | 10 | 0.011 | 0.008 | mad | True |
| participation | 10 | 0.024 | 0.009 | mad | True |
| action type | 10 | 0.009 | 0.009 | mad | True |

## Top candidate turning points

### 1. 2026-05-07T20:30:00+00:00

- Aggregate score: **3.388**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 91 → 71
- Before/after agent chats: 60 → 40
- Before/after session goals: 27 → 30
- Raw JS divergences: communication 0.213, intention 0.045, participation 0.111, action type 0.017
- Standardized components: communication 8.081, intention 3.478, participation 1.989, action type 0.006

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C01: pr, gemini, sights, claude, merge, haiku, batch, ready | 0.481 | 0.070 | -0.410 |
| C05: main, js, main js, origin, origin main, check, unique, current | 0.183 | 0.365 | 0.182 |
| C03: atlas, hud, discovered, cosmic, build, live, header, directory | 0.049 | 0.174 | 0.124 |
| C07: claiming, batch, computational, astrophysics, computational astrophysics, creating, slot, merged | 0.134 | 0.056 | -0.079 |
| C08: chambers, https ai-village-agents, ai-village-agents github, github io, io, ai-village-agents, explore, github | 0.075 | 0.141 | 0.066 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I04: pr, batch, merge, merged, sights, pt, main, create | 0.480 | 0.266 | -0.214 |
| I08: atlas, directory, hub, build, anchorage, universe hub, confirm, teleport | 0.105 | 0.185 | 0.080 |
| I07: js, origin, main, main js, local, origin main, stale, fetch | 0.097 | 0.159 | 0.062 |
| I05: surge, philosophy, html, journey, station, deploy, sonnet-world, tmp sonnet-world | 0.077 | 0.110 | 0.033 |
| I02: permalinks, canonical, re-verify persistence, re-verify, exact prepared, provenance hud, canonical observatory, permalinks re-verify | 0.033 | 0.057 | 0.024 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| Claude Haiku 4.5 | 0.165 | 0.056 | -0.108 |
| GPT-5.2 | 0.022 | 0.113 | 0.091 |
| GPT-5.4 | 0.066 | 0.155 | 0.089 |
| Claude Opus 4.5 | 0.132 | 0.056 | -0.076 |
| Claude Sonnet 4.6 | 0.022 | 0.070 | 0.048 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| CONSOLIDATE | 0.297 | 0.423 | 0.126 |
| AGENT_TALK | 0.659 | 0.563 | -0.096 |
| PAUSE | 0.044 | 0.014 | -0.030 |
| ENTER_ROOM | 0.000 | 0.000 | 0.000 |
| REQUEST_GOOGLE_SIGN_IN | 0.000 | 0.000 | 0.000 |

### 2. 2026-05-07T17:30:00+00:00

- Aggregate score: **1.821**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 76 → 64
- Before/after agent chats: 43 → 39
- Before/after session goals: 21 → 25
- Raw JS divergences: communication 0.074, intention 0.030, participation 0.062, action type 0.087
- Standardized components: communication 1.813, intention 1.639, participation 0.077, action type 3.756

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C01: pr, gemini, sights, claude, merge, haiku, batch, ready | 0.153 | 0.351 | 0.198 |
| C02: secrets, golden, batches, garden, milestone, persistence, day, persistence garden | 0.083 | 0.012 | -0.071 |
| C07: claiming, batch, computational, astrophysics, computational astrophysics, creating, slot, merged | 0.050 | 0.105 | 0.055 |
| C04: stations, journeys, drift, https claude-sonnet-46-drift, surge sh, claude-sonnet-46-drift surge, claude-sonnet-46-drift, sh | 0.087 | 0.044 | -0.043 |
| C03: atlas, hud, discovered, cosmic, build, live, header, directory | 0.149 | 0.108 | -0.041 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I08: atlas, directory, hub, build, anchorage, universe hub, confirm, teleport | 0.070 | 0.167 | 0.097 |
| I04: pr, batch, merge, merged, sights, pt, main, create | 0.432 | 0.356 | -0.076 |
| I07: js, origin, main, main js, local, origin main, stale, fetch | 0.099 | 0.150 | 0.051 |
| I03: batches, golden, batch, secrets, committed, perfect, perfect record, record | 0.139 | 0.095 | -0.044 |
| I01: universe, worlds, features, cosmic, live, opus, automation, garden | 0.055 | 0.024 | -0.031 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| DeepSeek-V3.2 | 0.171 | 0.281 | 0.110 |
| GPT-5.5 | 0.118 | 0.016 | -0.103 |
| GPT-5.4 | 0.158 | 0.109 | -0.049 |
| GPT-5.2 | 0.092 | 0.125 | 0.033 |
| Claude Sonnet 4.6 | 0.053 | 0.031 | -0.021 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| PAUSE | 0.158 | 0.000 | -0.158 |
| CONSOLIDATE | 0.276 | 0.391 | 0.114 |
| AGENT_TALK | 0.566 | 0.609 | 0.044 |
| ENTER_ROOM | 0.000 | 0.000 | 0.000 |
| REQUEST_GOOGLE_SIGN_IN | 0.000 | 0.000 | 0.000 |

### 3. 2026-05-06T17:30:00+00:00

- Aggregate score: **1.253**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 67 → 61
- Before/after agent chats: 40 → 36
- Before/after session goals: 24 → 23
- Raw JS divergences: communication 0.055, intention 0.023, participation 0.142, action type 0.018
- Standardized components: communication 0.957, intention 0.811, participation 3.181, action type 0.062

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C03: atlas, hud, discovered, cosmic, build, live, header, directory | 0.409 | 0.250 | -0.159 |
| C01: pr, gemini, sights, claude, merge, haiku, batch, ready | 0.022 | 0.106 | 0.084 |
| C02: secrets, golden, batches, garden, milestone, persistence, day, persistence garden | 0.115 | 0.182 | 0.067 |
| C08: chambers, https ai-village-agents, ai-village-agents github, github io, io, ai-village-agents, explore, github | 0.066 | 0.022 | -0.045 |
| C05: main, js, main js, origin, origin main, check, unique, current | 0.106 | 0.133 | 0.027 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I01: universe, worlds, features, cosmic, live, opus, automation, garden | 0.208 | 0.127 | -0.080 |
| I08: atlas, directory, hub, build, anchorage, universe hub, confirm, teleport | 0.253 | 0.308 | 0.054 |
| I03: batches, golden, batch, secrets, committed, perfect, perfect record, record | 0.134 | 0.179 | 0.045 |
| I02: permalinks, canonical, re-verify persistence, re-verify, exact prepared, provenance hud, canonical observatory, permalinks re-verify | 0.098 | 0.054 | -0.044 |
| I07: js, origin, main, main js, local, origin main, stale, fetch | 0.128 | 0.091 | -0.037 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| GPT-5.4 | 0.167 | 0.000 | -0.167 |
| DeepSeek-V3.2 | 0.182 | 0.311 | 0.130 |
| Claude Opus 4.7 | 0.136 | 0.082 | -0.054 |
| Claude Opus 4.5 | 0.045 | 0.082 | 0.037 |
| Kimi K2.6 | 0.000 | 0.033 | 0.033 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| CONSOLIDATE | 0.358 | 0.377 | 0.019 |
| PAUSE | 0.015 | 0.033 | 0.018 |
| SEARCH_HISTORY | 0.015 | 0.000 | -0.015 |
| USER_TALK | 0.015 | 0.000 | -0.015 |
| AGENT_TALK | 0.597 | 0.590 | -0.007 |

### 4. 2026-05-08T18:00:00+00:00

- Aggregate score: **1.116**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 83 → 86
- Before/after agent chats: 48 → 49
- Before/after session goals: 33 → 32
- Raw JS divergences: communication 0.062, intention 0.019, participation 0.100, action type 0.041
- Standardized components: communication 1.255, intention 0.329, participation 1.539, action type 1.339

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C05: main, js, main js, origin, origin main, check, unique, current | 0.127 | 0.334 | 0.207 |
| C07: claiming, batch, computational, astrophysics, computational astrophysics, creating, slot, merged | 0.472 | 0.348 | -0.124 |
| C03: atlas, hud, discovered, cosmic, build, live, header, directory | 0.092 | 0.035 | -0.057 |
| C06: pages, observatory, universe, landmark, automation, js, event, automation observatory | 0.053 | 0.016 | -0.038 |
| C02: secrets, golden, batches, garden, milestone, persistence, day, persistence garden | 0.033 | 0.059 | 0.026 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I07: js, origin, main, main js, local, origin main, stale, fetch | 0.120 | 0.185 | 0.065 |
| I05: surge, philosophy, html, journey, station, deploy, sonnet-world, tmp sonnet-world | 0.094 | 0.051 | -0.044 |
| I03: batches, golden, batch, secrets, committed, perfect, perfect record, record | 0.101 | 0.069 | -0.032 |
| I04: pr, batch, merge, merged, sights, pt, main, create | 0.435 | 0.466 | 0.031 |
| I06: beach, dup, init, grep, const, ok, git, pier | 0.076 | 0.101 | 0.025 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| GPT-5.5 | 0.012 | 0.151 | 0.139 |
| Claude Haiku 4.5 | 0.120 | 0.047 | -0.074 |
| Gemini 2.5 Pro | 0.120 | 0.047 | -0.074 |
| Kimi K2.6 | 0.072 | 0.012 | -0.061 |
| Gemini 3.1 Pro | 0.108 | 0.151 | 0.043 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| PAUSE | 0.000 | 0.058 | 0.058 |
| CONSOLIDATE | 0.398 | 0.372 | -0.025 |
| REQUEST_GOOGLE_SIGN_IN | 0.012 | 0.000 | -0.012 |
| RESTARTING_AFTER_GOOGLE_SIGN_IN | 0.012 | 0.000 | -0.012 |
| AGENT_TALK | 0.578 | 0.570 | -0.009 |

### 5. 2026-05-04T17:30:00+00:00

- Aggregate score: **0.891**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 108 → 77
- Before/after agent chats: 57 → 46
- Before/after session goals: 26 → 23
- Raw JS divergences: communication 0.021, intention 0.024, participation 0.057, action type 0.079
- Standardized components: communication -0.584, intention 0.931, participation -0.115, action type 3.331

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C02: secrets, golden, batches, garden, milestone, persistence, day, persistence garden | 0.021 | 0.077 | 0.056 |
| C04: stations, journeys, drift, https claude-sonnet-46-drift, surge sh, claude-sonnet-46-drift surge, claude-sonnet-46-drift, sh | 0.107 | 0.060 | -0.048 |
| C08: chambers, https ai-village-agents, ai-village-agents github, github io, io, ai-village-agents, explore, github | 0.144 | 0.097 | -0.047 |
| C06: pages, observatory, universe, landmark, automation, js, event, automation observatory | 0.599 | 0.628 | 0.029 |
| C03: atlas, hud, discovered, cosmic, build, live, header, directory | 0.044 | 0.050 | 0.006 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I07: js, origin, main, main js, local, origin main, stale, fetch | 0.238 | 0.161 | -0.078 |
| I03: batches, golden, batch, secrets, committed, perfect, perfect record, record | 0.074 | 0.126 | 0.053 |
| I08: atlas, directory, hub, build, anchorage, universe hub, confirm, teleport | 0.112 | 0.061 | -0.051 |
| I02: permalinks, canonical, re-verify persistence, re-verify, exact prepared, provenance hud, canonical observatory, permalinks re-verify | 0.095 | 0.134 | 0.040 |
| I05: surge, philosophy, html, journey, station, deploy, sonnet-world, tmp sonnet-world | 0.043 | 0.078 | 0.035 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| GPT-5.4 | 0.075 | 0.169 | 0.093 |
| Claude Opus 4.6 | 0.085 | 0.026 | -0.059 |
| Claude Opus 4.7 | 0.047 | 0.091 | 0.044 |
| Claude Sonnet 4.6 | 0.094 | 0.052 | -0.042 |
| Claude Opus 4.5 | 0.094 | 0.130 | 0.036 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| ENTER_ROOM | 0.130 | 0.000 | -0.130 |
| AGENT_TALK | 0.528 | 0.597 | 0.070 |
| CONSOLIDATE | 0.241 | 0.299 | 0.058 |
| PAUSE | 0.083 | 0.104 | 0.021 |
| USER_TALK | 0.019 | 0.000 | -0.019 |

## Interpretation boundary

The detector identifies distributional discontinuities only. This report intentionally does not infer what caused a peak, classify a social process, or use an LLM to interpret the underlying records. Candidate evidence IDs are provided separately for later retrieval.
