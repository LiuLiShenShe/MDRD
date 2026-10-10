# MDRD Phase 1B — PARTIAL / INSUFFICIENT

Generated 2026-10-10T10:40:31.132450+00:00, starting HEAD `7451831706ff2da771edee4669159b0254d0503d`, report-time HEAD `7451831706ff2da771edee4669159b0254d0503d`. Real videos only; Phase 01 reports and model hashes checked, baseline manifest: `../../outputs/phase1b/baseline_manifest.json`. Recorded Phase 01 tests 35 passed; Phase 1B test result {'tests': 65, 'failures': 0, 'errors': 0, 'skipped': 0}. Environment recorded in `../../outputs/environment_report.json`; CPU COLMAP 3.9.1, PyCOLMAP 4.2.0.

## Segment validation

Real source MOV independently redecoded at every original 2 fps decoded-frame index for complete-duration low-resolution previews; labels, timestamps, frame indices, registration, full-scene points and sharpness therefore refer to the exact same image, not a nearest preview. The existing Agnes labels are *automated* candidates, not human truth. Sampling duration sums local half-second intervals, not the elapsed span across gaps. Precision/recall/F1 unavailable.

| video | 2fps LOCAL | auto candidate sampled duration s | human confirmed duration | validated near-shot count | suspected omission |
| --- | --- | --- | --- | --- | --- |
| video_007 | 7 | 3.5 | N/A — no reviewer | UNKNOWN | UNKNOWN — full contact sheet requires human review |
| video_008 | 2 | 1.0 | N/A — no reviewer | UNKNOWN | UNKNOWN — full contact sheet requires human review |
| video_020 | 2 | 1.0 | N/A — no reviewer | UNKNOWN | UNKNOWN — full contact sheet requires human review |

7/2/2 is **not independently verified**. The images exist and are registered as Phase 01 recorded; visual LOCAL completeness, false positives, same-leaf ROI identity and sub-2fps missed closeups remain UNKNOWN. Inspect `../segment_review/video_XXX/timeline.html` and the clickable contact sheet index. Reviewer should focus on the 30–60 seconds near each candidate, as well as suspected early approach intervals.

## Foreground table (verified values N/A until review)

| video | mask candidates | human verified masks | verified plant points | candidate-only plant points | candidate global-local | candidate local-only | foreground angles |
| --- | --- | --- | --- | --- | --- | --- | --- |
| video_007 | 11 | 0 | N/A — no verified masks | 361 | 69 | 189 | N/A |
| video_008 | 6 | 0 | N/A — no verified masks | 55 | 0 | 0 | N/A |
| video_020 | 0 | 0 | N/A — no verified masks | N/A — no usable masks | N/A — no usable masks | N/A — no usable masks | N/A |

## Registration ablation

| video | phase | status | input images | fixed LOCAL registered | all registered | all-scene raw tracks | verified 2D matches | same-point direction deg | verified plant tracks | Sim3 normalized RMS | time s | reason/error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| video_007 | M0 | VALIDATED_EXISTING_PHASE01_NOT_RERUN | 116 | 7/7 | 115 | 8620 | 67548 | 7.546736455522629 | N/A | N/A | N/A | N/A |
| video_007 | M1 | EXECUTED | 33 | 0/7 | 7 | 410 | 5933 | N/A | N/A | 0.011030845469985404 | 81.9 | N/A |
| video_007 | M2 | EXECUTED | 37 | 0/7 | 7 | 406 | 7653 | N/A | N/A | 0.00863886095907177 | 95.3 | N/A |
| video_007 | M3 | EXECUTED | 43 | 0/7 | 7 | 810 | 13541 | N/A | N/A | 0.005827807829393725 | 102.4 | N/A |
| video_007 | M4 | BLOCKED | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | No human-verified same-plant surface overlap pairs; deep matching comparison cannot support causal cross-scale conclusion |
| video_008 | M0 | VALIDATED_EXISTING_PHASE01_NOT_RERUN | 92 | 2/2 | 81 | 5519 | 52616 | 10.791675816718838 | N/A | N/A | N/A | N/A |
| video_008 | M1 | EXECUTED | 28 | 0/2 | 2 | 14 | 4710 | N/A | N/A | N/A | 688.7 | N/A |
| video_008 | M2 | EXECUTED | 37 | 2/2 | 29 | 1684 | 14332 | 11.983473364212392 | N/A | 0.010639126373962228 | 130.2 | N/A |
| video_008 | M3 | EXECUTED | 43 | 2/2 | 37 | 2647 | 27124 | 14.75282511889134 | N/A | 0.008164922477179369 | 101.1 | N/A |
| video_008 | M4 | BLOCKED | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | No human-verified same-plant surface overlap pairs; deep matching comparison cannot support causal cross-scale conclusion |
| video_020 | M0 | VALIDATED_EXISTING_PHASE01_NOT_RERUN | 67 | 2/2 | 67 | 17486 | 158966 | 2.200963541121061 | N/A | N/A | N/A | N/A |
| video_020 | M1 | EXECUTED | 27 | 2/2 | 26 | 5007 | 31867 | 2.1412010871923215 | N/A | 0.040973049589036345 | 96.8 | N/A |
| video_020 | M2 | EXECUTED | 31 | 2/2 | 30 | 6898 | 49106 | 2.1763216207258522 | N/A | 0.015745986118346468 | 109.9 | N/A |
| video_020 | M3 | EXECUTED | 34 | 2/2 | 33 | 9115 | 79788 | 2.377433768552566 | N/A | 0.0342504290648433 | 122.4 | N/A |
| video_020 | M4 | BLOCKED | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | No human-verified same-plant surface overlap pairs; deep matching comparison cannot support causal cross-scale conclusion |

