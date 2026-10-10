# 三样本科研假设审计

不合并独立模型的绝对基线；逐视频/片段与时间块描述，避免把数千个相关图像对当成独立重复实验。

H1 需要可靠目标区域像素覆盖；H4 需要控制真实重叠及模糊，不能仅由注册率下结论。


## H1

| video_id | status | valid_points |
| --- | --- | --- |
| video_007 | INCONCLUSIVE | 7227 |
| video_008 | INCONCLUSIVE | 4566 |
| video_020 | INCONCLUSIVE | 14991 |

- video_007: No verified plant mask or correspondence-defined leaf ROI: increased target pixel coverage cannot be established. Ray angles are not reconstruction-accuracy measurements. 详见该视频 `../video_007/report/diagnosis.md` 的真实数值及样本数。

- video_008: No verified plant mask or correspondence-defined leaf ROI: increased target pixel coverage cannot be established. Ray angles are not reconstruction-accuracy measurements. 详见该视频 `../video_008/report/diagnosis.md` 的真实数值及样本数。

- video_020: No verified plant mask or correspondence-defined leaf ROI: increased target pixel coverage cannot be established. Ray angles are not reconstruction-accuracy measurements. 详见该视频 `../video_020/report/diagnosis.md` 的真实数值及样本数。


## H2

| video_id | status | valid_points |
| --- | --- | --- |
| video_007 | INCONCLUSIVE | 7227 |
| video_008 | INCONCLUSIVE | 4566 |
| video_020 | INCONCLUSIVE | 14991 |

- video_007: Descriptive full-scene recovered-feature evidence only. Thresholds are declared diagnostics, not universal geometry/accuracy limits. Blocks share frames/tracks; not independent population samples. Primary H2 decision uses same-local-segment pairs at <=3 s lag. COLMAP min triangulation angle and successful-registration selection censor unreconstructed/weak observations; NOT_SUPPORTED applies only to recovered-feature evidence. 详见该视频 `../video_007/report/diagnosis.md` 的真实数值及样本数。

- video_008: Descriptive full-scene recovered-feature evidence only. Thresholds are declared diagnostics, not universal geometry/accuracy limits. Blocks share frames/tracks; not independent population samples. Primary H2 decision uses same-local-segment pairs at <=3 s lag. COLMAP min triangulation angle and successful-registration selection censor unreconstructed/weak observations; NOT_SUPPORTED applies only to recovered-feature evidence. 详见该视频 `../video_008/report/diagnosis.md` 的真实数值及样本数。

- video_020: Descriptive full-scene recovered-feature evidence only. Thresholds are declared diagnostics, not universal geometry/accuracy limits. Blocks share frames/tracks; not independent population samples. Primary H2 decision uses same-local-segment pairs at <=3 s lag. COLMAP min triangulation angle and successful-registration selection censor unreconstructed/weak observations; NOT_SUPPORTED applies only to recovered-feature evidence. 详见该视频 `../video_020/report/diagnosis.md` 的真实数值及样本数。


## H3

| video_id | status | valid_points |
| --- | --- | --- |
| video_007 | SUPPORTED | 7227 |
| video_008 | INCONCLUSIVE | 4566 |
| video_020 | INCONCLUSIVE | 14991 |

- video_007: A mixed reconstructed track with non-collinear rays is an actual geometric correspondence, not merely potential overlap. Fewer than four independently observed local images is insufficient for a supported H3 judgment. Target-specific gain and final surface accuracy remain untested. 详见该视频 `../video_007/report/diagnosis.md` 的真实数值及样本数。

- video_008: A mixed reconstructed track with non-collinear rays is an actual geometric correspondence, not merely potential overlap. Fewer than four independently observed local images is insufficient for a supported H3 judgment. Target-specific gain and final surface accuracy remain untested. 详见该视频 `../video_008/report/diagnosis.md` 的真实数值及样本数。

- video_020: A mixed reconstructed track with non-collinear rays is an actual geometric correspondence, not merely potential overlap. Fewer than four independently observed local images is insufficient for a supported H3 judgment. Target-specific gain and final surface accuracy remain untested. 详见该视频 `../video_020/report/diagnosis.md` 的真实数值及样本数。


## H4

| video_id | status | valid_points |
| --- | --- | --- |
| video_007 | INCONCLUSIVE | 7227 |
| video_008 | INCONCLUSIVE | 4566 |
| video_020 | INCONCLUSIVE | 14991 |

- video_007: Cross-scale verified SIFT size ratios and match/registration rates are observed, but real overlap, motion blur, texture repetition and non-rigidity are not controlled. Failure alone cannot identify a scale mechanism. Verified-pair scale ratios are survivor-biased. 详见该视频 `../video_007/report/diagnosis.md` 的真实数值及样本数。

- video_008: Cross-scale verified SIFT size ratios and match/registration rates are observed, but real overlap, motion blur, texture repetition and non-rigidity are not controlled. Failure alone cannot identify a scale mechanism. Verified-pair scale ratios are survivor-biased. 详见该视频 `../video_008/report/diagnosis.md` 的真实数值及样本数。

- video_020: Cross-scale verified SIFT size ratios and match/registration rates are observed, but real overlap, motion blur, texture repetition and non-rigidity are not controlled. Failure alone cannot identify a scale mechanism. Verified-pair scale ratios are survivor-biased. 详见该视频 `../video_020/report/diagnosis.md` 的真实数值及样本数。