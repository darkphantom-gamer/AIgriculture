#!/usr/bin/env python3
"""
PyTorch/Ultralytics scanner for Farm Monitor batches.

This mirrors farm_monitor_raw_scan.py output so plantwatch.py can switch from
HEF to PT without changing the dashboard workflow, storage, or UI contract.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
from ultralytics import YOLO


def draw(frame, detections, model_name):
    color = (0, 220, 255) if model_name == "disease" else (50, 220, 80)
    h, w = frame.shape[:2]
    thick = max(3, int(round(min(w, h) / 190)))
    for det in detections:
        x1, y1, x2, y2 = map(int, det["box"])
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thick)
        text = f"{det['label']} {det['confidence']:.2f}"
        scale = max(0.7, min(1.1, w / 900))
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
        y_text = max(th + 12, y1)
        cv2.rectangle(frame, (x1, y_text - th - 13), (min(w - 1, x1 + tw + 14), y_text + 5), color, -1)
        cv2.putText(frame, text, (x1 + 7, y_text - 5), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 2, cv2.LINE_AA)


def parse_args():
    p = argparse.ArgumentParser(description="PT scanner for Farm Monitor batches.")
    p.add_argument("--model-name", choices=["disease", "ripeness"], required=True)
    p.add_argument("--pt", required=True)
    p.add_argument("--input-video", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--summary-json", required=True)
    p.add_argument("--expected-frames", type=int, required=True)
    p.add_argument("--conf", type=float, default=0.50)
    p.add_argument("--width", type=int, default=512)
    p.add_argument("--height", type=int, default=512)
    p.add_argument("--fps", type=int, default=7)
    return p.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    model = YOLO(args.pt)
    cap = cv2.VideoCapture(str(args.input_video))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open input video: {args.input_video}")

    frames = []
    frame_idx = 0
    prefix = "Disease_tmp" if args.model_name == "disease" else "Rip_tmp"

    try:
        while frame_idx < args.expected_frames:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            frame_idx += 1
            result = model.predict(frame, imgsz=int(args.width), conf=float(args.conf), save=False, verbose=False, device="cpu")[0]
            detections = []
            for box in result.boxes:
                cls_id = int(box.cls[0])
                score = float(box.conf[0])
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                detections.append({
                    "label": model.names.get(cls_id, f"class_{cls_id}"),
                    "class_id": cls_id,
                    "confidence": round(score, 4),
                    "box": [x1, y1, x2, y2],
                })
            annotated = frame.copy()
            draw(annotated, detections, args.model_name)
            out_path = out_dir / f"{prefix}_{frame_idx:03d}.jpg"
            cv2.imwrite(str(out_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 88])
            frames.append({
                "index": frame_idx,
                "detections": [
                    {
                        "label": d["label"],
                        "confidence": d["confidence"],
                        "bbox": [round(float(v), 2) for v in d["box"]],
                    }
                    for d in detections
                ],
                "annotated": str(out_path),
            })
    finally:
        cap.release()

    summary = {
        "model": args.model_name,
        "pt": str(args.pt),
        "frames_seen": frame_idx,
        "frames": frames,
        "written_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
