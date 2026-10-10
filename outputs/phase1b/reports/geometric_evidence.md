# Geometric Evidence and Attrition

| video | all-scene same points global+local | new LOCAL direction median deg | candidate image pairs | raw-match pairs | verified-match pairs | raw→verified pair retention | verified but no shared 3D track | 3D-track pairs | plant-only validated |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| video_007 | 286 | 7.546736455522629 | 6670 | 6201 | 839 | 13.5 | 19 | 1895 | N/A |
| video_008 | 149 | 10.791675816718838 | 4186 | 2993 | 762 | 25.5 | 44 | 1581 | N/A |
| video_020 | 2455 | 2.200963541121061 | 2211 | 2210 | 1220 | 55.2 | 35 | 1752 | N/A |

Raw→verified is the fraction of *image pairs with at least one match*, not individual feature-match retention. Full-scene measurements compare the **same** recovered 3D point's GLOBAL and LOCAL camera rays in one SfM gauge. Pair counts are correlated and raw/verified two-view matches do not map one-to-one to reconstructed point tracks; 3D-track pairs are **not** a subset of geometrically verified two-view pair entries. The pair CSV retains each stage separately; pairs with verified 2D matches but no common 3D track are not interpreted as lacking real geometry. Weak triangulation is not inferred from an arbitrary threshold. Foreground-specific unmatched 2D evidence and true surface accuracy are N/A because reliable masks and ROI identity are absent. Information-matrix helper is optional and not used for hypothesis support; correlated frames and camera-pose uncertainty preclude interpreting eigenvalues as true 3D covariance.
