# Mixed-Distance Reconstruction Diagnostics — Phase 01：PARTIAL

报告生成：2026-10-09T16:28:03.233830+00:00。本报告的源数据是真实 MOV；合成测试独立存储，不计入实测。


## 1. 环境

OS：Linux-6.17.0-40-generic-x86_64-with-glibc2.39；Python：3.13.12 | packaged by Anaconda, Inc. | (main, Feb 24 2026, 16:13:31) [GCC 14.3.0]；执行器 `/fj/混合拍摄距离下的三维重建优化问题/.venv/bin/python`。

| package | version |
| --- | --- |
| cv2 | 4.13.0 |
| numpy | 2.4.6 |
| pandas | 3.0.5 |
| scipy | 1.18.0 |
| matplotlib | 3.10.5 |
| plotly | 6.6.0 |
| pycolmap | 4.2.0 |
| yaml | 6.0.3 |
| pytest | 8.3.4 |

```text

Fri Oct  9 15:40:13 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 590.48.01              Driver Version: 590.48.01      CUDA Version: 13.1     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA RTX A6000               Off |   00000000:18:00.0 Off |                  Off |
| 40%   67C    P2             86W /  300W |    1753MiB /  49140MiB |      0%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+
|   1  NVIDIA RTX A6000               Off |   00000000:D8:00.0 Off |                  Off |
| 30%   52C    P8             29W /  300W |      14MiB /  49140MiB |      0%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A           68916      G   /usr/lib/xorg/Xorg                      160MiB |
|    0   N/A  N/A           69248      G   /usr/bin/gnome-shell                    133MiB |
|    0   N/A  N/A           69825      G   ...exec/xdg-desktop-portal-gnome         28MiB |
|    0   N/A  N/A          361274      G   /usr/bin/nautilus                        18MiB |
|    0   N/A  N/A         1548022      G   .../8995/usr/lib/firefox/firefox        411MiB |
|    0   N/A  N/A         1793766      C   venv/bin/python                         896MiB |
|    0   N/A  N/A         1971336      G   /usr/bin/gnome-system-monitor            28MiB |
|    1   N/A  N/A           68916      G   /usr/lib/xorg/Xorg                        4MiB |
+-----------------------------------------------------------------------------------------+

nvcc: NVIDIA (R) Cuda compiler driver
Copyright (c) 2005-2024 NVIDIA Corporation
Built on Tue_Oct_29_23:50:19_PDT_2024
Cuda compilation tools, release 12.6, V12.6.85
Build cuda_12.6.r12.6/compiler.35059454_0

COLMAP 3.9.1 -- Structure-from-Motion and Multi-View Stereo
(Commit Unknown on Unknown without CUDA)



ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers

```

环境实测报告：`../../outputs/environment_report.json`；PyCOLMAP CUDA 能力 False。隔离 `.venv` 只读继承已有依赖，未改动已有科研环境。


## 2. 数据与样本选择

发现 20 个真实视频，只对 3 个进行完整 SfM。原始视频 `/fj/混合拍摄距离下的三维重建优化问题/原始视频`。20 段预览用于清晰度/运动/时长筛选；完整选择依据在 `../../outputs/selection.json`。不使用植物类别，也不假设一文件对应唯一植物。

| video_id | duration_sec | extracted_frames | quality_counts |
| --- | --- | --- | --- |
| video_007 | 57.988 | 116 | {'CLEAR': 107, 'MILD_BLUR': 9} |
| video_008 | 45.770 | 92 | {'CLEAR': 88, 'MILD_BLUR': 4} |
| video_020 | 33.220 | 67 | {'CLEAR': 62, 'MILD_BLUR': 5} |

抽帧依据 FFmpeg 解码帧的 source PTS，而非 frame_id/fps。PNG 原分辨率，FFmpeg autorotate 方向转换；8-bit质量分析不等同 HDR 辐射标定。媒体 packet cadence 为 VFR 检查，decoded showinfo 日志为实际图像 PTS 依据。


## 3. SfM 结果与轨迹

