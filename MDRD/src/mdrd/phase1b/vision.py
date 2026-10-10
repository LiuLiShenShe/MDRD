from __future__ import annotations

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import requests

from mdrd.common import now, sha256, write_json


def propose_boxes(video_dir, destination, frame_ids, workers=4):
    token = os.environ.get("AGNES_API_KEY")
    if not token:
        raise RuntimeError("AGNES_API_KEY required for optional automated visual box proposals")
    video_dir, destination = Path(video_dir), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    instruction = 'Return one JSON object only: {"box_xyxy_normalized":[x1,y1,x2,y2],"plant_visible":true,"pot_visible":false,"uncertainty":"..."}. Box 0..1 bounds visible plant leaves/stems, exclude pot and background as far as possible. If plant cannot be located, plant_visible=false. This is a proposed prompt, not a verified segmentation.'

    def query(frame_id):
        filename = f"frame_{frame_id:06d}.png"
        path = video_dir / "sfm_images" / filename
        image = cv2.imread(str(path))
        if image is None:
            return {"frame_id": frame_id, "status": "MISSING_IMAGE"}
        image = cv2.resize(image, (480, round(image.shape[0] * 480 / image.shape[1])))
        _, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 72])
        content = [{"type": "text", "text": instruction}, {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(encoded).decode()}}]
        try:
            response = requests.post("https://apihub.agnes-ai.cn/v1/chat/completions", headers={"Authorization": f"Bearer {token}"}, json={"model": "agnes-2.5-flash", "messages": [{"role": "user", "content": content}], "max_tokens": 450}, timeout=100)
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"].strip()
            prompt = json.loads(text.removeprefix("```json").removesuffix("```").strip())
            box = prompt.get("box_xyxy_normalized")
            valid = prompt.get("plant_visible") is True and isinstance(box, list) and len(box) == 4 and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1
            return {"frame_id": frame_id, "filename": filename, "image_path": str(path), "image_sha256": sha256(path), "status": "PROVISIONAL_AUTO" if valid else "UNCERTAIN", "source": "AGNES_API_AUTOMATED_NOT_HUMAN", "human_confirmed": False, "box_xyxy_normalized": box, "plant_visible": prompt.get("plant_visible"), "pot_visible": prompt.get("pot_visible"), "uncertainty": prompt.get("uncertainty")}
        except Exception as exception:
            return {"frame_id": frame_id, "filename": filename, "status": "VISION_REQUEST_FAILED", "error": f"{type(exception).__name__}: {exception}"}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(query, frame_ids))
    write_json(destination / "prompt_proposals.json", {"created_at": now(), "video_id": video_dir.name, "status": "PROVISIONAL_AUTO_NOT_HUMAN", "prompts": rows})
    return rows
