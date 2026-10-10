from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go

from mdrd.geometry.core import broad_label
from mdrd.sfm.pipeline import PAIR_ID_FACTOR
from mdrd.visualization.plots import contact_sheet, timeline


def trajectory_figures(directory, cameras, motion, points):
    output = Path(directory) / "figures"
    output.mkdir(exist_ok=True)
    registered = cameras[cameras.registered]
    figure = go.Figure()
    for label, subset in registered.groupby("segment"):
        figure.add_trace(go.Scatter3d(x=subset.camera_center_x, y=subset.camera_center_y, z=subset.camera_center_z, mode="markers", name=label, text=subset.filename, marker={"size": 3}))
    if len(registered):
        figure.add_trace(go.Scatter3d(x=registered.camera_center_x, y=registered.camera_center_y, z=registered.camera_center_z, mode="lines", name="time path (gaps not validated)", line={"color": "gray", "width": 2}))
    xyz = np.array([point["xyz"] for point in list(points.values())[::max(1, len(points) // 6000)]]).reshape(-1, 3)
    if len(xyz):
        figure.add_trace(go.Scatter3d(x=xyz[:, 0], y=xyz[:, 1], z=xyz[:, 2], mode="markers", name="Filtered full-scene sparse points", marker={"size": 1, "opacity": .3, "color": "gray"}))
    figure.update_layout(title="Camera trajectory — relative SfM units; full scene, no plant mask", scene={"aspectmode": "data", "xaxis_title": "X (relative)", "yaxis_title": "Y (relative)", "zaxis_title": "Z (relative)"})
    figure.write_html(output / "camera_trajectory_3d.html", include_plotlyjs=True)
    for first, second in [("x", "y"), ("x", "z"), ("y", "z")]:
        plot, axis = plt.subplots(figsize=(7, 6))
        for label, subset in registered.groupby("segment"):
            axis.scatter(subset[f"camera_center_{first}"], subset[f"camera_center_{second}"], s=12, label=label)
        if len(registered):
            axis.plot(registered[f"camera_center_{first}"], registered[f"camera_center_{second}"], color="gray", linewidth=.5, alpha=.4)
            axis.legend(fontsize=7)
        else:
            axis.text(.5, .5, "N/A: no registered camera poses", transform=axis.transAxes, ha="center")
        axis.set_xlabel(f"{first.upper()} (relative SfM units)")
        axis.set_ylabel(f"{second.upper()} (relative SfM units)")
        axis.set_aspect("equal", adjustable="datalim")
        axis.grid(alpha=.2)
        plot.tight_layout()
        plot.savefig(output / f"camera_trajectory_{first}{second}.png", dpi=130)
        plt.close(plot)
    timeline(motion, ["translation_relative_units"], output / "translation_timeline.png")
    timeline(motion, ["rotation_deg"], output / "rotation_timeline.png")


def geometry_figures(directory, cameras, pairs, groups, common, jaccard):
    output = Path(directory) / "geometry"
    valid = pairs[pairs.geometry_valid]
    labels = ["GLOBAL_GLOBAL", "LOCAL_LOCAL", "GLOBAL_LOCAL", "GLOBAL_APPROACH", "APPROACH_LOCAL"]
    for metric, filename, ylabel in [("angle_median", "triangulation_angles.png", "Median common-point ray angle (degrees)"), ("median_baseline_depth_ratio", "baseline_depth_ratio.png", "Median baseline / mean ray distance (scale-free)")]:
        figure, axis = plt.subplots(figsize=(11, 5))
        data = [valid.loc[valid.group == group, metric].dropna().to_numpy() for group in labels]
        positions = [index + 1 for index, values in enumerate(data) if len(values)]
        if positions:
            axis.boxplot([values for values in data if len(values)], positions=positions, showfliers=False)
        else:
            axis.text(.5, .5, "N/A: no valid common-point pairs", transform=axis.transAxes, ha="center")
        axis.set_xticks(range(1, len(labels) + 1), [label + f"\nn={len(values)}" for label, values in zip(labels, data)], fontsize=8)
        axis.set_ylabel(ylabel)
        axis.set_title("Descriptive pair distributions (correlated, not independent samples)")
        axis.grid(axis="y", alpha=.2)
        figure.tight_layout()
        figure.savefig(output / filename, dpi=130)
        plt.close(figure)
    figure, axis = plt.subplots(figsize=(9, 8))
    colormap = plt.get_cmap("viridis").copy()
    colormap.set_bad("lightgray")
    image = axis.imshow(np.ma.masked_invalid(jaccard), vmin=0, vmax=1, cmap=colormap)
    axis.set_xlabel("Manifest frame order")
    axis.set_ylabel("Manifest frame order")
    axis.set_title("Filtered sparse-point Jaccard; gray = unavailable")
    figure.colorbar(image, ax=axis, label="Jaccard covisibility")
    figure.tight_layout()
    figure.savefig(output / "covisibility_heatmap.png", dpi=130)
    plt.close(figure)
    positions = np.linspace(0, 2 * np.pi, len(cameras), endpoint=False)
    coordinates = np.column_stack([np.cos(positions), np.sin(positions)])
    graph = go.Figure()
    edges = set()
    for index, row in enumerate(common):
        for neighbor in np.argsort(np.nan_to_num(row, nan=-1))[-6:]:
            if neighbor != index and np.isfinite(row[neighbor]) and row[neighbor] >= 20:
                edges.add(tuple(sorted([index, int(neighbor)])))
    edge_x, edge_y = [], []
    for first, second in edges:
        edge_x.extend([coordinates[first, 0], coordinates[second, 0], None])
        edge_y.extend([coordinates[first, 1], coordinates[second, 1], None])
    graph.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines", line={"width": .5, "color": "lightgray"}, hoverinfo="skip", name="Top-6 sparse links (not all edges)"))
    for label, subset in cameras.groupby("segment"):
        indices = subset.index.to_numpy()
        graph.add_trace(go.Scatter(x=coordinates[indices, 0], y=coordinates[indices, 1], text=subset.filename, mode="markers", name=label, marker={"size": 7}, hovertemplate="%{text}"))
    graph.update_layout(title="Temporal circular layout; sparse covisibility graph", xaxis={"visible": False}, yaxis={"visible": False, "scaleanchor": "x"})
    graph.write_html(output / "covisibility_graph.html", include_plotlyjs=True)


def draw_database_pair(directory, pair, path):
    directory = Path(directory)
    first_id, second_id = int(pair["image_id_i"]), int(pair["image_id_j"])
    pair_id = min(first_id, second_id) * PAIR_ID_FACTOR + max(first_id, second_id)
    with sqlite3.connect(directory / "sfm" / "database.db") as connection:
        geometry = connection.execute("SELECT rows,cols,data FROM two_view_geometries WHERE pair_id=?", (pair_id,)).fetchone()
        keypoints = []
        for image_id in [first_id, second_id]:
            row = connection.execute("SELECT rows,cols,data FROM keypoints WHERE image_id=?", (image_id,)).fetchone()
            keypoints.append(np.frombuffer(row[2], dtype=np.float32).reshape(row[0], row[1]))
    images = [cv2.imread(str(directory / "frames" / pair[key])) for key in ["filename_i", "filename_j"]]
    factors = [720 / max(image.shape[:2]) for image in images]
    resized = [cv2.resize(image, None, fx=factor, fy=factor) for image, factor in zip(images, factors)]
    height = max(image.shape[0] for image in resized)
    canvas = np.full((height + 75, sum(image.shape[1] for image in resized), 3), 245, np.uint8)
    offset = resized[0].shape[1]
    for image, start in zip(resized, [0, offset]):
        canvas[75:75 + image.shape[0], start:start + image.shape[1]] = image
    if geometry and geometry[0]:
        matches = np.frombuffer(geometry[2], dtype=np.uint32).reshape(geometry[0], geometry[1])
        matches = matches[::max(1, len(matches) // 35)][:35]
        for match in matches:
            first_point = keypoints[0][match[0], :2] * factors[0] + [0, 75]
            second_point = keypoints[1][match[1], :2] * factors[1] + [offset, 75]
            cv2.line(canvas, tuple(first_point.astype(int)), tuple(second_point.astype(int)), (0, 200, 0), 1, cv2.LINE_AA)
    label = f"{pair['group']}: raw={pair['match_count']}, verified={pair['verified_match_count']}"
    cv2.putText(canvas, label, (10, 23), cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 0, 0), 1)
    cv2.putText(canvas, f"{pair['filename_i']} | {pair['filename_j']}", (10, 47), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 0, 0), 1)
    cv2.imwrite(str(path), canvas)


def matching_examples(directory, audit, matching):
    directory = Path(directory)
    output = directory / "figures"
    local_global = matching[matching.group == "GLOBAL_LOCAL"]
    if len(local_global) and local_global.verified_match_count.max() >= 15:
        successful = local_global.sort_values("verified_match_count", ascending=False).iloc[0].to_dict()
        draw_database_pair(directory, successful, output / "global_local_matching_success.png")
        (output / "matching_success_provenance.json").write_text(json.dumps(successful, indent=2))
    failed = audit[~audit.registered]
    manifest = __import__("pandas").read_csv(directory / "frame_manifest.csv")
    if len(failed):
        examples = manifest[manifest.filename.isin(failed.filename)].head(6)
        contact_sheet(examples, output / "registration_failure_examples.png", title="Unregistered real frames; mechanism not inferred", columns=3)
        candidate_names = set(failed.filename)
        candidates = local_global[local_global.filename_i.isin(candidate_names) | local_global.filename_j.isin(candidate_names)]
        if len(candidates):
            best_failed = candidates.sort_values("verified_match_count", ascending=False).iloc[0].to_dict()
            draw_database_pair(directory, best_failed, output / "global_local_unregistered_pair.png")
            (output / "matching_failure_provenance.json").write_text(json.dumps(best_failed, indent=2))
