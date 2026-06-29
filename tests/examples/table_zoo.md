# Table Zoo

A regression fixture for md2star table rendering. Each table below exercises
a known-tricky width or column-count pattern. Re-render to DOCX/PPTX after
any change to the table pipeline to verify the visuals.

## Skewed three-column table

| ID | Description | Section |
|---|---|---|
| C1 | A short label in the first column, a paragraph-length cell in the second, and a tiny anchor in the third — the classic shape that crushes the side columns under naive auto-fit. | §6 |
| C2 | Another mid-length description so the column-2 average dominates the layout calculation. | §4 |
| C3 | Final row, with a `code span`, an *italic* word, and a [link](https://example.com). | §9 |

## Two-column with one wide cell

| Term | Definition |
|---|---|
| K-factor | The Elo learning-rate constant; controls how much each rating moves per win/loss outcome. |
| Capability mask | A safeguard that limits Elo updates to a fixed set of known capabilities so typos in user prompts cannot grow the state file. |

## Aligned three-column

| Left | Center | Right |
|:---|:---:|---:|
| a | b | c |
| 1 | 2 | 3 |

## Wide multi-column (should trigger MyTableSmall)

| Model | Provider | Latency (ms) | Cost ($/Mtok) | Context | Quality | Cap. coding | Cap. math | Notes |
|---|---|---|---|---|---|---|---|---|
| gemma4-e2b | local | 140 | 0.00 | 32k | 0.72 | 0.78 | 0.65 | runs cold-start in 1.4 s |
| gpt-4o-mini | openai | 280 | 0.15 | 128k | 0.85 | 0.81 | 0.88 | shipping default for cost band |
| claude-3-5-sonnet | anthropic | 410 | 3.00 | 200k | 0.93 | 0.92 | 0.90 | strong on long-context fusion |

## Tight tabular numbers

| Surface | RPS | p50 | p99 |
|---|---:|---:|---:|
| CLI | 1.2 | 220 | 880 |
| GUI | 0.9 | 240 | 1050 |
| API | 14.7 | 180 | 740 |
| MCP | 6.1 | 210 | 830 |

## Code in cells

| Variant | Env var | Quality score |
|---|---|---|
| Heuristic (default) | unset | Prior + rolling Elo. |
| Matrix factorisation | `ROITELET_ROUTER=mf` | TF-IDF + truncated SVD per-model centre, blended 50/50 with the heuristic. |
| Calibrated | `ROITELET_ROUTER=calibrated` | `sklearn` `LogisticRegression` wrapped in `CalibratedClassifierCV(sigmoid)` trained on judge winners. |
