from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from mdrd.common import now, read_json, sha256, write_json


def number(value, precision=3):
    if value is None or (isinstance(value, (int, float, np.number)) and not np.isfinite(value)):
        return "N/A"
    if isinstance(value, (int, np.integer)):
        return str(value)
    if isinstance(value, (float, np.floating)):
        return f"{value:.{precision}f}"
    return str(value)


def markdown_table(rows, columns):
    header = "| " + " | ".join(columns) + " |\n| " + " | ".join(["---"] * len(columns)) + " |\n"
    return header + "\n".join("| " + " | ".join(number(row.get(column)).replace("|", "/") for column in columns) + " |" for row in rows)


def geometry_table(groups):
    lookup = groups.set_index("group").to_dict("index")
    names = ["GLOBAL_GLOBAL", "LOCAL_LOCAL", "GLOBAL_LOCAL"]
    definitions = [("有效图像对数（非独立样本）", "valid_pairs"), ("时间块对数（仍有关联）", "temporal_block_pairs"), ("中位基线深度比（无量纲）", "median_baseline_depth_ratio"), ("中位三角化角（°）", "angle_median"), ("有效共视点数（图像对中位数）", "common_3d_points"), ("共视 Jaccard", "jaccard"), ("方向覆盖 i→j", "coverage_i_j"), ("方向覆盖 j→i", "coverage_j_i"), ("观测重投影误差中位数（px）", "reprojection_error")]
    rows = [{"指标": title, **{name: lookup.get(name, {}).get(metric) for name in names}} for title, metric in definitions]
    return markdown_table(rows, ["指标"] + names)


def sample_report(directory, source):
    directory = Path(directory)
    report_dir = directory / "report"
    report_dir.mkdir(exist_ok=True)
    diagnosis = read_json(directory / "geometry" / "diagnosis.json")
    quality = read_json(directory / "quality" / "quality_summary.json")
    sfm = read_json(directory / "sfm" / "sfm_summary.json")
    groups = pd.read_csv(directory / "geometry" / "geometry_group_comparison.csv")
    registration = pd.read_csv(directory / "sfm" / "registration_by_segment.csv")
    refined = read_json(directory / "segments" / "refined_segments.json")
    model = sfm.get("final_model") or {}
    report_kind = "合成集成测试（非真实视频）" if source.get("synthetic") else "真实视频诊断"
    text = [f"# {directory.name}：{report_kind}", f"生成时间：{now()}；源视频 `{source['filename']}`；SHA-256 `{source['file_sha256']}`。", "\n## 数据与质量", f"时长 {source['duration_sec']:.3f} s；抽帧 {diagnosis['total_images']} 张；8-bit 全图清晰度代理标签：{quality['quality_counts']}。没有植物目标掩码，不能把这些标签视为已标定的运动模糊真值。", f"最终连续片段 {len(refined['segments'])}；局部片段标签不是叶片实例 ID；UNKNOWN 不强制填补。", "\n## SfM 与失败", f"模型策略：`{sfm['strategy']}`。已注册 {diagnosis['registered_images']}/{diagnosis['total_images']}；稀疏点 {model.get('num_3d_points', 0)}，分析过滤后 {diagnosis['valid_3d_points']}；平均/中位点重投影误差 {number(model.get('mean_reprojection_error'))}/{number(model.get('median_reprojection_error'))} px。", markdown_table(registration.to_dict("records"), ["segment", "total", "registered", "registration_rate"]), f"基础 GLOBAL 候选 {sfm['global_candidates']}；基础模型实际数量 {len(sfm['global_models'])}；每个模型文件、注册名单与内参记录在 `../sfm/sfm_summary.json`。保留全部未注册图像，PnP 内点缺失为 N/A；有证据不足的原因均为 UNKNOWN。", f"过滤审计：{diagnosis['filter_rejections']}。焦距与畸变参数为实测 BA 输出，不等同物理标定。背景依赖尚未用掩码验证。", "\n## 几何统计", geometry_table(groups), "\nN/A 表示无足够有效共同点/对应标签或未注册；不是零角度。表为图像对中位数，不做独立样本检验。绝对基线仅限本模型相对单位；跨视频只比较比值/角度。", "\n## H1–H4"]
    for name, hypothesis in diagnosis["hypotheses"].items():
        text += [f"\n### {name}: {hypothesis['status']}", hypothesis["basis"], "实测证据：", "```json", __import__("json").dumps(hypothesis["evidence"], ensure_ascii=False, indent=2, default=str), "```", "进一步验证：" + hypothesis["required_followup"]]
    text += ["\n## 可核查图表", "- [三维轨迹](../figures/camera_trajectory_3d.html)", "- ![最终阶段](../segments/refined_segment_timeline.png)", "- ![相对清晰度](../quality/sharpness_timeline.png)", "- ![射线角度](../geometry/triangulation_angles.png)", "- ![共视](../geometry/covisibility_heatmap.png)", "- ![基线深度比](../geometry/baseline_depth_ratio.png)"]
    for filename, title in [("global_local_matching_success.png", "实际 COLMAP 全局—局部几何验证匹配（不保证植物区域）"), ("registration_failure_examples.png", "实际未注册帧"), ("global_local_unregistered_pair.png", "未注册局部帧与最佳全局连接候选")]:
        if (directory / "figures" / filename).exists():
            text.append(f"- ![{title}](../figures/{filename})")
        else:
            text.append(f"- {title}：N/A（不存在可用对应案例，不伪造配图）。")
    text += ["\n## 局限与追溯", *["- " + item for item in diagnosis["limitations"]], "- `../progress/*.json`、`../progress/history.jsonl`：阶段耗时、代码/输入签名及参数。", "- `../logs/ffmpeg_extract.log` 和 `../sfm/logs/*.log`：真实外部命令与完整输出。", "- `../sfm/registration_audit.csv`：全部成功及失败帧，含显式缺失值。", "- `../geometry/point_track_geometry.csv`：轨迹长度、5°贪心方向箱计数（描述性，不是严格 Fisher 信息或深度精度）。"]
    (report_dir / "diagnosis.md").write_text("\n\n".join(text), encoding="utf-8")
    return diagnosis, groups