| video_id | stage | frames | registered | registration_rate |
| --- | --- | --- | --- | --- |
| video_007 | GLOBAL | 105 | 105 | 1.000 |
| video_007 | LOCAL | 7 | 7 | 1.000 |
| video_007 | APPROACH | 3 | 3 | 1.000 |
| video_007 | TRANSITION | 1 | 0 | 0.000 |
| video_007 | UNKNOWN | 0 | 0 | N/A |
| video_008 | GLOBAL | 81 | 71 | 0.877 |
| video_008 | LOCAL | 2 | 2 | 1.000 |
| video_008 | APPROACH | 7 | 6 | 0.857 |
| video_008 | TRANSITION | 2 | 2 | 1.000 |
| video_008 | UNKNOWN | 0 | 0 | N/A |
| video_020 | GLOBAL | 61 | 61 | 1.000 |
| video_020 | LOCAL | 2 | 2 | 1.000 |
| video_020 | APPROACH | 4 | 4 | 1.000 |
| video_020 | TRANSITION | 0 | 0 | N/A |
| video_020 | UNKNOWN | 0 | 0 | N/A |

| video_id | registered_images | raw_3d_points | valid_3d_points | mean_reprojection_error | median_reprojection_error |
| --- | --- | --- | --- | --- | --- |
| video_007 | 115 | 8620 | 7227 | 1.424 | 1.397 |
| video_008 | 81 | 5519 | 4566 | 1.492 | 1.475 |
| video_020 | 67 | 17486 | 14991 | 1.297 | 1.242 |


### video_007

流程 `GLOBAL_FIRST_REGISTRATION_AND_INCREMENTAL_CONTINUATION`；初始 GLOBAL 候选 105；基础模型 2 个。最终片段 8：['GLOBAL', 'APPROACH', 'GLOBAL', 'LOCAL_01', 'GLOBAL', 'LOCAL_02', 'TRANSITION', 'GLOBAL']。

轨迹诊断：最大相邻已注册视图旋转 41.499°；相对平移 p99/中位数 1.948。时间间隙、运动方向和逐观测滤除记录在 CSV；这些数值不是可靠性判定的唯一依据。

[完整单样本报告](../../outputs/video_007/report/diagnosis.md)，[三维轨迹](../../outputs/video_007/figures/camera_trajectory_3d.html)。


## 4.video_007. 几何实测

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

![阶段](../../outputs/video_007/segments/refined_segment_timeline.png)

![清晰度](../../outputs/video_007/quality/sharpness_timeline.png)

![角度](../../outputs/video_007/geometry/triangulation_angles.png)

![共视](../../outputs/video_007/geometry/covisibility_heatmap.png)

![比值](../../outputs/video_007/geometry/baseline_depth_ratio.png)

![global_local_matching_success.png](../../outputs/video_007/figures/global_local_matching_success.png)

![registration_failure_examples.png](../../outputs/video_007/figures/registration_failure_examples.png)

`global_local_unregistered_pair.png`：N/A，没有符合条件的真实例子。


### video_008

流程 `GLOBAL_FIRST_REGISTRATION_AND_INCREMENTAL_CONTINUATION`；初始 GLOBAL 候选 81；基础模型 1 个。最终片段 8：['GLOBAL', 'APPROACH', 'GLOBAL', 'TRANSITION', 'GLOBAL', 'LOCAL_01', 'APPROACH', 'GLOBAL']。

轨迹诊断：最大相邻已注册视图旋转 104.940°；相对平移 p99/中位数 5.099。时间间隙、运动方向和逐观测滤除记录在 CSV；这些数值不是可靠性判定的唯一依据。

[完整单样本报告](../../outputs/video_008/report/diagnosis.md)，[三维轨迹](../../outputs/video_008/figures/camera_trajectory_3d.html)。


## 4.video_008. 几何实测

| 指标 | GLOBAL_GLOBAL | LOCAL_LOCAL | GLOBAL_LOCAL |
| --- | --- | --- | --- |
| 有效图像对数（非独立样本） | 371 | 1 | 7 |
| 时间块对数（仍有关联） | 44 | 1 | 3 |
| 中位基线深度比（无量纲） | 0.287 | 0.059 | 0.343 |
| 中位三角化角（°） | 12.892 | 2.105 | 9.815 |
| 有效共视点数（图像对中位数） | 47.000 | 49.000 | 24.000 |
| 共视 Jaccard | 0.105 | 0.327 | 0.146 |
| 方向覆盖 i→j | 0.192 | 0.516 | 0.258 |
| 方向覆盖 j→i | 0.215 | 0.471 | 0.253 |
| 观测重投影误差中位数（px） | 1.576 | 1.457 | 1.669 |

