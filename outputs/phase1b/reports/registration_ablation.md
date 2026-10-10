# Controlled Registration Ablation

M0 is preserved/hashed Phase 01 **not rerun**; its image universe includes real original approach frames. M1 is a deliberately sparse fixed GLOBAL/LOCAL **no-bridge control** (all-pairs exhaustive matching already covered by Phase 01, not a novel matching method). M2 adds only original 2 fps approach/transition observations; M3 adds selected real source frames outside the fixed target LOCAL set. M1–M3 fix the same original GLOBAL/LOCAL images and camera model/feature configuration. M4 is BLOCKED absent independently verified common plant surface overlap; preinstalled LightGlue weights are not a substitute for overlap truth.

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

For video_008, the sparse M1 registers 0/2 LOCAL and M2 registers 2/2; video_020 registers 2/2 even in M1; video_007 registers 0/7 in each thinned subset although the full M0 registers 7/7. These conflicting cases do not establish a universal bridge or feature bottleneck. Matching numbers are full-scene geometrically verified 2D correspondences, **not validated plant matches**. Only M1–M3 share a fixed target image subset; their separate reconstructions require common-camera Sim(3) alignment before comparing geometric proxies.

## Source-frame sampling policies

| video | policy | new candidate images | images in experiment | registered | target LOCAL registered | elapsed s |
| --- | --- | --- | --- | --- | --- | --- |
| video_007 | original 2 fps bridge | 0 | 37 | 7 | 0 | 95.3 |
| video_007 | uniform 4 fps candidate (SfM not run) | 14 | N/A | N/A | N/A | N/A |
| video_007 | adaptive from 8 fps candidate | 6 | 43 | 7 | 0 | 102.4 |
| video_008 | original 2 fps bridge | 0 | 37 | 29 | 2 | 130.2 |
| video_008 | uniform 4 fps candidate (SfM not run) | 14 | N/A | N/A | N/A | N/A |
| video_008 | adaptive from 8 fps candidate | 6 | 43 | 37 | 2 | 101.1 |
| video_020 | original 2 fps bridge | 0 | 31 | 30 | 2 | 109.9 |
| video_020 | uniform 4 fps candidate (SfM not run) | 7 | N/A | N/A | N/A | N/A |
| video_020 | adaptive from 8 fps candidate | 3 | 34 | 33 | 2 | 122.4 |

Uniform 4 fps is a decoded-candidate audit, **not** a completed SfM reconstruction; registration/cost are N/A. Adaptive frames are outside the fixed target LOCAL set, so their registration cannot be conflated with target-local registration. Selection is provisional until the time intervals and plant overlap are reviewed.

Do not interpret raw track counts, training reprojection residual or success on a thinned reference set as target reconstruction accuracy. Candidate model Pareto tables (registered coverage, tracks, reprojection, intrinsics, bridge) and all failed candidates are retained under `ablations/video_XXX/model_audit` and each M*/sfm. Sim(3) compares common camera centers only, not unverified point correspondences.

## M4 implementation/permission audit

Checked the official LightGlue README (`https://github.com/cvg/LightGlue/blob/main/README.md`): it supports SIFT and SuperPoint features, but explicitly notes different, restrictive licensing for SuperPoint weights/inference; do not assume the latter can be redistributed. The official COLMAP database format (`https://github.com/colmap/colmap/blob/main/doc/database.rst`) separates raw `matches` from geometry-verified `two_view_geometries`, and reconstruction consumes the latter. The installed CPU COLMAP 3.9.1 integration with a newly selected matcher has **not** been validated here. Do not import raw neural matches as ground-truth correspondences. M4 was not run because no human-verified same-surface overlap pairs exist; no GPU runtime or VRAM measurements are claimed.

## Failed full-GLOBAL sensitivity check

To check whether thinning the GLOBAL set confounds M1, a separate video_008 run retains all 81 original GLOBAL and 2 original LOCAL frames, omitting only original APPROACH/TRANSITION images. The CPU exhaustive matching command timed out at its predeclared 240-second bound; no registration result is available. Status: FAILED. Error: `RuntimeError: Command returned -124: see outputs/phase1b/ablations/video_008/full_global_no_bridge/sfm/logs/exhaustive_matcher.log`. Logs/configuration remain in `ablations/video_008/full_global_no_bridge`. Do **not** interpret this computational timeout as feature or geometric failure. Full-GLOBAL sensitivity remains unresolved.