def generate_reports(configuration, sample_ids):
    output = Path(configuration["output_root"])
    aggregate = output / "aggregate"
    aggregate.mkdir(exist_ok=True)
    inventory = pd.read_csv(output / "video_inventory.csv")
    environment = read_json(output / "environment_report.json")
    tests = read_json(output / "tests" / "test_summary.json") if (output / "tests" / "test_summary.json").exists() else {"status": "NOT_RUN"}
    completed = []
    unavailable = []
    all_groups = []
    summaries = []
    for sample_id in sample_ids:
        directory = output / sample_id
        source = inventory[inventory.video_id == sample_id].iloc[0].to_dict()
        if not (directory / "geometry" / "diagnosis.json").exists():
            unavailable.append(sample_id)
            continue
        diagnosis, groups = sample_report(directory, source)
        completed.append(diagnosis)
        groups.insert(0, "video_id", sample_id)
        all_groups.append(groups)
        quality = read_json(directory / "quality" / "quality_summary.json")
        model = (read_json(directory / "sfm" / "sfm_summary.json").get("final_model") or {})
        broad = diagnosis["registration_by_broad_stage"]
        summaries.append({"video_id": sample_id, "duration_sec": source["duration_sec"], "extracted_frames": diagnosis["total_images"], "registered_images": diagnosis["registered_images"], "global_total": broad["GLOBAL"]["frames"], "global_registered": broad["GLOBAL"]["registered"], "local_total": broad["LOCAL"]["frames"], "local_registered": broad["LOCAL"]["registered"], "raw_3d_points": diagnosis["raw_3d_points"], "valid_3d_points": diagnosis["valid_3d_points"], "mean_reprojection_error": model.get("mean_reprojection_error"), "median_reprojection_error": model.get("median_reprojection_error"), "quality_counts": str(quality["quality_counts"])})
    comparison = pd.concat(all_groups, ignore_index=True) if all_groups else pd.DataFrame(columns=["video_id", "group"])
    comparison.to_csv(aggregate / "geometry_comparison.csv", index=False)
    pd.DataFrame(summaries).to_csv(aggregate / "sample_summary.csv", index=False)
    required = ["frame_manifest.csv", "quality/frame_quality.csv", "quality/quality_summary.json", "segments/coarse_segments.json", "segments/refined_segments.json", "sfm/sfm_summary.json", "sfm/registration_audit.csv", "geometry/cameras.csv", "geometry/pairwise_geometry.csv", "geometry/covisibility.npy", "geometry/common_counts.npy", "geometry/directional_coverage.npy", "figures/camera_trajectory_3d.html", "geometry/covisibility_heatmap.png", "geometry/triangulation_angles.png", "geometry/baseline_depth_ratio.png", "report/diagnosis.md"]
    validation = {"samples": {}, "source_integrity": {}, "tested_at": now()}
    for sample_id in sample_ids:
        directory = output / sample_id
        validation["samples"][sample_id] = {name: (directory / name).is_file() and (directory / name).stat().st_size > 0 for name in required}
        source = inventory[inventory.video_id == sample_id].iloc[0]
        validation["source_integrity"][sample_id] = sha256(source.source_path) == source.file_sha256
    output_complete = len(completed) == 3 and all(all(files.values()) for files in validation["samples"].values())
    effective = all(item["registered_images"] >= 5 and item["valid_3d_points"] >= 50 for item in completed)
    local_evidence = all(item["registration_by_broad_stage"]["LOCAL"]["frames"] >= 4 and item["registration_by_broad_stage"]["LOCAL"]["registered"] >= 2 for item in completed)
    if tests.get("failed", 0):
        acceptance = "FAIL"
    elif not completed:
        acceptance = "BLOCKED" if unavailable else "PARTIAL"
    elif output_complete and effective and local_evidence and tests.get("status") == "PASSED" and all(validation["source_integrity"].values()):
        acceptance = "PASS"
    else:
        acceptance = "PARTIAL"
    validation.update(acceptance=acceptance, complete_samples=len(completed), output_complete=output_complete, effective_reconstructions=effective, local_evidence_available_all_three=local_evidence, tests=tests)
    write_json(aggregate / "acceptance.json", validation)
    hypothesis_lines = ["# 三样本科研假设审计", "不合并独立模型的绝对基线；逐视频/片段与时间块描述，避免把数千个相关图像对当成独立重复实验。", "H1 需要可靠目标区域像素覆盖；H4 需要控制真实重叠及模糊，不能仅由注册率下结论。"]
    for name in ["H1", "H2", "H3", "H4"]:
        rows = [{"video_id": item["video_id"], "status": item["hypotheses"][name]["status"], "valid_points": item["valid_3d_points"]} for item in completed]
        hypothesis_lines += [f"\n## {name}", markdown_table(rows, ["video_id", "status", "valid_points"])]
        for item in completed:
            hypothesis_lines.append(f"- {item['video_id']}: {item['hypotheses'][name]['basis']} 详见该视频 `../{item['video_id']}/report/diagnosis.md` 的真实数值及样本数。")
    (aggregate / "research_hypotheses.md").write_text("\n\n".join(hypothesis_lines), encoding="utf-8")
    rows = []
    for item in completed:
        for label in ["GLOBAL", "LOCAL", "APPROACH", "TRANSITION", "UNKNOWN"]:
            records = item["registration_by_broad_stage"][label]
            rows.append({"video_id": item["video_id"], "stage": label, **records})
    stage_table = markdown_table(rows, ["video_id", "stage", "frames", "registered", "registration_rate"])
    notes = [f"# Phase 01 总诊断：{acceptance}", f"实际发现 {len(inventory)} 个源视频；第一轮指定 {len(sample_ids)} 个；完成可读诊断 {len(completed)} 个；未完成 {unavailable or '无'}。SfM 可用性、局部证据和测试分别验收，不把命令启动等同成功。", markdown_table(summaries, ["video_id", "duration_sec", "extracted_frames", "registered_images", "raw_3d_points", "valid_3d_points", "mean_reprojection_error", "median_reprojection_error"]), "\n## 按阶段配准", stage_table, "\n## 历史失败与修复", "首轮真实 SfM 运行曾失败：COLMAP 3.9.1 拒绝原始 16-bit RGB PNG，导致三段第一次特征提取不可用；原始日志和失败清单保留在 `outputs/video_*/sfm_previous/`、`outputs/logs/`，修复为独立 `sfm_images/` 的确定性 uint16→uint8 转换并记录双重哈希。视觉复核服务曾返回 HTTP 429，错误响应保留在 `segments/visual_review/`，随后串行限速完成全部三个样本。`docs/REPAIR_LOG.md` 是逐次修复审计；这些历史失败不等于最终三段重跑失败。", "\n## 研究建议", "当前不直接进入新的 3DGS 几何损失开发。优先研究/验证一个具体前置问题：**在已验证植物目标重叠的全局—过渡—近景图像对中，如何区分‘缺少对应关系’与‘已有对应但角度退化’，并保留真实约束的桥接视图？**", "实验证据仅限本报告的配准审计、匹配率、共同轨迹和角度分布。没有目标掩码、几何真值及对照消融时，不能把稀疏全场景现象直接升级为植物 3DGS 优化必要性或创新性结论。", "现有基础流程只能对成功匹配/三角化的点统计，无法解释未形成点的真实表面重叠；PnP 内点未被结构化提供。需要目标区域审核、固定重叠的尺度/清晰度匹配实验及过渡帧消融。算法模块候选为可核查的跨尺度候选匹配+共视桥接选择/退化告警，而不是预设一个新的训练损失。", "应进一步检索并与原作者方法核对：COLMAP/SfM 的初始化与增量注册、SIFT 跨尺度匹配、SuperPoint/SuperGlue/LightGlue、LoFTR、Pixel-Perfect SfM、Gaussian Splatting 的几何正则与稀疏视图问题。这些仅为后续检索方向，未声称其解决或未解决本数据问题。", "当前三段数据可继续做目标 ROI 审核、局部片段与时间间隔敏感性、补过渡帧和匹配消融；需要独立更多采集或参考几何才能判断优化是否提高真实精度。", "\n## 关键局限", "植物种类/数量未知；样本 ID 只对应文件。无尺度标定/重建真值/植物掩码；可能由背景点支撑。标签为图像及三维稀疏点代理，不等同人工逐帧真值。VFR、旋转、HDR、电子防抖、滚动快门与潜在裁切需要记录，不因 1× 锁焦而排除。", f"测试状态：{tests}；源码完整性：{validation['source_integrity']}；详细验收见 `acceptance.json`。"]
    (aggregate / "aggregate_diagnosis.md").write_text("\n\n".join(notes), encoding="utf-8")
    package_root = Path(__file__).resolve().parents[3]
    docs = package_root / "docs"
    packages = [{"package": name, "version": value.get("version", value.get("error"))} for name, value in environment["packages"].items()]
    final = [f"# Mixed-Distance Reconstruction Diagnostics — Phase 01：{acceptance}", f"报告生成：{now()}。本报告的源数据是真实 MOV；合成测试独立存储，不计入实测。", "\n## 1. 环境", f"OS：{environment['os']}；Python：{environment['python']}；执行器 `{environment['python_executable']}`。", markdown_table(packages, ["package", "version"]), "```text", environment["gpu"].get("text", "N/A"), environment["cuda"].get("text", "N/A"), environment["tools"]["colmap"].get("text", "N/A").split("Usage:")[0], environment["tools"]["ffmpeg"].get("text", "N/A").splitlines()[0], "```", f"环境实测报告：`../../outputs/environment_report.json`；PyCOLMAP CUDA 能力 {environment['pycolmap_has_cuda']}。隔离 `.venv` 只读继承已有依赖，未改动已有科研环境。", "\n## 2. 数据与样本选择", f"发现 {len(inventory)} 个真实视频，只对 {len(sample_ids)} 个进行完整 SfM。原始视频 `{Path(inventory.source_path.iloc[0]).parent}`。20 段预览用于清晰度/运动/时长筛选；完整选择依据在 `../../outputs/selection.json`。不使用植物类别，也不假设一文件对应唯一植物。", markdown_table(summaries, ["video_id", "duration_sec", "extracted_frames", "quality_counts"]), "抽帧依据 FFmpeg 解码帧的 source PTS，而非 frame_id/fps。PNG 原分辨率，FFmpeg autorotate 方向转换；8-bit质量分析不等同 HDR 辐射标定。媒体 packet cadence 为 VFR 检查，decoded showinfo 日志为实际图像 PTS 依据。", "\n## 3. SfM 结果与轨迹", stage_table, markdown_table(summaries, ["video_id", "registered_images", "raw_3d_points", "valid_3d_points", "mean_reprojection_error", "median_reprojection_error"])]
    for item in completed:
        sample_id = item["video_id"]
        directory = output / sample_id
        sfm = read_json(directory / "sfm" / "sfm_summary.json")
        segment_data = read_json(directory / "segments" / "refined_segments.json")
        final += [f"\n### {sample_id}", f"流程 `{sfm['strategy']}`；初始 GLOBAL 候选 {sfm['global_candidates']}；基础模型 {len(sfm['global_models'])} 个。最终片段 {len(segment_data['segments'])}：{[segment['label'] for segment in segment_data['segments']]}。", f"轨迹诊断：最大相邻已注册视图旋转 {number(item['trajectory_max_rotation_deg'])}°；相对平移 p99/中位数 {number(item['trajectory_step_p99_over_median'])}。时间间隙、运动方向和逐观测滤除记录在 CSV；这些数值不是可靠性判定的唯一依据。", f"[完整单样本报告](../../outputs/{sample_id}/report/diagnosis.md)，[三维轨迹](../../outputs/{sample_id}/figures/camera_trajectory_3d.html)。", f"\n## 4.{sample_id}. 几何实测", geometry_table(pd.read_csv(directory / "geometry" / "geometry_group_comparison.csv")), f"![阶段](../../outputs/{sample_id}/segments/refined_segment_timeline.png)", f"![清晰度](../../outputs/{sample_id}/quality/sharpness_timeline.png)", f"![角度](../../outputs/{sample_id}/geometry/triangulation_angles.png)", f"![共视](../../outputs/{sample_id}/geometry/covisibility_heatmap.png)", f"![比值](../../outputs/{sample_id}/geometry/baseline_depth_ratio.png)"]
        for filename in ["global_local_matching_success.png", "registration_failure_examples.png", "global_local_unregistered_pair.png"]:
            final.append(f"![{filename}](../../outputs/{sample_id}/figures/{filename})" if (directory / "figures" / filename).exists() else f"`{filename}`：N/A，没有符合条件的真实例子。")
    final += ["\n## 5. 科研假设与下一阶段", *hypothesis_lines[1:], "\n## 历史失败与修复", "首轮真实 SfM 曾因 COLMAP 3.9.1 拒绝 16-bit RGB PNG 而失败；修复后使用独立 `sfm_images/` uint16→uint8 转换并记录源/目标哈希。视觉复核服务曾返回 HTTP 429；错误响应被保留，随后串行限速完成复核。`docs/REPAIR_LOG.md`、`outputs/logs/initial_last_failures.json` 和每视频 `sfm_previous/` 是历史失败与修复的可追溯记录；最终修正运行无当前失败。", *notes[notes.index("\n## 研究建议") + 1:], "\n## 6. 测试与验收", f"结果 `{acceptance}`，不是把部分实验写成 PASS。单元/集成自动测试：{tests}。输出存在性、源文件哈希、有效重建和局部证据逐项记录于 `../../outputs/aggregate/acceptance.json`。", "关键指标：真实共同点射线角，不是光轴夹角；C = −Rᵀt；逐观测负深度/高残差/短轨迹滤除；无共同点为 N/A；未注册共视为 NaN；相对尺度无米/厘米；不跨独立模型汇总绝对平移。", "\n## 7. 文件、日志、方法与资料来源", "- `../../outputs/video_inventory.csv`、`video_metadata.json`：20个源文件及完整元数据。", "- 每视频 `frame_manifest.csv`、`progress/`、`logs/`、`sfm/logs/commands.jsonl`：时间戳/配置/软件/执行耗时与真实日志。", "- `../../outputs/tests/`：合成数学及真实外部工具集成测试，不能作为真实视频结果。", "- `METHODS.md`、`METRICS.md`：算法假设、阈值、统计单位与欠缺证据。", "- 官方 COLMAP CLI/FAQ：https://colmap.github.io/cli.html ; https://colmap.github.io/faq.html （Context7 获取，并逐命令核验本机3.9.1 help；PyCOLMAP4.2本机 introspection）。", "- PyCOLMAP：https://colmap.github.io/pycolmap/ ; https://github.com/colmap/pycolmap （旧仓库文档仅参考，实际4.2 API已运行核验）。", "- FFmpeg：https://ffmpeg.org/ffmpeg-all.html （原 PTS、select、showinfo，已用本机6.1.1验证）。", "- OpenCV：https://docs.opencv.org/5.0/py_tutorials/py_features/py_matcher/py_matcher.html （检索版5.0；本机4.13具体调用已测试）。", "- 图片内容由 Agnes API 识别；描述归档在 `../../outputs/previews/*/agnes_description.md`；不是植物分类或逐帧人工真值。初次20图请求只返回4图的描述，已披露且未当成完整审核。", "- Bocha联网搜索返回HTTP403；本阶段实现依据来自成功获取的Context7官方文档、安装版本help与真实测量，而非未检索的API记忆。"]
    (docs / "PHASE_01_FINAL_REPORT.md").write_text("\n\n".join(final), encoding="utf-8")
    print(f"REPORT {acceptance} {len(completed)}/{len(sample_ids)} samples", flush=True)
    return acceptance
