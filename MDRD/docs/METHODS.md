# Methods and traceability

## P0: inventory and selection

Recursively discover MOV/MP4 case-insensitively. FFprobe records full stream/container metadata and packet PTS/duration diagnostics. Source SHA-256, size, modification time and absolute path are saved. Distinct packet cadence is a VFR signal, not inferred frame time. Ten low-resolution approximate seek previews per video support purposive quality/motion/duration diversity selection; they are not analysis frames and do not establish a complete orbit. No category or individual-plant identity is inferred. First phase has a hard three-video full-SfM guard.

`environment_report.json` records OS, executable paths and actual versions, GPU/driver, CUDA toolkit, disk and package availability. The system COLMAP 3.9.1 is CPU-only despite two GPUs being present. PyCOLMAP 4.2.0 is also CPU-only. API access is checked against installed symbols and real integration tests; CLI support is read from each installed command's help. Official Context7 sources were fetched before implementation. Missing RTK.md is disclosed; no nonexistent instructions were assumed.

## P1: frame timestamp authority

FFmpeg `-copyts`, decoded `showinfo@source`, timestamp-aware `select`, selected `showinfo@selected`, `-fps_mode passthrough` and autorotate. Sample the first decoded frame and subsequent frames at requested interval; a long sequence may be capped by increasing interval. Actual selected PTS and decoder source-frame index, dimensions, file/source hashes and sampling method are persisted. Target-count mode selects nearest decoded best-effort presentation times from FFprobe, then FFmpeg uses exact decoded frame indices. Adaptive mode preserves baseline source indices and merges bounded proposed nearest decoded PTS. No frame_id/fps timestamp inference, duplicate frame insertion or arbitrary all-frame SfM.

Scientific PNG extraction preserves the decoder RGB16 representation of the 10-bit HLG/Dolby Vision base-layer source. COLMAP 3.9.1 rejects these PNGs: separate `sfm_images` convert uint16 to uint8 by `>>8`, with source/output hashes and unchanged geometry. This is not photometric HDR calibration or tone mapping. Rotation is applied once by FFmpeg; the actual oriented dimensions are used by SfM.

## P2/P3: relative image evidence

Quality uses a fixed maximum analysis dimension, Laplacian variance, squared Sobel gradient mean (Tenengrad), mean brightness, near-saturation/dark pixel ratios, 15×15 local standard deviation, SIFT feature count and occupied 8×6 feature-grid fraction. A nine-frame local median comparison in log sharpness/gradient space flags relative dips, not a universal optical blur threshold. Severe candidate: relative Laplacian <0.3 and gradient <0.5; mild: <0.65 and <0.8; insufficient texture/window => UNCERTAIN. All frames remain candidates. Labels are confounded by texture, scale, crop and background; actual optical motion blur is not established from a scalar.

Adjacent matching uses SIFT 2-NN ratio 0.75 and homography RANSAC for a conservative *2D proxy* scale estimate. This homography inlier count is not COLMAP epipolar verification or PnP. LK uses forward/backward error <1.5 analysis pixels, median displacement, radial expansion and eight-bin flow direction histogram. Flow is not physical translation. Coarse states use relative verified feature-scale regimes, expansion/motion/change evidence and temporal run smoothing; low confidence remains UNKNOWN. No fractional split or forced number of close-ups.

Original automatic frames are saved before overrides. The optional Agnes API reviews frame contact sheets with timestamps; this is image-content evidence, **not human verification**. Per-frame response provenance, source, confidence, time of correction and prior labels are retained. Semantic review is protected from an unsupported depth-proxy relabel. Human CSV/JSON editing is supported without overwriting automatic originals.

## P4/P5: global-first, all-frame audit

Use semantically reviewed or automatic GLOBAL candidates with sufficient feature coverage, never remove local/failed input silently. A shared SIMPLE_RADIAL camera is the first low-parameter model; principal point is fixed at default, focal/distortion refined. All chosen frames get SIFT features. At ≤130 frames, exhaustively match all pairs for temporal bridging and loop closure. Above that, match sequence neighbors, non-neighbor global anchors and all global pairs; this is documented rather than pretending exhaustive statistics.

