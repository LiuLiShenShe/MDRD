# video_007：真实视频诊断

生成时间：2026-10-09T16:27:59.022994+00:00；源视频 `2026-02-11 151247.mov`；SHA-256 `ca889fb3f50652d80ee4109850c78e43a3662b563df3cabab05cc8d67d52af21`。


## 数据与质量

时长 57.988 s；抽帧 116 张；8-bit 全图清晰度代理标签：{'CLEAR': 107, 'MILD_BLUR': 9}。没有植物目标掩码，不能把这些标签视为已标定的运动模糊真值。

最终连续片段 8；局部片段标签不是叶片实例 ID；UNKNOWN 不强制填补。


## SfM 与失败

模型策略：`GLOBAL_FIRST_REGISTRATION_AND_INCREMENTAL_CONTINUATION`。已注册 115/116；稀疏点 8620，分析过滤后 7227；平均/中位点重投影误差 1.424/1.397 px。

| segment | total | registered | registration_rate |
| --- | --- | --- | --- |
| APPROACH | 3 | 3 | 1.000 |
| GLOBAL | 105 | 105 | 1.000 |
| LOCAL_01 | 2 | 2 | 1.000 |
| LOCAL_02 | 5 | 5 | 1.000 |
| TRANSITION | 1 | 0 | 0.000 |

基础 GLOBAL 候选 105；基础模型实际数量 2；每个模型文件、注册名单与内参记录在 `../sfm/sfm_summary.json`。保留全部未注册图像，PnP 内点缺失为 N/A；有证据不足的原因均为 UNKNOWN。

过滤审计：{'nonfinite_or_high_point_error': 0, 'short_track': 1371, 'invalid_association': 0, 'nonpositive_depth': 0, 'high_observation_error': 57, 'short_after_filter': 22}。焦距与畸变参数为实测 BA 输出，不等同物理标定。背景依赖尚未用掩码验证。


## 几何统计

| 指标 | GLOBAL_GLOBAL | LOCAL_LOCAL | GLOBAL_LOCAL |
| --- | --- | --- | --- |
| 有效图像对数（非独立样本） | 502 | 11 | 7 |
| 时间块对数（仍有关联） | 66 | 4 | 4 |
| 中位基线深度比（无量纲） | 0.183 | 0.201 | 0.196 |
| 中位三角化角（°） | 9.133 | 4.776 | 4.308 |
| 有效共视点数（图像对中位数） | 55.000 | 69.000 | 27.000 |
| 共视 Jaccard | 0.118 | 0.343 | 0.127 |
| 方向覆盖 i→j | 0.227 | 0.585 | 0.239 |
| 方向覆盖 j→i | 0.221 | 0.500 | 0.221 |
| 观测重投影误差中位数（px） | 1.548 | 1.503 | 1.418 |


N/A 表示无足够有效共同点/对应标签或未注册；不是零角度。表为图像对中位数，不做独立样本检验。绝对基线仅限本模型相对单位；跨视频只比较比值/角度。


## H1–H4


### H1: INCONCLUSIVE

No verified plant mask or correspondence-defined leaf ROI: increased target pixel coverage cannot be established. Ray angles are not reconstruction-accuracy measurements.

实测证据：

```json

{
  "target_pixel_coverage": null,
  "local_pair_angle_median_deg": 4.776182321648626,
  "global_pair_angle_median_deg": 9.133291131789743,
  "local_only_reconstructed_points": 126,
  "shared_global_local_points": 286
}

```

进一步验证：Validate foreground/leaf ROI correspondences and target pixel coverage; obtain reconstruction accuracy or a reference surface.


### H2: INCONCLUSIVE

Descriptive full-scene recovered-feature evidence only. Thresholds are declared diagnostics, not universal geometry/accuracy limits. Blocks share frames/tracks; not independent population samples. Primary H2 decision uses same-local-segment pairs at <=3 s lag. COLMAP min triangulation angle and successful-registration selection censor unreconstructed/weak observations; NOT_SUPPORTED applies only to recovered-feature evidence.

实测证据：

```json

{
  "valid_local_pairs": 11,
  "local_temporal_block_pairs": 4,
  "high_covisibility_low_angle_block_fraction": 0.25,
  "jaccard_threshold": 0.25,
  "angle_threshold_deg": 3.0,
  "local_pair_angle_median_deg": 4.776182321648626,
  "local_pair_jaccard_median": 0.34328358208955223,
  "local_baseline_depth_ratio_median": 0.200907155056269,
  "within_same_local_segment_gap_le_3s_valid_pairs": 11,
  "within_segment_short_gap_blocks": 4,
  "within_segment_short_gap_high_jaccard_low_angle_fraction": 0.25
}

```

进一步验证：Repeat within verified local target ROIs and independent acquisitions; examine within-segment and temporal-gap sensitivity.


### H3: SUPPORTED

A mixed reconstructed track with non-collinear rays is an actual geometric correspondence, not merely potential overlap. Fewer than four independently observed local images is insufficient for a supported H3 judgment. Target-specific gain and final surface accuracy remain untested.

实测证据：

