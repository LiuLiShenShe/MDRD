import argparse
import base64
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import requests

from mdrd.common import now, write_json


def main():
    parser = argparse.ArgumentParser(description="Optional traceable image-content review; does not provide human ground truth or physical distance")
    parser.add_argument("--output", default="outputs")
    parser.add_argument("--samples", nargs="+", required=True)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    key = os.environ.get("AGNES_API_KEY")
    if not key:
        raise SystemExit("Set AGNES_API_KEY; no credentials are stored in source or logs")
    tasks = []
    for sample in args.samples:
        directory = Path(args.output) / sample
        review = directory / "segments" / "visual_review"
        review.mkdir(parents=True, exist_ok=True)
        manifest = pd.read_csv(directory / "frame_manifest.csv")
        for start in range(0, len(manifest), 12):
            subset = manifest.iloc[start:start + 12]
            path = review / f"page_{start // 12:03d}.jpg"
            canvas = np.full((4 * 480, 3 * 290, 3), 250, np.uint8)
            for index, item in enumerate(subset.to_dict("records")):
                image = cv2.imread(item["image_path"])
                factor = min(270 / image.shape[1], 430 / image.shape[0])
                image = cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
                top, left = index // 3 * 480, index % 3 * 290
                cv2.putText(canvas, f"id={item['frame_id']} t={item['timestamp_sec']:.3f}s", (left + 5, top + 25), cv2.FONT_HERSHEY_SIMPLEX, .48, (0, 0, 0), 1)
                canvas[top + 40:top + 40 + image.shape[0], left + 5:left + 5 + image.shape[1]] = image
            cv2.imwrite(str(path), canvas, [cv2.IMWRITE_JPEG_QUALITY, 92])
            tasks.append((sample, subset, path))

    def process(task):
        sample, subset, path = task
        response_path = path.with_suffix(".response.json")
        if response_path.exists() and json.loads(response_path.read_text()).get("http_status") == 200:
            data = json.loads(response_path.read_text())
        else:
            identifiers = subset[["frame_id", "timestamp_sec"]].to_dict("records")
            prompt = "客观读取这张真实植物视频逐帧接触表。返回且仅返回JSON数组，每张图一行，字段frame_id、label、confidence(0到1)、description。输入图上有帧ID和源PTS。GLOBAL仅表示整盆/大部分植物及整体背景参照可见；LOCAL表示只见部分叶片/冠层近景、整株/盆的整体参照明显缺失；APPROACH只有连续帧可见明确逐步接近才用；TRANSITION是明显切换的中间状态；无法确认用UNKNOWN。不能凭静态图推断真实相机平移、尺度、完整360度环绕、植物类别、几盆或几片叶实例。俯视不自动算LOCAL，整盆俯视仍GLOBAL；不要预设每段视频有几个特写。不要以预期拍摄顺序分段。低于0.65置信度用UNKNOWN。必须逐一覆盖提供的全部frame_id。图片来自" + sample + "；帧清单：" + json.dumps(identifiers)
            payload = {"model": "agnes-2.5-flash", "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()}}]}], "temperature": .1}
            for attempt in range(3):
                time.sleep(6 if attempt == 0 else 70)
                response = requests.post("https://apihub.agnes-ai.cn/v1/chat/completions", headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, json=payload, timeout=150)
                if response.status_code != 429:
                    break
                write_json(path.with_suffix(f".rate_limit_{attempt}.json"), {"http_status": response.status_code, "response": response.json(), "created_at": now()})
                print(sample, path.name, "429 rate limit; delaying retry", flush=True)
            data = response.json()
            if response_path.exists():
                response_path.rename(path.with_suffix(".previous_error.json"))
            write_json(response_path, {"http_status": response.status_code, "response": data, "created_at": now(), "frame_ids": subset.frame_id.tolist(), "model": "agnes-2.5-flash"})
            if not response.ok:
                raise RuntimeError(f"Vision API HTTP {response.status_code}; {response_path}")
            data = {"response": data}
        text = data["response"]["choices"][0]["message"]["content"]
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            raise ValueError(f"Vision response not JSON array: {response_path}")
        labels = json.loads(match.group(0))
        expected = set(subset.frame_id.astype(int))
        if {int(item["frame_id"]) for item in labels} != expected or len(labels) != len(expected):
            raise ValueError(f"Incomplete vision review {response_path}")
        by_id = subset.set_index("frame_id").timestamp_sec.to_dict()
        records = []
        for item in labels:
            label = item["label"]
            confidence = float(item["confidence"])
            if label not in {"GLOBAL", "LOCAL", "APPROACH", "TRANSITION", "UNKNOWN"}:
                raise ValueError(f"Unsupported vision label {label}")
            if confidence < .65:
                label = "UNKNOWN"
            timestamp = float(by_id[int(item["frame_id"])])
            records.append({"frame_id": int(item["frame_id"]), "start_timestamp_sec": timestamp - .00002, "end_timestamp_sec": timestamp + .00002, "label": label, "confidence": confidence, "source": "AGNES_API_FRAME_REVIEW_NOT_HUMAN_GROUND_TRUTH", "description": item.get("description"), "response_path": str(response_path)})
        print(sample, path.name, "reviewed", len(records), flush=True)
        return sample, records

    reviewed = {sample: [] for sample in args.samples}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for sample, records in pool.map(process, tasks):
            reviewed[sample].extend(records)
    for sample, records in reviewed.items():
        records.sort(key=lambda item: item["frame_id"])
        write_json(Path(args.output) / sample / "segments" / "visual_review_overrides.json", {"segments": records, "review_model": "agnes-2.5-flash", "created_at": now(), "limitation": "Image-content interpretation only; automated API review, not human annotations or measured physical distance."})


if __name__ == "__main__":
    main()
