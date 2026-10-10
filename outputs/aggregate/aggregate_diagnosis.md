# Phase 01 总诊断：PARTIAL

实际发现 20 个源视频；第一轮指定 3 个；完成可读诊断 3 个；未完成 无。SfM 可用性、局部证据和测试分别验收，不把命令启动等同成功。

| video_id | duration_sec | extracted_frames | registered_images | raw_3d_points | valid_3d_points | mean_reprojection_error | median_reprojection_error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| video_007 | 57.988 | 116 | 115 | 8620 | 7227 | 1.424 | 1.397 |
| video_008 | 45.770 | 92 | 81 | 5519 | 4566 | 1.492 | 1.475 |
| video_020 | 33.220 | 67 | 67 | 17486 | 14991 | 1.297 | 1.242 |


## 按阶段配准

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


## 历史失败与修复

首轮真实 SfM 运行曾失败：COLMAP 3.9.1 拒绝原始 16-bit RGB PNG，导致三段第一次特征提取不可用；原始日志和失败清单保留在 `outputs/video_*/sfm_previous/`、`outputs/logs/`，修复为独立 `sfm_images/` 的确定性 uint16→uint8 转换并记录双重哈希。视觉复核服务曾返回 HTTP 429，错误响应保留在 `segments/visual_review/`，随后串行限速完成全部三个样本。`docs/REPAIR_LOG.md` 是逐次修复审计；这些历史失败不等于最终三段重跑失败。


## 研究建议

当前不直接进入新的 3DGS 几何损失开发。优先研究/验证一个具体前置问题：**在已验证植物目标重叠的全局—过渡—近景图像对中，如何区分‘缺少对应关系’与‘已有对应但角度退化’，并保留真实约束的桥接视图？**

实验证据仅限本报告的配准审计、匹配率、共同轨迹和角度分布。没有目标掩码、几何真值及对照消融时，不能把稀疏全场景现象直接升级为植物 3DGS 优化必要性或创新性结论。

现有基础流程只能对成功匹配/三角化的点统计，无法解释未形成点的真实表面重叠；PnP 内点未被结构化提供。需要目标区域审核、固定重叠的尺度/清晰度匹配实验及过渡帧消融。算法模块候选为可核查的跨尺度候选匹配+共视桥接选择/退化告警，而不是预设一个新的训练损失。

应进一步检索并与原作者方法核对：COLMAP/SfM 的初始化与增量注册、SIFT 跨尺度匹配、SuperPoint/SuperGlue/LightGlue、LoFTR、Pixel-Perfect SfM、Gaussian Splatting 的几何正则与稀疏视图问题。这些仅为后续检索方向，未声称其解决或未解决本数据问题。

当前三段数据可继续做目标 ROI 审核、局部片段与时间间隔敏感性、补过渡帧和匹配消融；需要独立更多采集或参考几何才能判断优化是否提高真实精度。


## 关键局限

植物种类/数量未知；样本 ID 只对应文件。无尺度标定/重建真值/植物掩码；可能由背景点支撑。标签为图像及三维稀疏点代理，不等同人工逐帧真值。VFR、旋转、HDR、电子防抖、滚动快门与潜在裁切需要记录，不因 1× 锁焦而排除。

测试状态：{'status': 'PASSED', 'unit': {'tests': 33, 'failures': 0, 'skipped': 0}, 'integration': {'tests': 2, 'failures': 0, 'skipped': 0}, 'total_tests': 35, 'failed': 0, 'artifacts': ['/fj/混合拍摄距离下的三维重建优化问题/outputs/tests/unit_results_verified.xml', '/fj/混合拍摄距离下的三维重建优化问题/outputs/tests/integration_results_verified.xml'], 'summarized_at': '2026-10-09T16:13:30.033496+00:00'}；源码完整性：{'video_007': True, 'video_008': True, 'video_020': True}；详细验收见 `acceptance.json`。