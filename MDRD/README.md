# MDRD — Mixed-Distance Reconstruction Diagnostics

A runnable, auditable first-phase diagnosis of real mixed-distance videos. No plant taxonomy, invented scale, fabricated poses, or new Gaussian-Splatting training algorithm.

## Paths and isolation

The workspace is `PROJECT_ROOT`; real inputs are in `PROJECT_ROOT/原始视频`; all experimental outputs are in `PROJECT_ROOT/outputs`. `MDRD/outputs` links to that directory. `PROJECT_ROOT/docs` links to `MDRD/docs`. The `.venv` uses `--system-site-packages` to read installed scientific packages without modifying them; MDRD itself is installed only into that virtual environment. Installed versions are captured in `outputs/environment_report.json`. To create an entirely independent installation, use the recorded requirements and a compatible Python environment, not the system site packages.

```bash
cd /fj/混合拍摄距离下的三维重建优化问题
python -m venv --system-site-packages .venv
.venv/bin/python -m pip install --no-deps --no-build-isolation -e MDRD
.venv/bin/mdrd inspect --input 原始视频 --preview
.venv/bin/mdrd run-all --samples video_007 video_008 video_020
```

The three-video SfM guard is intentional. Inspect/preview may read all inputs; full SfM never implicitly processes all 20. Sample IDs refer to sorted source file inventory, not unique plants or classes. See `outputs/selection.json`.

## Independently runnable stages

```bash
.venv/bin/mdrd extract --samples video_008 --fps 2 --format png
.venv/bin/mdrd quality --samples video_008
.venv/bin/mdrd segment --samples video_008
.venv/bin/mdrd sfm --samples video_008 --camera-model SIMPLE_RADIAL
.venv/bin/mdrd analyze --samples video_008
.venv/bin/mdrd report --samples video_007 video_008 video_020
.venv/bin/mdrd run-all --samples video_008 --rerun-stage quality segment analyze
```

Common options: `--config PATH`, `--output PATH`, `--input DIR`, `--video FILE`, `--samples ID ...`, `--force`, `--no-reuse`, `--rerun-stage STAGE ...`. Sampling accepts `--fps`, `--interval`, `--target-count`, `--max-images`, PNG/JPEG. `--colmap` selects the executable; version-specific extra options are placed in the YAML `sfm.extra_options` keyed by command. Unsupported installed CLI flags are rejected. YAML controls feature limits, matching density and geometry filters.

Stage receipts use input/parameter/code hashes. Successful unchanged stages resume. Missing scientific inputs or a failed command are errors, never silently synthetic substitutes. `sfm_previous` / `sfm_history` and command-log histories preserve failed attempts. `last_run_configuration.json` is only a latest convenience receipt; stage receipts and command logs are authoritative.

## Labels and overrides

The automatic 2D labels are **candidates**, not proof of distance or a complete orbit. Originals and timestamped override histories remain in `segments/versions/`. A CSV or JSON override has `start_timestamp_sec,end_timestamp_sec,label,confidence,source`; apply with:

```bash
.venv/bin/mdrd segment --samples video_008 --override path/to/annotations.json --force
```

An optional visual API reviewer is implemented in `scripts/review_segments.py`. Set `AGNES_API_KEY` in the environment; no API key is stored in source. The outputs are clearly marked **automated image-content review, not human ground truth**. API errors and rate limits are persisted, not converted into guessed labels. The final geometry labels mark 3D-supported proxies versus unregistered temporal inference. There is no reliable gravity/plant mask, so TOP labels are not invented.

## Adaptive supplementation

`analyze` writes a bounded proposal of actual timeline locations at failed registration, high 2D motion, label boundaries and low adjacent matches. It does not promise success. Preserve the baseline run before applying a second experiment:

```bash
.venv/bin/mdrd extract --samples video_008 --supplemental-times outputs/video_008/geometry/adaptive_supplement_proposal.json --force
```

The extractor merges baseline selected decoded-frame indices with nearest **actual** decoded source PTS; it does not indiscriminately ingest all frames. Run downstream stages after any supplementation. For fair ablations, use separate output roots and preserve baseline results/logs.

## Phase 1B: audited plant geometry and registration controls

The original Phase 01 outputs remain in `outputs/video_XXX`; the frozen hashes and original test status are in `outputs/phase1b/baseline_manifest.json`. Phase 1B outputs are isolated under `outputs/phase1b/` and never turn provisional vision proposals into human ground truth. Run `video_008` first for supplementary extraction and ablation:

```bash
.venv/bin/mdrd review-segments --samples video_007 video_008 video_020
.venv/bin/mdrd foreground --samples video_008
.venv/bin/mdrd supplement --samples video_008 --densities 4 8
.venv/bin/mdrd ablate-registration --samples video_008
.venv/bin/mdrd evidence --samples video_007 video_008 video_020
.venv/bin/mdrd phase1b-report --samples video_007 video_008 video_020
```

`review-segments` creates complete-duration low-resolution source-video previews, interactive offline timelines, and separate `reviewed_segments.json` proposals. Review `outputs/phase1b/segment_review/video_XXX/timeline.html`, then independently annotate candidate LOCAL intervals and corresponding plant surfaces. The `foreground` command accepts `--override PATH` for a manifest of externally reviewed three-class masks; `--checkpoint PATH` uses installed SAM with existing automated box proposals, **not** verified segmentations. Missing masks yield UNCERTAIN, never an all-image foreground. The original 2 fps frames are fixed across M1–M3; M2 adds 2 fps bridge frames and M3 selected source-video transition candidates. M0 is the hashed Phase 01 reference, already matched exhaustively; M4 must remain blocked until same-surface overlap is confirmed. Read `docs/PHASE_1B_FINAL_REPORT.md` for the exact status, failures, and the distinction between engineering and research acceptance. Preview images, MOVs, COLMAP databases/models, and segmentation checkpoints remain local and are excluded from Git; regenerate media from the hashed original inputs.

## Tests and scientific reading

```bash
.venv/bin/python -m pytest MDRD/tests -q --junitxml=outputs/tests/all_results.xml
```

The final acceptance report reads `outputs/tests/test_summary.json`. To reproduce its unit/integration counts from separate JUnit files, run `MDRD/scripts/summarize_tests.py --unit outputs/tests/unit_results_verified.xml --integration outputs/tests/integration_results_verified.xml --output outputs/tests/test_summary.json` using `.venv/bin/python` before `mdrd report --samples video_007 video_008 video_020`.

Unit tests check camera centers, coordinate conventions, projection/inverse, true common-point ray angles, scale invariance, missing/empty/unregistered data, observation filtering, timestamp mapping, segmentation boundaries, overrides and concurrent receipts. Integration tests execute FFmpeg on a explicitly synthetic VFR fixture, COLMAP on a seeded known-trajectory noncoplanar scene, read its model, align its recovered gauge, calculate common-point geometry and generate a report. Synthetic fixtures are confined to `outputs/tests` and never counted as real video experiments.

Read `docs/METHODS.md`, `docs/METRICS.md`, `docs/REPAIR_LOG.md`, and `docs/PHASE_01_FINAL_REPORT.md`. Raw movies are never modified. Sparse full-scene covisibility is not plant surface visibility; no target masks or reference geometry means plant-specific pixel-coverage/accuracy hypotheses may remain INCONCLUSIVE.
