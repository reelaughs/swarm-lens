# Population-level turning points: Perform novel research!

This calibration report ranks changes in collective behavior. It does not assign causal triggers or social-process labels.

## Episode and detector

- Goal ID: `ee7a006d-c196-4824-b804-ead8e9632228`
- Authoritative interval: `[2026-05-11T07:47:04.725000+00:00, 2026-05-18T12:26:24.346000+00:00)` UTC
- Configuration fingerprint: `172e24df5adeb504a70d263632e34ef8491f07f48aeca2da7f27511074a930fe`
- Topic cache reused: `False`
- Minimum valid comparisons for reliable standardization: `10`
- Minimum peak separation: `120` clock minutes
- Participation and action-type signals are complementary views of the same high-level-event stream; they are not statistically independent measurements.

## Windowing diagnostics

| Window | Active / total | Overall-eligible | Adjacent comparisons | Valid aggregates | Inactive gaps | Inactive minutes | Max gap | Reliable |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 30m | 50 / 346 | 40 | 35 | 35 | 6 | 8858 | 3776 | True |
| 60m | 30 / 174 | 20 | 15 | 15 | 6 | 8558 | 3746 | True |
| 90m | 20 / 116 | 15 | 10 | 10 | 6 | 8558 | 3716 | True |

Recommended initial window size: **30 minutes**.
The recommendation rule chooses the smallest profiled window size with enough valid aggregate comparisons, preserving the highest supported temporal resolution.

## Topic representations

- **Communication**: 2146 usable documents, 5000 TF-IDF features, 8 NMF components, reconstruction error 43.842.
- **Intention**: 1014 usable documents, 5000 TF-IDF features, 8 NMF components, reconstruction error 29.263.

## Standardization diagnostics

### 30-minute windows

| Component | Valid raw divergences | Center | Scale | Method | Reliable |
| --- | ---: | ---: | ---: | --- | --- |
| communication | 35 | 0.045 | 0.030 | mad | True |
| intention | 35 | 0.029 | 0.025 | mad | True |
| participation | 35 | 0.076 | 0.047 | mad | True |
| action type | 35 | 0.034 | 0.025 | mad | True |

### 60-minute windows

| Component | Valid raw divergences | Center | Scale | Method | Reliable |
| --- | ---: | ---: | ---: | --- | --- |
| communication | 15 | 0.039 | 0.021 | mad | True |
| intention | 15 | 0.020 | 0.013 | mad | True |
| participation | 15 | 0.037 | 0.021 | mad | True |
| action type | 15 | 0.032 | 0.014 | mad | True |

### 90-minute windows

| Component | Valid raw divergences | Center | Scale | Method | Reliable |
| --- | ---: | ---: | ---: | --- | --- |
| communication | 10 | 0.048 | 0.043 | mad | True |
| intention | 10 | 0.033 | 0.013 | mad | True |
| participation | 10 | 0.034 | 0.012 | mad | True |
| action type | 10 | 0.032 | 0.019 | mad | True |

## Top candidate turning points

### 1. 2026-05-15T17:30:00+00:00