![阶段](../../outputs/video_008/segments/refined_segment_timeline.png)

![清晰度](../../outputs/video_008/quality/sharpness_timeline.png)

![角度](../../outputs/video_008/geometry/triangulation_angles.png)

![共视](../../outputs/video_008/geometry/covisibility_heatmap.png)

![比值](../../outputs/video_008/geometry/baseline_depth_ratio.png)

![global_local_matching_success.png](../../outputs/video_008/figures/global_local_matching_success.png)

![registration_failure_examples.png](../../outputs/video_008/figures/registration_failure_examples.png)

![global_local_unregistered_pair.png](../../outputs/video_008/figures/global_local_unregistered_pair.png)


### video_020

流程 `GLOBAL_FIRST_REGISTRATION_AND_INCREMENTAL_CONTINUATION`；初始 GLOBAL 候选 61；基础模型 1 个。最终片段 4：['GLOBAL', 'APPROACH', 'LOCAL_01', 'GLOBAL']。

轨迹诊断：最大相邻已注册视图旋转 20.084°；相对平移 p99/中位数 1.916。时间间隙、运动方向和逐观测滤除记录在 CSV；这些数值不是可靠性判定的唯一依据。

[完整单样本报告](../../outputs/video_020/report/diagnosis.md)，[三维轨迹](../../outputs/video_020/figures/camera_trajectory_3d.html)。


## 4.video_020. 几何实测

| 指标 | GLOBAL_GLOBAL | LOCAL_LOCAL | GLOBAL_LOCAL |
| --- | --- | --- | --- |
| 有效图像对数（非独立样本） | 842 | 1 | 59 |
| 时间块对数（仍有关联） | 58 | 1 | 9 |
| 中位基线深度比（无量纲） | 0.716 | 0.110 | 0.586 |
| 中位三角化角（°） | 39.434 | 4.915 | 28.393 |
| 有效共视点数（图像对中位数） | 81.000 | 236.000 | 78.000 |
| 共视 Jaccard | 0.040 | 0.094 | 0.026 |
| 方向覆盖 i→j | 0.104 | 0.561 | 0.060 |
| 方向覆盖 j→i | 0.090 | 0.101 | 0.074 |
| 观测重投影误差中位数（px） | 1.461 | 1.635 | 1.629 |

![阶段](../../outputs/video_020/segments/refined_segment_timeline.png)

![清晰度](../../outputs/video_020/quality/sharpness_timeline.png)

![角度](../../outputs/video_020/geometry/triangulation_angles.png)

![共视](../../outputs/video_020/geometry/covisibility_heatmap.png)

![比值](../../outputs/video_020/geometry/baseline_depth_ratio.png)

![global_local_matching_success.png](../../outputs/video_020/figures/global_local_matching_success.png)

`registration_failure_examples.png`：N/A，没有符合条件的真实例子。

`global_local_unregistered_pair.png`：N/A，没有符合条件的真实例子。


## 5. 科研假设与下一阶段

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


## 历史失败与修复

首轮真实 SfM 曾因 COLMAP 3.9.1 拒绝 16-bit RGB PNG 而失败；修复后使用独立 `sfm_images/` uint16→uint8 转换并记录源/目标哈希。视觉复核服务曾返回 HTTP 429；错误响应被保留，随后串行限速完成复核。`docs/REPAIR_LOG.md`、`outputs/logs/initial_last_failures.json` 和每视频 `sfm_previous/` 是历史失败与修复的可追溯记录；最终修正运行无当前失败。

当前不直接进入新的 3DGS 几何损失开发。优先研究/验证一个具体前置问题：**在已验证植物目标重叠的全局—过渡—近景图像对中，如何区分‘缺少对应关系’与‘已有对应但角度退化’，并保留真实约束的桥接视图？**

实验证据仅限本报告的配准审计、匹配率、共同轨迹和角度分布。没有目标掩码、几何真值及对照消融时，不能把稀疏全场景现象直接升级为植物 3DGS 优化必要性或创新性结论。

现有基础流程只能对成功匹配/三角化的点统计，无法解释未形成点的真实表面重叠；PnP 内点未被结构化提供。需要目标区域审核、固定重叠的尺度/清晰度匹配实验及过渡帧消融。算法模块候选为可核查的跨尺度候选匹配+共视桥接选择/退化告警，而不是预设一个新的训练损失。

