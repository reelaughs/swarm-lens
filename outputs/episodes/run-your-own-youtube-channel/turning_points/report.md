# Population-level turning points: Run your own Youtube channel!

This calibration report ranks changes in collective behavior. It does not assign causal triggers or social-process labels.

## Episode and detector

- Goal ID: `a11372d6-e2c5-4ffc-9468-01a25d7bca39`
- Authoritative interval: `[2026-05-18T12:26:24.346000+00:00, 2026-05-25T12:03:15.101000+00:00)` UTC
- Configuration fingerprint: `172e24df5adeb504a70d263632e34ef8491f07f48aeca2da7f27511074a930fe`
- Topic cache reused: `True`
- Minimum valid comparisons for reliable standardization: `10`
- Minimum peak separation: `120` clock minutes
- Participation and action-type signals are complementary views of the same high-level-event stream; they are not statistically independent measurements.

## Windowing diagnostics

| Window | Active / total | Overall-eligible | Adjacent comparisons | Valid aggregates | Inactive gaps | Inactive minutes | Max gap | Reliable |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 30m | 50 / 337 | 40 | 35 | 35 | 6 | 8556 | 3753 | True |
| 60m | 30 / 169 | 20 | 15 | 15 | 6 | 8256 | 3723 | True |
| 90m | 20 / 113 | 15 | 10 | 10 | 6 | 8256 | 3693 | True |

Recommended initial window size: **30 minutes**.
The recommendation rule chooses the smallest profiled window size with enough valid aggregate comparisons, preserving the highest supported temporal resolution.

## Topic representations

- **Communication**: 1218 usable documents, 5000 TF-IDF features, 8 NMF components, reconstruction error 33.116.
- **Intention**: 1221 usable documents, 5000 TF-IDF features, 8 NMF components, reconstruction error 31.931.

## Standardization diagnostics

### 30-minute windows

| Component | Valid raw divergences | Center | Scale | Method | Reliable |
| --- | ---: | ---: | ---: | --- | --- |
| communication | 35 | 0.047 | 0.035 | mad | True |
| intention | 35 | 0.013 | 0.009 | mad | True |
| participation | 35 | 0.052 | 0.030 | mad | True |
| action type | 35 | 0.035 | 0.029 | mad | True |

### 60-minute windows

| Component | Valid raw divergences | Center | Scale | Method | Reliable |
| --- | ---: | ---: | ---: | --- | --- |
| communication | 15 | 0.052 | 0.043 | mad | True |
| intention | 15 | 0.014 | 0.013 | mad | True |
| participation | 15 | 0.031 | 0.005 | mad | True |
| action type | 15 | 0.017 | 0.018 | mad | True |

### 90-minute windows

| Component | Valid raw divergences | Center | Scale | Method | Reliable |
| --- | ---: | ---: | ---: | --- | --- |
| communication | 10 | 0.061 | 0.026 | mad | True |
| intention | 10 | 0.009 | 0.008 | mad | True |
| participation | 10 | 0.023 | 0.010 | mad | True |
| action type | 10 | 0.024 | 0.016 | mad | True |

## Top candidate turning points

### 1. 2026-05-21T19:00:00+00:00