```json

{
  "local_frames": 7,
  "registered_local_frames": 7,
  "shared_global_local_points": 286,
  "global_local_valid_pairs": 7,
  "global_local_angle_median_deg": 4.3075406631079876,
  "global_local_temporal_blocks": 4,
  "blocks_with_angle_at_least_5deg_fraction": 0.5,
  "local_only_points": 126,
  "shared_points_with_local_direction_over_5deg_from_nearest_global": 175
}

```

进一步验证：Separate plant/background tracks and compare global-only versus global+local target geometry under aligned gauges.


### H4: INCONCLUSIVE

Cross-scale verified SIFT size ratios and match/registration rates are observed, but real overlap, motion blur, texture repetition and non-rigidity are not controlled. Failure alone cannot identify a scale mechanism. Verified-pair scale ratios are survivor-biased.

实测证据：

```json

{
  "matching_groups": {
    "APPROACH_LOCAL": {
      "tested_pairs_in_database": 21,
      "geometry_verified_pairs_15": 0,
      "verification_rate": 0.0,
      "raw_matches_median": 25.0,
      "verified_matches_median": 0.0,
      "local_global_scale_ratio_median": null
    },
    "GLOBAL_APPROACH": {
      "tested_pairs_in_database": 315,
      "geometry_verified_pairs_15": 31,
      "verification_rate": 0.09841269841269841,
      "raw_matches_median": 33.0,
      "verified_matches_median": 0.0,
      "local_global_scale_ratio_median": null
    },
    "GLOBAL_GLOBAL": {
      "tested_pairs_in_database": 5460,
      "geometry_verified_pairs_15": 717,
      "verification_rate": 0.13131868131868132,
      "raw_matches_median": 29.0,
      "verified_matches_median": 0.0,
      "local_global_scale_ratio_median": null
    },
    "GLOBAL_LOCAL": {
      "tested_pairs_in_database": 735,
      "geometry_verified_pairs_15": 72,
      "verification_rate": 0.09795918367346938,
      "raw_matches_median": 22.0,
      "verified_matches_median": 0.0,
      "local_global_scale_ratio_median": 1.4686619639396667
    },
    "LOCAL_LOCAL": {
      "tested_pairs_in_database": 21,
      "geometry_verified_pairs_15": 11,
      "verification_rate": 0.5238095238095238,
      "raw_matches_median": 77.0,
      "verified_matches_median": 47.0,
      "local_global_scale_ratio_median": null
    },
    "OTHER": {
      "tested_pairs_in_database": 118,
      "geometry_verified_pairs_15": 8,
      "verification_rate": 0.06779661016949153,
      "raw_matches_median": 0.0,
      "verified_matches_median": 0.0,
      "local_global_scale_ratio_median": null
    }
  },
  "registration_by_broad_stage": {
    "GLOBAL": {
      "frames": 105,
      "registered": 105,
      "registration_rate": 1.0
    },
    "LOCAL": {
      "frames": 7,
      "registered": 7,
      "registration_rate": 1.0
    },
    "APPROACH": {
      "frames": 3,
      "registered": 3,
      "registration_rate": 1.0
    },
    "TRANSITION": {
      "frames": 1,
      "registered": 0,
      "registration_rate": 0.0
    },
    "UNKNOWN": {
      "frames": 0,
      "registered": 0,
      "registration_rate": null
    }
  }
}

```

进一步验证：Audit actual overlap in failed pairs; compare fixed overlap with scale-normalized matching, sharpness-matched pairs and transition-frame ablations.


## 可核查图表

- [三维轨迹](../figures/camera_trajectory_3d.html)

- ![最终阶段](../segments/refined_segment_timeline.png)

- ![相对清晰度](../quality/sharpness_timeline.png)

- ![射线角度](../geometry/triangulation_angles.png)

- ![共视](../geometry/covisibility_heatmap.png)

- ![基线深度比](../geometry/baseline_depth_ratio.png)

- ![实际 COLMAP 全局—局部几何验证匹配（不保证植物区域）](../figures/global_local_matching_success.png)

- ![实际未注册帧](../figures/registration_failure_examples.png)

- 未注册局部帧与最佳全局连接候选：N/A（不存在可用对应案例，不伪造配图）。


## 局限与追溯

- No plant foreground masks; all geometric conclusions concern recovered full-scene features.

- No metric scale or known gravity; absolute baselines cannot be pooled across videos.

- Segment labels are proxy evidence, with unregistered temporal inference explicitly marked.

- Pair and time-block statistics remain correlated; no independent-pair significance test or causal blur claim.

- 8-bit sharpness/exposure diagnostics of HDR source are not calibrated radiometry.

- `../progress/*.json`、`../progress/history.jsonl`：阶段耗时、代码/输入签名及参数。

- `../logs/ffmpeg_extract.log` 和 `../sfm/logs/*.log`：真实外部命令与完整输出。

- `../sfm/registration_audit.csv`：全部成功及失败帧，含显式缺失值。

- `../geometry/point_track_geometry.csv`：轨迹长度、5°贪心方向箱计数（描述性，不是严格 Fisher 信息或深度精度）。