应进一步检索并与原作者方法核对：COLMAP/SfM 的初始化与增量注册、SIFT 跨尺度匹配、SuperPoint/SuperGlue/LightGlue、LoFTR、Pixel-Perfect SfM、Gaussian Splatting 的几何正则与稀疏视图问题。这些仅为后续检索方向，未声称其解决或未解决本数据问题。

当前三段数据可继续做目标 ROI 审核、局部片段与时间间隔敏感性、补过渡帧和匹配消融；需要独立更多采集或参考几何才能判断优化是否提高真实精度。


## 关键局限

植物种类/数量未知；样本 ID 只对应文件。无尺度标定/重建真值/植物掩码；可能由背景点支撑。标签为图像及三维稀疏点代理，不等同人工逐帧真值。VFR、旋转、HDR、电子防抖、滚动快门与潜在裁切需要记录，不因 1× 锁焦而排除。

测试状态：{'status': 'PASSED', 'unit': {'tests': 33, 'failures': 0, 'skipped': 0}, 'integration': {'tests': 2, 'failures': 0, 'skipped': 0}, 'total_tests': 35, 'failed': 0, 'artifacts': ['/fj/混合拍摄距离下的三维重建优化问题/outputs/tests/unit_results_verified.xml', '/fj/混合拍摄距离下的三维重建优化问题/outputs/tests/integration_results_verified.xml'], 'summarized_at': '2026-10-09T16:13:30.033496+00:00'}；源码完整性：{'video_007': True, 'video_008': True, 'video_020': True}；详细验收见 `acceptance.json`。


## 6. 测试与验收

结果 `PARTIAL`，不是把部分实验写成 PASS。单元/集成自动测试：{'status': 'PASSED', 'unit': {'tests': 33, 'failures': 0, 'skipped': 0}, 'integration': {'tests': 2, 'failures': 0, 'skipped': 0}, 'total_tests': 35, 'failed': 0, 'artifacts': ['/fj/混合拍摄距离下的三维重建优化问题/outputs/tests/unit_results_verified.xml', '/fj/混合拍摄距离下的三维重建优化问题/outputs/tests/integration_results_verified.xml'], 'summarized_at': '2026-10-09T16:13:30.033496+00:00'}。输出存在性、源文件哈希、有效重建和局部证据逐项记录于 `../../outputs/aggregate/acceptance.json`。

关键指标：真实共同点射线角，不是光轴夹角；C = −Rᵀt；逐观测负深度/高残差/短轨迹滤除；无共同点为 N/A；未注册共视为 NaN；相对尺度无米/厘米；不跨独立模型汇总绝对平移。


## 7. 文件、日志、方法与资料来源

- `../../outputs/video_inventory.csv`、`video_metadata.json`：20个源文件及完整元数据。

- 每视频 `frame_manifest.csv`、`progress/`、`logs/`、`sfm/logs/commands.jsonl`：时间戳/配置/软件/执行耗时与真实日志。

- `../../outputs/tests/`：合成数学及真实外部工具集成测试，不能作为真实视频结果。

- `METHODS.md`、`METRICS.md`：算法假设、阈值、统计单位与欠缺证据。

- 官方 COLMAP CLI/FAQ：https://colmap.github.io/cli.html ; https://colmap.github.io/faq.html （Context7 获取，并逐命令核验本机3.9.1 help；PyCOLMAP4.2本机 introspection）。

- PyCOLMAP：https://colmap.github.io/pycolmap/ ; https://github.com/colmap/pycolmap （旧仓库文档仅参考，实际4.2 API已运行核验）。

- FFmpeg：https://ffmpeg.org/ffmpeg-all.html （原 PTS、select、showinfo，已用本机6.1.1验证）。

- OpenCV：https://docs.opencv.org/5.0/py_tutorials/py_features/py_matcher/py_matcher.html （检索版5.0；本机4.13具体调用已测试）。

- 图片内容由 Agnes API 识别；描述归档在 `../../outputs/previews/*/agnes_description.md`；不是植物分类或逐帧人工真值。初次20图请求只返回4图的描述，已披露且未当成完整审核。

- Bocha联网搜索返回HTTP403；本阶段实现依据来自成功获取的Context7官方文档、安装版本help与真实测量，而非未检索的API记忆。