- Aggregate score: **2.025**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 56 → 54
- Before/after agent chats: 22 → 20
- Before/after session goals: 29 → 29
- Raw JS divergences: communication 0.183, intention 0.052, participation 0.055, action type 0.026
- Standardized components: communication 3.897, intention 4.458, participation 0.084, action type -0.338

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C02: shot, verify-the-rails, greenlit, md, pushed, added, upload-ready, greenlit upload-ready | 0.150 | 0.450 | 0.300 |
| C04: gemini, just, scene, pro, gemini pro, v5, like, right | 0.239 | 0.005 | -0.234 |
| C01: day, polish, quality, ready, quality review, pm, pt, audio | 0.197 | 0.104 | -0.092 |
| C08: gui, text-only, upload, youtube, studio, collaboration, github, agent | 0.106 | 0.161 | 0.055 |
| C03: big questions, big, questions, questions https, questions series, problem, https youtu, youtu | 0.105 | 0.056 | -0.048 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I06: video, publish, click, set, upload, captions, captions srt, public | 0.115 | 0.309 | 0.194 |
| I05: v5, gemini, v6, caption, kimi, feedback, captions, v7 | 0.182 | 0.094 | -0.088 |
| I08: oembed, proof, artifacts, pages-mixed-state-youtube, video, video6, oembed json, artifacts video6 | 0.181 | 0.131 | -0.050 |
| I03: claim, computeruse verify-the-rails, evidence, shot, verify-the-rails, phone-safe, head, short | 0.124 | 0.082 | -0.042 |
| I04: quality, production, day, documentation, collaboration, video, ready, visual | 0.183 | 0.152 | -0.031 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| GPT-5.4 | 0.111 | 0.241 | 0.130 |
| DeepSeek-V3.2 | 0.167 | 0.093 | -0.074 |
| Gemini 3.5 Flash | 0.111 | 0.037 | -0.074 |
| Claude Haiku 4.5 | 0.037 | 0.074 | 0.037 |
| Claude Opus 4.6 | 0.019 | 0.037 | 0.019 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| SEARCH_HISTORY | 0.018 | 0.056 | 0.038 |
| USER_TALK | 0.036 | 0.000 | -0.036 |
| AGENT_TALK | 0.393 | 0.370 | -0.022 |
| CONSOLIDATE | 0.518 | 0.537 | 0.019 |
| PAUSE | 0.036 | 0.037 | 0.001 |

### 2. 2026-05-20T20:00:00+00:00

- Aggregate score: **1.845**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 52 → 68
- Before/after agent chats: 19 → 37
- Before/after session goals: 29 → 27
- Raw JS divergences: communication 0.194, intention 0.022, participation 0.093, action type 0.057
- Standardized components: communication 4.198, intention 1.077, participation 1.356, action type 0.750

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C01: day, polish, quality, ready, quality review, pm, pt, audio | 0.436 | 0.170 | -0.266 |
| C02: shot, verify-the-rails, greenlit, md, pushed, added, upload-ready, greenlit upload-ready | 0.071 | 0.316 | 0.245 |
| C08: gui, text-only, upload, youtube, studio, collaboration, github, agent | 0.254 | 0.063 | -0.192 |
| C07: pages-mixed-state-youtube, oembed, artifacts, commit, py, pushed, docs, ai-village-agents pages-mixed-state-youtube | 0.060 | 0.201 | 0.141 |
| C06: https, https youtu, youtu, published, video, ai, videos, video published | 0.041 | 0.081 | 0.040 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I06: video, publish, click, set, upload, captions, captions srt, public | 0.226 | 0.129 | -0.097 |
| I01: videos, pm, day, published, pm pt, pt, channel, video | 0.096 | 0.158 | 0.062 |
| I04: quality, production, day, documentation, collaboration, video, ready, visual | 0.148 | 0.196 | 0.049 |
| I05: v5, gemini, v6, caption, kimi, feedback, captions, v7 | 0.145 | 0.100 | -0.045 |
| I08: oembed, proof, artifacts, pages-mixed-state-youtube, video, video6, oembed json, artifacts video6 | 0.150 | 0.183 | 0.033 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| GPT-5.4 | 0.058 | 0.209 | 0.151 |
| DeepSeek-V3.2 | 0.231 | 0.104 | -0.126 |
| GPT-5.2 | 0.115 | 0.164 | 0.049 |
| GPT-5.5 | 0.038 | 0.000 | -0.038 |
| Gemini 3.5 Flash | 0.038 | 0.075 | 0.036 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| AGENT_TALK | 0.365 | 0.544 | 0.179 |
| CONSOLIDATE | 0.558 | 0.397 | -0.161 |
| REQUEST_GOOGLE_SIGN_IN | 0.019 | 0.000 | -0.019 |
| RESTARTING_AFTER_GOOGLE_SIGN_IN | 0.019 | 0.000 | -0.019 |
| SEARCH_HISTORY | 0.000 | 0.015 | 0.015 |

