from pathlib import Path

import cv2
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def timeline(frame, columns, path, ylabel=None):
    figure, axes = plt.subplots(len(columns), 1, figsize=(12, max(3, 2.5 * len(columns))), sharex=True, squeeze=False)
    for axis, column in zip(axes.ravel(), columns):
        axis.plot(frame.timestamp_sec, frame[column], linewidth=1)
        axis.set_ylabel(ylabel or column)
        axis.grid(alpha=.2)
    axes[-1, 0].set_xlabel("Source presentation time (s)")
    figure.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=130)
    plt.close(figure)


def contact_sheet(frame, path, title="", columns=4):
    rows = max(1, int(np.ceil(len(frame) / columns)))
    figure, axes = plt.subplots(rows, columns, figsize=(columns * 3.2, rows * 2.15), squeeze=False)
    for axis in axes.ravel():
        axis.axis("off")
    for axis, item in zip(axes.ravel(), frame.to_dict("records")):
        image = cv2.imread(str(item["image_path"]))
        if image is None:
            continue
        axis.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        axis.set_title(f"{item.get('frame_id', '')} t={item.get('timestamp_sec', 0):.2f}s {item.get('quality_label', '')}", fontsize=8)
    figure.suptitle(title, fontsize=11)
    figure.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=110)
    plt.close(figure)


def segment_timeline(frame, path, column="label"):
    labels = list(dict.fromkeys(frame[column].astype(str)))
    codes = {label: index for index, label in enumerate(labels)}
    figure, axis = plt.subplots(figsize=(12, 3))
    axis.scatter(frame.timestamp_sec, frame[column].map(codes), c=frame[column].map(codes), cmap="tab10", s=18)
    axis.set_yticks(list(codes.values()), list(codes))
    axis.set_xlabel("Source presentation time (s)")
    axis.grid(alpha=.2)
    figure.tight_layout()
    figure.savefig(path, dpi=130)
    plt.close(figure)
