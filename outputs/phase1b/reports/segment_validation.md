# Phase 1B Segment Validation

Real source MOV independently redecoded at every original 2 fps decoded-frame index for complete-duration low-resolution previews; labels, timestamps, frame indices, registration, full-scene points and sharpness therefore refer to the exact same image, not a nearest preview. The existing Agnes labels are *automated* candidates, not human truth. Sampling duration sums local half-second intervals, not the elapsed span across gaps. Precision/recall/F1 unavailable.

| video | 2fps LOCAL | auto candidate sampled duration s | human confirmed duration | validated near-shot count | suspected omission |
| --- | --- | --- | --- | --- | --- |
| video_007 | 7 | 3.5 | N/A — no reviewer | UNKNOWN | UNKNOWN — full contact sheet requires human review |
| video_008 | 2 | 1.0 | N/A — no reviewer | UNKNOWN | UNKNOWN — full contact sheet requires human review |
| video_020 | 2 | 1.0 | N/A — no reviewer | UNKNOWN | UNKNOWN — full contact sheet requires human review |

7/2/2 is **not independently verified**. The images exist and are registered as Phase 01 recorded; visual LOCAL completeness, false positives, same-leaf ROI identity and sub-2fps missed closeups remain UNKNOWN. Inspect `../segment_review/video_XXX/timeline.html` and the clickable contact sheet index. Reviewer should focus on the 30–60 seconds near each candidate, as well as suspected early approach intervals.