Map GLOBAL images first, retain all submodels. Register remaining frames against the chosen global seed; `image_registrator` alone does not triangulate or BA. Continue mapping with fixed existing images, then triangulate and perform final BA. A low-coverage/no-seed attempt triggers joint mapping; joint models are independently scaled and cannot be compared via raw baseline. Chosen and discarded models, complete logs, camera parameters, focal-to-max-dimension, track histograms, point residuals and image registration lists are saved. An unsuccessful default initialization is not concealed by dropping images or loosening gates.

Every input image is in the final audit. Database raw/verified matches, SIFT count and structured registration status are available. PnP inliers are missing because this CLI does not provide stable structured output; missing is not fabricated from pair matches. Specific failure causes require evidence; otherwise UNKNOWN. Low feature count is used only below a necessary PnP-support threshold. Registration success and low residual alone are not physical geometry correctness.

## P6/P7: pose and stages

PyCOLMAP world-to-camera pose is `Xc=R Xw+t`; center is `−Rᵀt`. It is numerically compared with `projection_center()`. Pose/intrinsics/image ID/camera ID/time/stage rows include unregistered images with missing poses. Step distance/rotation/direction are between consecutive **registered** samples; source-frame adjacency and time gap are explicit. Missing frames are not interpolated into fake poses. All distances are relative SfM units.

Refinement uses recovered centers/view directions, valid observation distances, common-point relative distances to global reference views, adjacent sparse covisibility and temporal/quality context. A median depth of different points is a content-confounded proxy; common-point normalization mitigates but cannot solve absent foreground evidence. Temporal run smoothing only changes automatic labels: short manually/visually reviewed LOCAL runs retain their provenance and explicit confidence rather than silently disappearing. LOCAL numbering identifies continuous near-view runs, not leaf instances. No known gravity/verified plant top: do not force TOP_CANDIDATE. Unregistered labels remain temporal/visual inference, not direct 3D validation.

## P8/P9: observational geometry

Retain finite points with mean point error ≤4 px and ≥3 accepted registered observations. Validate each track index ↔ point ID association, actual camera projection with radial model, positive camera depth and individual residual ≤4 px, then recheck track length. This avoids confusing point-level mean error with an individually valid observation. Calculate every manifest image pair, with NaN where unregistered/undefined. Registered pairs with <20 valid common points retain actual counts/baseline/covisibility but no accepted angle statistics.

Angles use the two actual center-to-common-point rays; no optical-axis-angle substitute. Baseline/depth ratio uses mean Euclidean ray distances (not only z-depth). Sparse-point Jaccard/directional coverage use filtered per-image tracks. Missing unregistered matrices are NaN, true disjoint nonempty registered sets have zero covisibility. No target masks were verified, so all evidence refers to reconstructed full-scene points; background attribution remains unresolved.

## P10: nonindependence and conservative hypotheses

Report pair medians with actual counts, temporal block-pair medians (3 s bins) and time-gap/same-segment sensitivity. Blocks still share cameras and tracks; this is not a significance test or population confidence interval. Across videos pool only per-video scale-invariant summaries, never raw independent-model baselines. Purposively chosen pilot videos are not a random sample. Greedy 5° direction bins and ray-angle ranges are descriptive orientation diversity, not calibrated depth precision or Fisher information.

H1 needs validated target pixel/ROI coverage and reference geometry; absent that, INCONCLUSIVE. H2 evaluates within-local-segment ≤3 s lag, ≥10 valid pairs and ≥4 temporal block pairs; “high” sparse Jaccard ≥0.25 and “low” median ray angle <3° are declared diagnostic thresholds. A fraction ≥0.5 supports a recovered-feature descriptive phenomenon; ≤0.1 does not support it in this filtered set. Successful matching/triangulation selection and COLMAP's min-angle gate censor weak/unreconstructed evidence. H3 requires ≥4 local registered images, ≥50 actually shared tracks, ≥4 mixed temporal blocks and ≥0.5 blocks with median angle ≥5°; support means full-scene geometric correspondence, not plant-specific accuracy gain. H4 remains inconclusive without controlling real overlap, texture, blur/nonrigidity; survivor SIFT-scale ratios and lower match rates alone do not establish mechanism.

No statistical significance, causal blur effect, new optimization merit or target reconstruction accuracy is claimed without corresponding data. Failure examples and missing outputs are labeled; original failures and repair history are not erased.
