# Phase 1B implementation and verification record

## Baseline protection

Actual starting HEAD/branch: `7451831706ff2da771edee4669159b0254d0503d` / `main`. The real source MOV files and the three Phase 01 COLMAP models exist locally. `outputs/phase1b/baseline_manifest.json` is retained, not recomputed after modifications. Real-video Phase 01 report/model/diagnosis hashes are verified again by the Phase 1B report command. Media and binary models are excluded from Git. Following the baseline manifest's clean-before-test receipt, tracked Phase 01 synthetic fixture text outputs were restored and untracked regenerated synthetic logs removed; ignored media and binary fixture files remain local. Final test fixtures are isolated under Phase 1B. Existing code changes were retained and included in the Phase 1B patch, not discarded.

## Fixed bugs

- Authoritative HUMAN_VERIFIED, MANUAL_OVERRIDE and EXTERNAL_VERIFIED_ANNOTATION sources outrank automatic image/geometry/vision labels; verified imports require provenance. Short LOCAL runs survive generic temporal smoothing. Refinement records before/after labels and reasons.
- Stage receipts hash actual image contents, overrides, labels, database and selected model artifacts as appropriate. Output hashes prevent reuse of missing/modified results. Dynamically discovered SfM model outputs are recorded on the first completed run, preventing an unnecessary immediate rerun.
- Reporting templates are excluded from SfM/analyze and foreground signatures; mask changes affect foreground analysis, not source extraction. Phase 1B CLI commands do not rewrite Phase 01's `last_run_configuration.json`.
- Candidate models retain the max-registration baseline and a separate multi-indicator Pareto audit. Valid point filtering, stage coverage, reprojection distributions, tracks, intrinsics, trajectory proxies and unbridged LOCAL observations are recorded without an arbitrary weighted accuracy score.
- Foreground classification requires at least two consistent camera observations. Conflict, missing and out-of-bounds evidence is UNCERTAIN. A point classified from GLOBAL masks does not automatically become a supported LOCAL foreground observation when its LOCAL mask is absent.
- Mask manifests cannot make an automatic proposal human-verified by returning a `human_confirmed`/`source` field in a model response. Imported verified masks require an authoritative source and named reviewer; supplied image/mask hashes must agree.
- Empty masks produce readable, header-only CSVs and N/A geometric summaries. Exact source-index preview extraction removes the previous nearest-preview timestamp ambiguity. Offline timelines require no third-party JavaScript bundle.

## Genuine limits and failures

Agnes returned malformed responses or rate limits for multiple frames, including all requested video_020 prompts. These failures remain in `prompt_proposals.json`. No mask or segment has been marked human verified. Video_008 has no usable LOCAL masks, so zero supported cross-stage foreground observations cannot establish zero actual target overlap.

M1–M3 were genuinely run for all three samples after video_008. Their fixed GLOBAL reference is thinned, which limits causal interpretation. A separate full-GLOBAL video_008 no-bridge sensitivity check failed because CPU exhaustive matching exceeded its 240-second command bound. No registration failure is inferred from this timeout. M0 is preserved/hashed, not an independently repeated reconstruction; uniform 4 fps supplementary candidates were decoded but not reconstructed separately. M4 is BLOCKED without reviewed same-plant-surface overlap. These are not substituted with synthetic results.

An early pre-integration run of the original synthetic SfM test produced only three registered cameras and failed its original >=6 assertion. A subsequent reproduction and later full suites passed; the assertion was not weakened. Both receipts remain in `outputs/phase1b/tests/integration_preintegration.xml` and `integration_repro.xml`. Final external-test runs use `outputs/phase1b/tests/fixtures`; `MDRD_TEST_OUTPUT_ROOT` and `MDRD_SYNTHETIC_SOURCE_ROOT` can explicitly relocate fixtures without changing their numerical assertions. The synthetic foreground integration uses known-scene tracks and test stage assignments; it is not a real plant, real near-shot validation, or a substitute for a full mixed-distance plant ground-truth scene.

The instability recurred in a final suite (3/8 images, 8 points), so it was not hidden as an isolated success. The saved `selfcalibration_failure.xml`/`.log` retain the failure. The fixture has known focal=580, principal point=(320,240), distortion=0; unconstrained self-calibration produced focal=1108 in the failed run and focal=5.55 in an earlier numerically passing run. This makes the old fixture's intrinsic accuracy unchecked. Fixed only the synthetic test configuration to hold known intrinsics during mapper, registration, triangulation and final bundle adjustment; declared seed=731 for geometrical randomness. Added an exact intrinsic consistency assertion. Original >=6 images, >30 points, trajectory .12 and angle 1e-8 assertions are unchanged. No real-video calibration or experiment setting is modified. COLMAP's official fixed-intrinsics guidance was checked via Context7, and every option exists in installed COLMAP 3.9.1 help.

Two original `test_segment_empty_single_and_boundaries` assertions intentionally change: they previously expected a one-frame LOCAL run to become GLOBAL/UNKNOWN, contradicting the explicit Phase 1B requirement not to delete LOCAL solely because it is short. They now assert the exact retained LOCAL sequence. Empty/boundary checks and numerical SfM/geometry tolerances remain unchanged; additional source-priority and short-run regressions justify the semantic change.

## Documentation checks

PyCOLMAP and LightGlue API documentation was retrieved through Context7. LightGlue permissions/features and COLMAP verified-database semantics were checked against the projects' official sources. Bocha search returned an authorization denial; it was not treated as successful web research. No API credentials are stored in repository artifacts.

Engineering acceptance and research readiness remain separate. Until independent segment/plant/ROI review is available, no Gaussian optimization or cross-scale registration research direction is confirmed.
