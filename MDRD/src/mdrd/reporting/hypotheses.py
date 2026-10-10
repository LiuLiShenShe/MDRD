import numpy as np


def diagnose(video_id, cameras, groups, blocks, tracks, matching, audit, parameters):
    grouped = groups.set_index("group").to_dict("index")
    local = grouped.get("LOCAL_LOCAL", {})
    global_pairs = grouped.get("GLOBAL_GLOBAL", {})
    mixed = grouped.get("GLOBAL_LOCAL", {})
    local_blocks = blocks[blocks.group == "LOCAL_LOCAL"]
    high_low = (local_blocks.jaccard >= parameters["high_covisibility"]) & (local_blocks.angle_median < parameters["low_angle_deg"])
    fraction = float(high_low.mean()) if len(local_blocks) else None
    hypotheses = {}
    hypotheses["H1"] = {"status": "INCONCLUSIVE", "evidence": {"target_pixel_coverage": None, "local_pair_angle_median_deg": local.get("angle_median"), "global_pair_angle_median_deg": global_pairs.get("angle_median"), "local_only_reconstructed_points": int(tracks.local_without_global.sum()) if len(tracks) else 0, "shared_global_local_points": int(tracks.global_local_shared.sum()) if len(tracks) else 0}, "basis": "No verified plant mask or correspondence-defined leaf ROI: increased target pixel coverage cannot be established. Ray angles are not reconstruction-accuracy measurements.", "figures": ["geometry/triangulation_angles.png", "geometry/point_track_geometry.csv"], "required_followup": "Validate foreground/leaf ROI correspondences and target pixel coverage; obtain reconstruction accuracy or a reference surface."}
    if len(local_blocks) < parameters["min_independent_blocks"] or local.get("valid_pairs", 0) < 10:
        h2 = "INCONCLUSIVE"
    elif fraction >= .5:
        h2 = "SUPPORTED"
    elif fraction <= .1:
        h2 = "NOT_SUPPORTED"
    else:
        h2 = "INCONCLUSIVE"
    hypotheses["H2"] = {"status": h2, "evidence": {"valid_local_pairs": local.get("valid_pairs", 0), "local_temporal_block_pairs": len(local_blocks), "high_covisibility_low_angle_block_fraction": fraction, "jaccard_threshold": parameters["high_covisibility"], "angle_threshold_deg": parameters["low_angle_deg"], "local_pair_angle_median_deg": local.get("angle_median"), "local_pair_jaccard_median": local.get("jaccard"), "local_baseline_depth_ratio_median": local.get("median_baseline_depth_ratio")}, "basis": "Descriptive full-scene recovered-feature evidence only. Thresholds are declared diagnostics, not universal geometry/accuracy limits. Blocks share frames/tracks; not independent population samples.", "figures": ["geometry/covisibility_heatmap.png", "geometry/triangulation_angles.png", "geometry/geometry_temporal_block_comparison.csv"], "required_followup": "Repeat within verified local target ROIs and independent acquisitions; examine within-segment and temporal-gap sensitivity."}
    shared = int(tracks.global_local_shared.sum()) if len(tracks) else 0
    mixed_blocks = blocks[blocks.group == "GLOBAL_LOCAL"]
    useful_fraction = float((mixed_blocks.angle_median >= parameters["adequate_angle_deg"]).mean()) if len(mixed_blocks) else None
    segments = [] if cameras is None else cameras.segment
    registration_flags = [] if cameras is None else cameras.registered
    local_frames = int(sum(str(segment).startswith("LOCAL") for segment in segments))
    registered_local_frames = int(sum(str(segment).startswith("LOCAL") and registered for segment, registered in zip(segments, registration_flags)))
    if local_frames >= 4 and registered_local_frames >= 4 and shared >= 50 and len(mixed_blocks) >= parameters["min_independent_blocks"] and useful_fraction >= .5:
        h3 = "SUPPORTED"
    else:
        h3 = "INCONCLUSIVE"
    hypotheses["H3"] = {"status": h3, "evidence": {"local_frames": local_frames, "registered_local_frames": registered_local_frames, "shared_global_local_points": shared, "global_local_valid_pairs": mixed.get("valid_pairs", 0), "global_local_angle_median_deg": mixed.get("angle_median"), "global_local_temporal_blocks": len(mixed_blocks), "blocks_with_angle_at_least_5deg_fraction": useful_fraction, "local_only_points": int(tracks.local_without_global.sum()) if len(tracks) else 0}, "basis": "A mixed reconstructed track with non-collinear rays is an actual geometric correspondence, not merely potential overlap. Fewer than four independently observed local images is insufficient for a supported H3 judgment. Target-specific gain and final surface accuracy remain untested.", "figures": ["figures/global_local_matching_success.png", "geometry/point_track_geometry.csv", "geometry/baseline_depth_ratio.png"], "required_followup": "Separate plant/background tracks and compare global-only versus global+local target geometry under aligned gauges."}
    match_groups = matching.set_index("group").to_dict("index") if len(matching) else {}
    registration = {}
    for label in ["GLOBAL", "LOCAL", "APPROACH", "TRANSITION", "UNKNOWN"]:
        selection = audit.segment.astype(str).str.startswith("LOCAL") if label == "LOCAL" else audit.segment.eq(label)
        subset = audit.loc[selection]
        registration[label] = {"frames": len(subset), "registered": int(subset.registered.sum()), "registration_rate": float(subset.registered.mean()) if len(subset) else None}
    hypotheses["H4"] = {"status": "INCONCLUSIVE", "evidence": {"matching_groups": match_groups, "registration_by_broad_stage": registration}, "basis": "Cross-scale verified SIFT size ratios and match/registration rates are observed, but real overlap, motion blur, texture repetition and non-rigidity are not controlled. Failure alone cannot identify a scale mechanism. Verified-pair scale ratios are survivor-biased.", "figures": ["geometry/matching_group_comparison.csv", "geometry/blur_registration_comparison.csv", "figures/global_local_unregistered_pair.png"], "required_followup": "Audit actual overlap in failed pairs; compare fixed overlap with scale-normalized matching, sharpness-matched pairs and transition-frame ablations."}
    return {"video_id": video_id, "hypotheses": hypotheses, "registration_by_broad_stage": registration, "foreground_scope": "FULL_SCENE_SPARSE_FEATURES_NO_VERIFIED_PLANT_MASK", "population_inference": "No independent-pair p-values; purposive pilot selection is not a population sample."}
