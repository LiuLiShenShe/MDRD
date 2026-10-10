# Failures and repairs

## 2026-10-09 — initial real SfM attempt
All three initial attempts reached feature extraction but COLMAP 3.9.1 rejected the decoded 16-bit RGB PNG format. The extractor returned zero usable images; the matcher then aborted. Evidence: each `outputs/video_*/sfm_previous/logs/{feature_extractor,exhaustive_matcher}.log` and stage history. No registration or geometry result was claimed for this attempt.

Repair: keep original scientific PNG files unmodified, create separate `sfm_images/` with deterministic uint16→uint8 (`>> 8`) conversion and no tone-map/crop/resize, record both hashes, dtype and dimensions in `sfm/sfm_image_manifest.csv`, and abort explicitly when fewer than two images have usable features. Failed SfM directories are archived before rerunning.

## 2026-10-09 — empty-evidence test
A boolean selection expressed as an empty list dropped all DataFrame columns. Unit test `test_empty_evidence_does_not_support_hypotheses` caught the resulting missing `registered` column. Repair: use a typed Pandas boolean Series and `.loc`, retaining schema and INCONCLUSIVE on empty evidence. Original failing JUnit/log files are preserved before retesting.

## 2026-10-09 — concurrent CLI receipts
The three-process retry collided on the fixed `.tmp` filename used by the shared `last_run_configuration.json`. One process failed before its SfM run, not during geometric estimation. Repair: unique UUID temporary files with atomic rename; add a 40-write concurrent regression test. Individual stage histories and command logs remain the provenance authority; the shared `last_run` file is only a convenience receipt.

## 2026-10-09 — short reviewed local runs and empty H3 evidence

The initial 3D refinement applied the generic short-run smoother to already source-provenanced visual labels. It converted the reviewed 2–3-frame LOCAL runs in video_008 and video_020 into UNKNOWN, understating their near-view evidence. The final repair smooths only automatic labels, retains the raw automated review and its independent version, and adds a regression test. H3 requires at least four registered LOCAL images before a supported judgment; two-frame evidence is inconclusive. A further unit test initially failed on the H3 empty-camera case after adding this guard; the function now treats missing camera evidence as an empty sequence rather than assuming a pose. Original failing JUnit output is preserved in `outputs/tests/unit_results_final2.xml`.

## 2026-10-09 — ambiguous automated near-view labels

An initial automated frame reviewer labeled video_008 frames 7–9 and 85–87 LOCAL even though its descriptions mentioned an intact pot/whole plant. A separate targeted Agnes image review of frames 6–10 and 84–88 found frames 7–10 and 85–86 retain GLOBAL context; only frames 87–88 lacked full context. The two API outputs and comparison image are preserved in `outputs/video_008/segments/visual_review/`; the original first-pass overrides are in `outputs/video_008/segments/visual_review_overrides_initial.json`. Revised labels/previous labels and correction provenance reside in `outputs/video_008/segments/visual_review_overrides.json`, with original 2D automatic labels retained in `segments/versions/`. Both passes remain automated vision proxies, not human ground truth or measured camera distance. Re-run segmentation, SfM, analysis and report after this change.

## 2026-10-10 — test receipt parsing

The first final JUnit aggregation script read only the XML root attributes, but pytest emits a `<testsuites>` wrapper with actual counts inside `<testsuite>`. It wrongly wrote zero tests despite `33 passed` and `2 passed` in the untouched test logs and XML. This was a reporting bug, not a test failure. `scripts/summarize_tests.py` now traverses test suites, rejects a zero-test receipt, writes the verified 35-test summary, and the final acceptance report is regenerated. Earlier zero-count receipt remains traceable in `outputs/logs/final_report_verified.log` and stage histories; the corrected report is the acceptance source of truth.
