# Plant versus Full-Scene Geometry

COLMAP full-scene feature tracks must not be represented as plant geometry. Three-class 8-bit masks: 0=UNCERTAIN, 1=PLANT_FOREGROUND, 2=BACKGROUND; exact COLMAP image dimensions and multiview voting required. Automatic Agnes box + cached SAM ViT-B produced **provisional, not human-verified** masks; unknown background/pot areas intentionally remain UNCERTAIN. SAM score is not true IoU. Failed HTTP 429/vision parsing is preserved in each prompt manifest.

| video | mask candidates | human verified masks | verified plant points | candidate-only plant points | candidate global-local | candidate local-only | candidate LOCAL angle deg | candidate G-L angle deg | candidate track median | candidate reproj median | verified foreground angles |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| video_007 | 11 | 0 | N/A — no verified masks | 361 | 69 | 189 | 4.778154573817808 | 23.163385941750708 | 4.0 | 1.7001229846083836 | N/A — mask/ROI not verified |
| video_008 | 6 | 0 | N/A — no verified masks | 55 | 0 | 0 | N/A | N/A | 5.0 | 1.580716711080547 | N/A — mask/ROI not verified |
| video_020 | 0 | 0 | N/A — no verified masks | N/A — no usable masks | N/A — no usable masks | N/A — no usable masks | N/A | N/A | N/A | N/A | N/A — mask/ROI not verified |

No real same-leaf ROI correspondences or mask ground truth. Candidate-only values are exploratory and must not be used to support H1–H4. Representative RGB/mask overlays and point-level provenance reside locally under each foreground folder. Human corrections can be imported with three-class pixel masks, a reviewer ID and unchanged COLMAP image orientation.

video_008 has no masked LOCAL images: its zero supported cross-stage foreground observations do **not** imply zero actual plant overlap. video_020 has no usable masks: all plant-specific geometric quantities are N/A, **not zero**. Per-frame candidate pixel fractions and feature density are in `foreground/video_XXX/per_image_foreground.csv`; the mask checklist records unresolved clipping, pot and blur risks.

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