## Evidence

| video | all-scene same points global+local | new LOCAL direction median deg | candidate image pairs | raw-match pairs | verified-match pairs | raw→verified pair retention | verified but no shared 3D track | 3D-track pairs | plant-only validated |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| video_007 | 286 | 7.546736455522629 | 6670 | 6201 | 839 | 13.5 | 19 | 1895 | N/A |
| video_008 | 149 | 10.791675816718838 | 4186 | 2993 | 762 | 25.5 | 44 | 1581 | N/A |
| video_020 | 2455 | 2.200963541121061 | 2211 | 2210 | 1220 | 55.2 | 35 | 1752 | N/A |

## H1–H4 and decision

**Engineering Status: PARTIAL. Research Evidence Status: INSUFFICIENT.** Engineering tests and synthetic fixtures do not make unverified plant masks into target truth. The video_008 M1→M2 change shows a conditional bridge effect on a **thinned, fixed** global reference. In video_020, M1 registers the same fixed LOCAL images without bridge frames; this is counterevidence against a universal bridge bottleneck. Original M0 already includes transition images, so neither case proves a new failure mode or an accuracy improvement. No cross-scale feature-match causal conclusion is available without audited overlapping plant surface pairs.

- **H1: INCONCLUSIVE**; Phase 01 full-scene per-video status: {'video_007': 'INCONCLUSIVE', 'video_008': 'INCONCLUSIVE', 'video_020': 'INCONCLUSIVE'}. Verified local ROI: N/A.
- **H2: INCONCLUSIVE**; Phase 01 full-scene per-video status: {'video_007': 'INCONCLUSIVE', 'video_008': 'INCONCLUSIVE', 'video_020': 'INCONCLUSIVE'}. Verified local ROI: N/A.
- **H3: INCONCLUSIVE**; Phase 01 full-scene per-video status: {'video_007': 'SUPPORTED', 'video_008': 'INCONCLUSIVE', 'video_020': 'INCONCLUSIVE'}. Verified local ROI: N/A.
- **H4: INCONCLUSIVE**; Phase 01 full-scene per-video status: {'video_007': 'INCONCLUSIVE', 'video_008': 'INCONCLUSIVE', 'video_020': 'INCONCLUSIVE'}. Verified local ROI: N/A.

Only one next research candidate is proposed for *validation*, not asserted as confirmed: **Does verified plant-surface bridging still fail under matched image coverage after controlling frame density and actual overlap?** It cannot yet be promoted to a new Gaussian loss/optimization algorithm.

`NO_RESEARCH_DIRECTION_CONFIRMED`

## H1 evidence audit

- FULL_SCENE_EVIDENCE: {'video_007': 'INCONCLUSIVE', 'video_008': 'INCONCLUSIVE', 'video_020': 'INCONCLUSIVE'}
- PLANT_FOREGROUND_EVIDENCE: PROVISIONAL_AUTO_ONLY_OR_MISSING
- VERIFIED_LOCAL_ROI_EVIDENCE: None
- COUNTEREVIDENCE: Phase 01 already registers most images, including all tagged local images in video_007/video_020 and registered tagged local images in video_008; no absolute 3D ground truth
- REMAINING_UNCERTAINTY: Human time intervals, plant/pot masks and matched same-leaf overlap not independently verified

## H2 evidence audit

- FULL_SCENE_EVIDENCE: {'video_007': 'INCONCLUSIVE', 'video_008': 'INCONCLUSIVE', 'video_020': 'INCONCLUSIVE'}
- PLANT_FOREGROUND_EVIDENCE: PROVISIONAL_AUTO_ONLY_OR_MISSING
- VERIFIED_LOCAL_ROI_EVIDENCE: None
- COUNTEREVIDENCE: Phase 01 already registers most images, including all tagged local images in video_007/video_020 and registered tagged local images in video_008; no absolute 3D ground truth
- REMAINING_UNCERTAINTY: Human time intervals, plant/pot masks and matched same-leaf overlap not independently verified