- Aggregate score: **1.670**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 46 → 58
- Before/after agent chats: 33 → 39
- Before/after session goals: 6 → 16
- Raw JS divergences: communication 0.047, intention 0.162, participation 0.120, action type 0.045
- Standardized components: communication 0.059, intention 5.258, participation 0.935, action type 0.428

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C01: github io, io, ai-village-agents github, https ai-village-agents, ai-village-agents, github, https, html | 0.042 | 0.149 | 0.107 |
| C07: governance, cross-room, coordination, protocol, incidents, data, research, activation | 0.469 | 0.382 | -0.087 |
| C04: html, public, id, edge, garden, persistence, edge garden, qa | 0.175 | 0.125 | -0.049 |
| C03: kimi, gemini, c2, judge, c1, claude, label-swap, pushed | 0.086 | 0.130 | 0.044 |
| C06: persistence, secrets, garden, velocity, pm, hour, features, historic | 0.062 | 0.105 | 0.043 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I07: goal, new, html, research, github, pr, ai-village-agents, https | 0.389 | 0.180 | -0.209 |
| I01: garden, edge, liminal, edge garden, features, persistence, drift, pm | 0.183 | 0.373 | 0.190 |
| I03: kimi, py, c1, c2, replication-wave, claude, gemini, judge | 0.057 | 0.196 | 0.139 |
| I02: hud, canonical, anchor, permalink, verify persistence, canonical observatory, observatory, worlds json | 0.216 | 0.080 | -0.135 |
| I05: secrets, batch, batches, pm, added secrets, day added, started day, repository sonnet-45-world | 0.000 | 0.093 | 0.093 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| GPT-5.4 | 0.233 | 0.125 | -0.108 |
| Claude Opus 4.5 | 0.047 | 0.143 | 0.096 |
| DeepSeek-V3.2 | 0.256 | 0.179 | -0.077 |
| Claude Sonnet 4.5 | 0.000 | 0.071 | 0.071 |
| Claude Opus 4.6 | 0.023 | 0.071 | 0.048 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| CONSOLIDATE | 0.130 | 0.276 | 0.145 |
| PAUSE | 0.065 | 0.017 | -0.048 |
| AGENT_TALK | 0.717 | 0.672 | -0.045 |
| USER_TALK | 0.065 | 0.034 | -0.031 |
| SEARCH_HISTORY | 0.022 | 0.000 | -0.022 |

### 2. 2026-05-12T17:30:00+00:00

- Aggregate score: **1.079**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 86 → 97
- Before/after agent chats: 33 → 70
- Before/after session goals: 18 → 17
- Raw JS divergences: communication 0.032, intention 0.031, participation 0.131, action type 0.123
- Standardized components: communication -0.452, intention 0.075, participation 1.173, action type 3.521

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C08: main, pr, docs, md, com, blogpost, github, pages | 0.238 | 0.371 | 0.133 |
| C02: task, fresh, session, scoring, structured, skeptic, solo, proposer | 0.508 | 0.378 | -0.130 |
| C03: kimi, gemini, c2, judge, c1, claude, label-swap, pushed | 0.189 | 0.133 | -0.056 |
| C07: governance, cross-room, coordination, protocol, incidents, data, research, activation | 0.036 | 0.067 | 0.031 |
| C05: journey, surge, surge sh, sh, claude-sonnet-46-drift surge, claude-sonnet-46-drift, stations, https claude-sonnet-46-drift | 0.003 | 0.017 | 0.014 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I07: goal, new, html, research, github, pr, ai-village-agents, https | 0.093 | 0.192 | 0.099 |
| I02: hud, canonical, anchor, permalink, verify persistence, canonical observatory, observatory, worlds json | 0.110 | 0.059 | -0.051 |
| I08: signal cartographer, hub qa, anchorage, cartographer, universe hub, hub, signal, universe | 0.125 | 0.074 | -0.051 |
| I03: kimi, py, c1, c2, replication-wave, claude, gemini, judge | 0.218 | 0.244 | 0.026 |
| I05: secrets, batch, batches, pm, added secrets, day added, started day, repository sonnet-45-world | 0.022 | 0.002 | -0.021 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| Claude Opus 4.6 | 0.153 | 0.072 | -0.081 |
| Gemini 2.5 Pro | 0.082 | 0.010 | -0.072 |
| DeepSeek-V3.2 | 0.024 | 0.093 | 0.069 |
| GPT-5.2 | 0.059 | 0.124 | 0.065 |
| Claude Sonnet 4.6 | 0.082 | 0.021 | -0.062 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| AGENT_TALK | 0.384 | 0.722 | 0.338 |
| PAUSE | 0.395 | 0.093 | -0.303 |
| CONSOLIDATE | 0.209 | 0.175 | -0.034 |
| USER_TALK | 0.012 | 0.000 | -0.012 |
| REQUEST_GOOGLE_SIGN_IN | 0.000 | 0.010 | 0.010 |

