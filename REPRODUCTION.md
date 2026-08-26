# Reproduction plan: one branch per measured slide

Status as of 2026-08-26. This is a planning document, not yet acted on —
branch creation/cleanup is deliberately left as TODO work (see note at the
bottom on why `steps/OnePredict.cc` needs attention before any of this is
final).

Each row is a slide (or slide group) in `slides.qmd` that cites a measured
number, the branch that should reproduce it, and what state that branch is
actually in today.

| slide(s) | what it needs | branch | base | status |
|---|---|---|---|---|
| 4 — original work distribution (1,161s/1,612s/66,623s/41.3×) | upstream `OnePredict`, `StaticFor` | `figures/baseline-instrumented` | `d1005c27` | **exists**, but `presentation_data/BRANCHES.md` notes it was still "build in progress, verifying it compiles" last time it was touched — re-verify before trusting it as the reproduction source. The actual cited numbers came from `build-fast/slurm-threeway-65941437.out` (an older, separately-run three-way comparison), not yet re-confirmed against this branch's own build. |
| 5 — core-cycle imbalance, scaling table | same, `StaticFor` | `figures/baseline-instrumented` | `d1005c27` | **exists**, data already collected in `presentation_data/baseline_analysis/` and `presentation_data/baseline_vtune/`. |
| 6 — per-thread histogram | same, `StaticFor`, `debuglevel=2` | `figures/baseline-instrumented` | `d1005c27` | **exists**, `presentation_data/baseline_analysis/histogram_raw.log`. |
| 7 — TBB attempt, approach | (no data, description only) | — | — | n/a |
| 8 — TBB attempt, results (7–25% faster than baseline) | TBB `parallel_for`, per-source granularity, **with the buffer-resize fix** (removes the per-call `PredictBuffer::Resize()`, replaces it with a per-patch beam cache in per-thread scratch) | **TODO — does not exist as a commit yet.** Currently sitting **uncommitted** in the `rebase-onto-upstream` working tree (`git status` shows `M steps/OnePredict.cc`, `M steps/OnePredict.h`, `M steps/OnePredictNew.cc`). See note below. | should branch from `d1005c27` | not committed |
| 9 — memory traffic / L3 misses, "before" side | same fixed TBB build as slide 8 | same TODO branch as slide 8 | `d1005c27` | not committed; measured today directly against the uncommitted working tree (`presentation_data/tbb_memory_access/`) |
| 9 — memory traffic / L3 misses, "after" side | tiled `OnePredictNew`, current HEAD | `rebase-onto-upstream` | `d1005c27`..HEAD | **exists** (it's just current HEAD); measured today in `presentation_data/final_memory_access/` |
| 10 — tiling concept diagram | (no data, conceptual figure) | — | — | n/a |
| 11 — impact of new layout alone (1,161s → 562s) | tiled dispatch, **before** split-planes/slab-rounding/SIMD | `rebase-onto-upstream` at `3e439717` (last tiling-only commit, right before `9fc2a064`/`30fea0ad` touch the accumulator) | `d1005c27`'s ancestor at that point | **exists** as a real commit already in history — just needs a build+run, not a new branch |
| 12 — split real/imaginary planes (562s → 547s) | + `62c44168` | `rebase-onto-upstream` at `62c44168` | — | **exists**, real commit |
| 13 — slab sizing / AVX-512 (547s → 529s) | + `cd6f63fb` | `rebase-onto-upstream` at `cd6f63fb` | — | **exists**, real commit |
| 14 — SIMD `sincos` (529s → ~337s) | + `5c9ff19e` (and `d1005c27` for the unrelated numthreads fix, no-op at 72 threads) | `rebase-onto-upstream` at `5c9ff19e` or current HEAD | — | **exists**, real commit |
| 15 — final scaling (2→72 threads, 67% efficiency) | tiled `OnePredictNew`, current HEAD | `rebase-onto-upstream` | HEAD (`d1005c27`) | **exists**, current HEAD; `presentation_data/tbb_global_control_fix/` |
| 16 — conclusion | (no new data) | — | — | n/a |

## Why this needs attention before it's "done"

`steps/OnePredict.cc` is supposed to stay the pristine `StaticFor` baseline
on `rebase-onto-upstream` — it's the thing slides 4–6 compare against. The
TBB buffer-resize fix behind slides 8–9 was written directly into that same
file, on this same branch, uncommitted. Two consequences:

1. As long as it stays uncommitted, nothing about it is reproducible from a
   clean checkout — a fresh clone of `rebase-onto-upstream` does not
   reproduce the slide 8/9 numbers.
2. If it were committed as-is on `rebase-onto-upstream`, `OnePredict.cc`
   would stop being the `StaticFor` baseline on this branch, which would
   break reproducibility for slides 4–6 instead.

**The TODO**: cut a dedicated branch (name not yet decided — candidates:
`figures/attempt2-tbb-fixed`, or extend the existing
`figures/attempt2-tbb-source-parallel` branch with one more commit) from
`d1005c27`, commit the current working-tree diff there, and then decide
whether `rebase-onto-upstream`'s own `OnePredict.cc` should be reverted back
to the pristine baseline it was before this session's edits. Left for you to
do — this document just records what state things need to end up in.