## H3 evidence audit

- FULL_SCENE_EVIDENCE: {'video_007': 'SUPPORTED', 'video_008': 'INCONCLUSIVE', 'video_020': 'INCONCLUSIVE'}
- PLANT_FOREGROUND_EVIDENCE: PROVISIONAL_AUTO_ONLY_OR_MISSING
- VERIFIED_LOCAL_ROI_EVIDENCE: None
- COUNTEREVIDENCE: Phase 01 already registers most images, including all tagged local images in video_007/video_020 and registered tagged local images in video_008; no absolute 3D ground truth
- REMAINING_UNCERTAINTY: Human time intervals, plant/pot masks and matched same-leaf overlap not independently verified

## H4 evidence audit

- FULL_SCENE_EVIDENCE: {'video_007': 'INCONCLUSIVE', 'video_008': 'INCONCLUSIVE', 'video_020': 'INCONCLUSIVE'}
- PLANT_FOREGROUND_EVIDENCE: PROVISIONAL_AUTO_ONLY_OR_MISSING
- VERIFIED_LOCAL_ROI_EVIDENCE: None
- COUNTEREVIDENCE: Phase 01 already registers most images, including all tagged local images in video_007/video_020 and registered tagged local images in video_008; no absolute 3D ground truth
- REMAINING_UNCERTAINTY: Human time intervals, plant/pot masks and matched same-leaf overlap not independently verified

## Explicit next-stage answers

1. Current plant-research limit: unverified LOCAL intervals, plant masks and same-surface overlap; not proven feature or geometric degeneration.
2. Repeated target failure mechanism: none established; the bridge registration response differs across the three videos.
3. Ordinary engineering fixes: source-priority protection, cache signatures, independently decoded review media and bounded bridge sampling; video_008's sparse-subset registration symptom responds to original bridge frames.
4. Residual after controlling basic variables: unresolved, since complete GLOBAL sensitivity timed out and target overlap is unverified.
5. Confirmed unique algorithmic problem: `NO_RESEARCH_DIRECTION_CONFIRMED`.
6. Geometry-Evidence-Aware Gaussian Optimization: not supported for algorithm development by the present evidence.
7. Cross-scale registration: review verified plant-surface bridging first, but do not promote it to a confirmed research direction.
8. Additional independently reviewed videos and held-out/independent geometry truth are required for causal target-quality and population-level statements.

The current limiting factor for a *scientific* plant claim is unverified segmentation/overlap, not proven cross-scale matching or Gaussian geometry degeneration. Ordinary frame selection/bridge observations may address the registration symptom in a thinned experiment, but its effect on independently verified plant geometry remains unknown. Collect human-confirmed frames/ROI masks before choosing an algorithm. Full rationale, failures and isolated logs are in `../../outputs/phase1b/reports/`.

## Required verified target quantities

| metric | video_007 | video_008 | video_020 |
| --- | --- | --- | --- |
| Effective verified plant frames | N/A — no independently verified multiview plant masks | N/A — no independently verified multiview plant masks | N/A — no independently verified multiview plant masks |
| Foreground mask verification | NONE — automatic/unavailable, no human review | NONE — automatic/unavailable, no human review | NONE — automatic/unavailable, no human review |
| Verified plant 3D points | N/A — no independently verified multiview plant masks | N/A — no independently verified multiview plant masks | N/A — no independently verified multiview plant masks |
| Verified GLOBAL–LOCAL shared plant points | N/A — no independently verified multiview plant masks | N/A — no independently verified multiview plant masks | N/A — no independently verified multiview plant masks |
| Verified LOCAL-only plant points | N/A — no independently verified multiview plant masks | N/A — no independently verified multiview plant masks | N/A — no independently verified multiview plant masks |
| Verified LOCAL triangulation angle | N/A — no independently verified multiview plant masks | N/A — no independently verified multiview plant masks | N/A — no independently verified multiview plant masks |
| Verified GLOBAL–LOCAL triangulation angle | N/A — no independently verified multiview plant masks | N/A — no independently verified multiview plant masks | N/A — no independently verified multiview plant masks |

Candidate-only values cannot fill these verified quantities. Whole-plant pixel fraction is not a same-leaf magnification ratio; no verified ROI identity exists.

## Unexecuted and failed work

M0 was hashed and reused, not independently rerun. Uniform-density supplementary SfM and M4 were not executed. The separate full-GLOBAL video_008 sensitivity check timed out during matching, so thinning remains a confounder. Automated mask coverage is incomplete, and video_020 has none. Full failure/provenance logs are retained. See `PHASE_1B_REPAIR_LOG.md` for code changes, the original synthetic-test instability, changed short-LOCAL semantics and external documentation checks. Phase 01's real-video results remain intact.