### 3. 2026-05-22T19:30:00+00:00

- Aggregate score: **1.550**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 77 → 104
- Before/after agent chats: 31 → 54
- Before/after session goals: 29 → 36
- Raw JS divergences: communication 0.047, intention 0.035, participation 0.100, action type 0.095
- Standardized components: communication 0.000, intention 2.514, participation 1.598, action type 2.086

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C05: framework, exchange, concept, feedback, category, evaluation, constraints, audience | 0.571 | 0.373 | -0.198 |
| C01: day, polish, quality, ready, quality review, pm, pt, audio | 0.103 | 0.212 | 0.109 |
| C04: gemini, just, scene, pro, gemini pro, v5, like, right | 0.179 | 0.259 | 0.080 |
| C06: https, https youtu, youtu, published, video, ai, videos, video published | 0.020 | 0.068 | 0.047 |
| C03: big questions, big, questions, questions https, questions series, problem, https youtu, youtu | 0.066 | 0.050 | -0.016 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I04: quality, production, day, documentation, collaboration, video, ready, visual | 0.138 | 0.245 | 0.107 |
| I08: oembed, proof, artifacts, pages-mixed-state-youtube, video, video6, oembed json, artifacts video6 | 0.137 | 0.045 | -0.092 |
| I05: v5, gemini, v6, caption, kimi, feedback, captions, v7 | 0.139 | 0.188 | 0.049 |
| I03: claim, computeruse verify-the-rails, evidence, shot, verify-the-rails, phone-safe, head, short | 0.198 | 0.152 | -0.046 |
| I06: video, publish, click, set, upload, captions, captions srt, public | 0.150 | 0.124 | -0.026 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| DeepSeek-V3.2 | 0.250 | 0.427 | 0.177 |
| GPT-5.1 | 0.079 | 0.000 | -0.079 |
| Gemini 3.1 Pro | 0.026 | 0.078 | 0.051 |
| Claude Haiku 4.5 | 0.105 | 0.058 | -0.047 |
| Claude Opus 4.7 | 0.092 | 0.049 | -0.044 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| PAUSE | 0.208 | 0.038 | -0.169 |
| AGENT_TALK | 0.403 | 0.519 | 0.117 |
| SEARCH_HISTORY | 0.000 | 0.087 | 0.087 |
| CONSOLIDATE | 0.377 | 0.346 | -0.030 |
| USER_TALK | 0.013 | 0.010 | -0.003 |

### 4. 2026-05-19T18:00:00+00:00

- Aggregate score: **0.648**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 62 → 49
- Before/after agent chats: 40 → 18
- Before/after session goals: 22 → 26
- Raw JS divergences: communication 0.063, intention 0.005, participation 0.086, action type 0.092
- Standardized components: communication 0.449, intention -0.945, participation 1.137, action type 1.952

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C04: gemini, just, scene, pro, gemini pro, v5, like, right | 0.476 | 0.264 | -0.212 |
| C08: gui, text-only, upload, youtube, studio, collaboration, github, agent | 0.134 | 0.252 | 0.118 |
| C07: pages-mixed-state-youtube, oembed, artifacts, commit, py, pushed, docs, ai-village-agents pages-mixed-state-youtube | 0.067 | 0.145 | 0.078 |
| C05: framework, exchange, concept, feedback, category, evaluation, constraints, audience | 0.089 | 0.028 | -0.061 |
| C06: https, https youtu, youtu, published, video, ai, videos, video published | 0.081 | 0.115 | 0.034 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I04: quality, production, day, documentation, collaboration, video, ready, visual | 0.153 | 0.196 | 0.043 |
| I08: oembed, proof, artifacts, pages-mixed-state-youtube, video, video6, oembed json, artifacts video6 | 0.133 | 0.101 | -0.032 |
| I03: claim, computeruse verify-the-rails, evidence, shot, verify-the-rails, phone-safe, head, short | 0.098 | 0.082 | -0.016 |
| I07: big questions, big, questions, https, https youtu, youtu, problem, type | 0.086 | 0.097 | 0.011 |
| I06: video, publish, click, set, upload, captions, captions srt, public | 0.200 | 0.189 | -0.011 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| GPT-5.2 | 0.177 | 0.082 | -0.096 |
| Claude Opus 4.6 | 0.097 | 0.041 | -0.056 |
| Claude Opus 4.5 | 0.113 | 0.061 | -0.052 |
| Claude Opus 4.7 | 0.032 | 0.082 | 0.049 |
| Claude Sonnet 4.5 | 0.016 | 0.061 | 0.045 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| AGENT_TALK | 0.645 | 0.367 | -0.278 |
| CONSOLIDATE | 0.355 | 0.531 | 0.176 |
| REQUEST_GOOGLE_SIGN_IN | 0.000 | 0.041 | 0.041 |
| RESTARTING_AFTER_GOOGLE_SIGN_IN | 0.000 | 0.041 | 0.041 |
| SEARCH_HISTORY | 0.000 | 0.020 | 0.020 |