### 3. 2026-05-15T20:30:00+00:00

- Aggregate score: **1.056**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 47 → 63
- Before/after agent chats: 34 → 36
- Before/after session goals: 10 → 14
- Raw JS divergences: communication 0.090, intention 0.069, participation 0.129, action type 0.035
- Standardized components: communication 1.485, intention 1.572, participation 1.124, action type 0.043

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C04: html, public, id, edge, garden, persistence, edge garden, qa | 0.336 | 0.153 | -0.184 |
| C01: github io, io, ai-village-agents github, https ai-village-agents, ai-village-agents, github, https, html | 0.081 | 0.205 | 0.123 |
| C06: persistence, secrets, garden, velocity, pm, hour, features, historic | 0.142 | 0.264 | 0.122 |
| C03: kimi, gemini, c2, judge, c1, claude, label-swap, pushed | 0.189 | 0.090 | -0.098 |
| C07: governance, cross-room, coordination, protocol, incidents, data, research, activation | 0.014 | 0.062 | 0.049 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I03: kimi, py, c1, c2, replication-wave, claude, gemini, judge | 0.305 | 0.147 | -0.158 |
| I07: goal, new, html, research, github, pr, ai-village-agents, https | 0.128 | 0.228 | 0.101 |
| I01: garden, edge, liminal, edge garden, features, persistence, drift, pm | 0.375 | 0.306 | -0.070 |
| I02: hud, canonical, anchor, permalink, verify persistence, canonical observatory, observatory, worlds json | 0.011 | 0.081 | 0.069 |
| I06: journey, stations, deploy, journeys, surge, deployed, surge sh, currently journey | 0.014 | 0.068 | 0.054 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| GPT-5.4 | 0.217 | 0.102 | -0.116 |
| DeepSeek-V3.2 | 0.022 | 0.119 | 0.097 |
| GPT-5.2 | 0.130 | 0.034 | -0.097 |
| GPT-5.5 | 0.130 | 0.051 | -0.080 |
| Claude Opus 4.5 | 0.043 | 0.119 | 0.075 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| AGENT_TALK | 0.723 | 0.571 | -0.152 |
| PAUSE | 0.043 | 0.143 | 0.100 |
| USER_TALK | 0.021 | 0.063 | 0.042 |
| CONSOLIDATE | 0.213 | 0.222 | 0.009 |
| ENTER_ROOM | 0.000 | 0.000 | 0.000 |

### 4. 2026-05-12T20:30:00+00:00

- Aggregate score: **0.997**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 65 → 81
- Before/after agent chats: 37 → 34
- Before/after session goals: 24 → 30
- Raw JS divergences: communication 0.057, intention 0.043, participation 0.185, action type 0.053
- Standardized components: communication 0.397, intention 0.536, participation 2.299, action type 0.754

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C03: kimi, gemini, c2, judge, c1, claude, label-swap, pushed | 0.277 | 0.358 | 0.081 |
| C08: main, pr, docs, md, com, blogpost, github, pages | 0.424 | 0.345 | -0.078 |
| C02: task, fresh, session, scoring, structured, skeptic, solo, proposer | 0.145 | 0.070 | -0.075 |
| C06: persistence, secrets, garden, velocity, pm, hour, features, historic | 0.010 | 0.082 | 0.072 |
| C05: journey, surge, surge sh, sh, claude-sonnet-46-drift surge, claude-sonnet-46-drift, stations, https claude-sonnet-46-drift | 0.065 | 0.013 | -0.052 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I07: goal, new, html, research, github, pr, ai-village-agents, https | 0.255 | 0.474 | 0.218 |
| I04: task, session, skeptic, proposer, solo, scoring, pair, gpt-5 | 0.208 | 0.110 | -0.098 |
| I03: kimi, py, c1, c2, replication-wave, claude, gemini, judge | 0.274 | 0.212 | -0.062 |
| I08: signal cartographer, hub qa, anchorage, cartographer, universe hub, hub, signal, universe | 0.081 | 0.051 | -0.030 |
| I05: secrets, batch, batches, pm, added secrets, day added, started day, repository sonnet-45-world | 0.080 | 0.060 | -0.019 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| GPT-5.4 | 0.000 | 0.152 | 0.152 |
| Gemini 3.1 Pro | 0.172 | 0.063 | -0.109 |
| GPT-5.2 | 0.141 | 0.051 | -0.090 |
| DeepSeek-V3.2 | 0.078 | 0.165 | 0.086 |
| Claude Opus 4.5 | 0.172 | 0.089 | -0.083 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| AGENT_TALK | 0.569 | 0.420 | -0.149 |
| PAUSE | 0.046 | 0.123 | 0.077 |
| SEARCH_HISTORY | 0.000 | 0.062 | 0.062 |
| USER_TALK | 0.015 | 0.025 | 0.009 |
| CONSOLIDATE | 0.369 | 0.370 | 0.001 |

### 5. 2026-05-13T20:00:00+00:00

- Aggregate score: **0.899**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 79 → 68
- Before/after agent chats: 38 → 41
- Before/after session goals: 27 → 24
- Raw JS divergences: communication 0.084, intention 0.064, participation 0.091, action type 0.049
- Standardized components: communication 1.302, intention 1.366, participation 0.317, action type 0.611

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C07: governance, cross-room, coordination, protocol, incidents, data, research, activation | 0.243 | 0.072 | -0.171 |
| C04: html, public, id, edge, garden, persistence, edge garden, qa | 0.031 | 0.163 | 0.132 |
| C01: github io, io, ai-village-agents github, https ai-village-agents, ai-village-agents, github, https, html | 0.205 | 0.268 | 0.063 |
| C08: main, pr, docs, md, com, blogpost, github, pages | 0.165 | 0.132 | -0.032 |
| C05: journey, surge, surge sh, sh, claude-sonnet-46-drift surge, claude-sonnet-46-drift, stations, https claude-sonnet-46-drift | 0.043 | 0.013 | -0.030 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I03: kimi, py, c1, c2, replication-wave, claude, gemini, judge | 0.216 | 0.343 | 0.128 |
| I07: goal, new, html, research, github, pr, ai-village-agents, https | 0.398 | 0.286 | -0.112 |
| I01: garden, edge, liminal, edge garden, features, persistence, drift, pm | 0.080 | 0.168 | 0.088 |
| I06: journey, stations, deploy, journeys, surge, deployed, surge sh, currently journey | 0.079 | 0.003 | -0.075 |
| I05: secrets, batch, batches, pm, added secrets, day added, started day, repository sonnet-45-world | 0.109 | 0.072 | -0.037 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| GPT-5.4 | 0.105 | 0.212 | 0.107 |
| Claude Opus 4.6 | 0.053 | 0.121 | 0.069 |
| DeepSeek-V3.2 | 0.053 | 0.000 | -0.053 |
| GPT-5.2 | 0.092 | 0.045 | -0.047 |
| Claude Haiku 4.5 | 0.105 | 0.061 | -0.045 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| AGENT_TALK | 0.481 | 0.603 | 0.122 |
| PAUSE | 0.114 | 0.015 | -0.099 |
| REQUEST_GOOGLE_SIGN_IN | 0.013 | 0.000 | -0.013 |
| RESTARTING_AFTER_GOOGLE_SIGN_IN | 0.013 | 0.000 | -0.013 |
| CONSOLIDATE | 0.342 | 0.353 | 0.011 |

## Interpretation boundary

The detector identifies distributional discontinuities only. This report intentionally does not infer what caused a peak, classify a social process, or use an LLM to interpret the underlying records. Candidate evidence IDs are provided separately for later retrieval.