### 5. 2026-05-19T20:30:00+00:00

- Aggregate score: **0.508**
- Contributing components (4): `communication,intention,participation,action_type`
- Before/after high-level events: 75 → 73
- Before/after agent chats: 40 → 28
- Before/after session goals: 30 → 40
- Raw JS divergences: communication 0.044, intention 0.018, participation 0.089, action type 0.047
- Standardized components: communication -0.101, intention 0.514, participation 1.215, action type 0.406

#### Communication-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| C04: gemini, just, scene, pro, gemini pro, v5, like, right | 0.357 | 0.270 | -0.087 |
| C01: day, polish, quality, ready, quality review, pm, pt, audio | 0.049 | 0.125 | 0.076 |
| C02: shot, verify-the-rails, greenlit, md, pushed, added, upload-ready, greenlit upload-ready | 0.089 | 0.136 | 0.046 |
| C05: framework, exchange, concept, feedback, category, evaluation, constraints, audience | 0.041 | 0.000 | -0.041 |
| C07: pages-mixed-state-youtube, oembed, artifacts, commit, py, pushed, docs, ai-village-agents pages-mixed-state-youtube | 0.030 | 0.056 | 0.026 |

#### Action/intention-workstream changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| I05: v5, gemini, v6, caption, kimi, feedback, captions, v7 | 0.132 | 0.232 | 0.099 |
| I04: quality, production, day, documentation, collaboration, video, ready, visual | 0.175 | 0.122 | -0.053 |
| I06: video, publish, click, set, upload, captions, captions srt, public | 0.177 | 0.127 | -0.050 |
| I01: videos, pm, day, published, pm pt, pt, channel, video | 0.167 | 0.146 | -0.021 |
| I02: hud, permalink, copy, persistence, nb hyphen, nb, hyphen, canonical | 0.049 | 0.061 | 0.012 |

#### Agent-participation changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| Gemini 3.1 Pro | 0.041 | 0.194 | 0.154 |
| Claude Opus 4.5 | 0.162 | 0.083 | -0.079 |
| DeepSeek-V3.2 | 0.135 | 0.069 | -0.066 |
| GPT-5.1 | 0.081 | 0.139 | 0.058 |
| Claude Opus 4.6 | 0.081 | 0.028 | -0.053 |

#### High-level action-type changes

| Item | Before | After | Δ |
| --- | ---: | ---: | ---: |
| AGENT_TALK | 0.533 | 0.384 | -0.150 |
| CONSOLIDATE | 0.400 | 0.548 | 0.148 |
| PAUSE | 0.013 | 0.055 | 0.041 |
| SEARCH_HISTORY | 0.040 | 0.000 | -0.040 |
| USER_TALK | 0.013 | 0.014 | 0.000 |

## Interpretation boundary

The detector identifies distributional discontinuities only. This report intentionally does not infer what caused a peak, classify a social process, or use an LLM to interpret the underlying records. Candidate evidence IDs are provided separately for later retrieval.
