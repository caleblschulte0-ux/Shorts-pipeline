from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence


def _write_json(path: str, value: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def dhash(path: str, hash_size: int = 8) -> str:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Pillow is required for dhash") from exc
    with Image.open(path) as image:
        image = image.convert("L").resize((hash_size + 1, hash_size))
        pixels = list(image.getdata())
    bits = []
    for row in range(hash_size):
        offset = row * (hash_size + 1)
        bits.extend(pixels[offset + column] > pixels[offset + column + 1] for column in range(hash_size))
    value = sum(1 << index for index, bit in enumerate(bits) if bit)
    return f"{value:0{hash_size * hash_size // 4}x}"


def clip_scores(image_paths: Sequence[str], prompt: str, model_name: str) -> list[dict[str, object]]:
    try:
        import torch
        from PIL import Image
        from transformers import CLIPModel, CLIPProcessor
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("clip-score requires torch, transformers, and Pillow") from exc
    model = CLIPModel.from_pretrained(model_name)
    processor = CLIPProcessor.from_pretrained(model_name)
    images = [Image.open(path).convert("RGB") for path in image_paths]
    inputs = processor(text=[prompt] * len(images), images=images, return_tensors="pt", padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
    probabilities = outputs.logits_per_image[:, 0].softmax(dim=0).tolist()
    return [{"path": path, "score": float(score), "prompt": prompt, "model": model_name} for path, score in zip(image_paths, probabilities)]


def mediapipe_track(video: str, mode: str) -> dict[str, object]:
    try:
        import cv2
        import mediapipe as mp
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("mediapipe-track requires opencv-python and mediapipe") from exc
    capture = cv2.VideoCapture(video)
    if not capture.isOpened():
        raise RuntimeError(f"unable to open video: {video}")
    frame_count = 0
    detected_frames = 0
    if mode == "pose":
        detector = mp.solutions.pose.Pose(static_image_mode=False)
        process = lambda image: detector.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).pose_landmarks is not None
    elif mode == "hands":
        detector = mp.solutions.hands.Hands(static_image_mode=False)
        process = lambda image: bool(detector.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).multi_hand_landmarks)
    elif mode == "face":
        detector = mp.solutions.face_detection.FaceDetection(model_selection=0)
        process = lambda image: bool(detector.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).detections)
    else:
        raise ValueError("mode must be pose, face, or hands")
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frame_count += 1
            if process(frame):
                detected_frames += 1
    finally:
        capture.release()
        detector.close()
    return {"video": video, "mode": mode, "frames": frame_count, "detected_frames": detected_frames, "coverage": detected_frames / frame_count if frame_count else 0.0}


def sam2_mask(image: str, checkpoint: str, config: str, prompt_json: str, output: str) -> None:
    """Optional SAM 2 runner kept explicit because model APIs and checkpoints vary.

    The implementation deliberately refuses silent guessing. Claude should adapt this
    worker to the exact installed SAM 2 release and test fixture before enabling it.
    """
    raise RuntimeError(
        "SAM 2 worker requires a release-pinned adapter. Inputs were validated but no model was run: "
        f"image={image}, checkpoint={checkpoint}, config={config}, prompt={prompt_json}, output={output}"
    )


def moviepy_render(timeline_path: str, output: str) -> None:
    try:
        from moviepy import AudioFileClip, CompositeAudioClip, CompositeVideoClip, VideoFileClip
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("moviepy-render requires moviepy") from exc
    timeline = json.loads(Path(timeline_path).read_text(encoding="utf-8"))
    video_clips = []
    audio_clips = []
    for track in timeline["tracks"]["children"]:
        cursor = 0.0
        for child in track["children"]:
            schema = child.get("OTIO_SCHEMA", "")
            duration = child["source_range"]["duration"]["value"] / child["source_range"]["duration"]["rate"]
            if schema.startswith("Gap"):
                cursor += duration
                continue
            source = child["media_reference"]["target_url"]
            start = child["source_range"]["start_time"]["value"] / child["source_range"]["start_time"]["rate"]
            if track["kind"] == "Audio":
                audio_clips.append(AudioFileClip(source).subclipped(start, start + duration).with_start(cursor))
            else:
                video_clips.append(VideoFileClip(source).subclipped(start, start + duration).with_start(cursor))
            cursor += duration
    composition = CompositeVideoClip(video_clips, size=(timeline["metadata"]["width"], timeline["metadata"]["height"]))
    if audio_clips:
        composition = composition.with_audio(CompositeAudioClip(audio_clips))
    composition.write_videofile(output, fps=timeline["metadata"]["fps"], codec="libx264", audio_codec="aac")


def main() -> int:
    parser = argparse.ArgumentParser(description="Optional local workers for the review-only free capability stack")
    subparsers = parser.add_subparsers(dest="command", required=True)
    hashes = subparsers.add_parser("dhash")
    hashes.add_argument("images", nargs="+")
    hashes.add_argument("--output", required=True)
    clip = subparsers.add_parser("clip-score")
    clip.add_argument("images", nargs="+")
    clip.add_argument("--prompt", required=True)
    clip.add_argument("--model", default="openai/clip-vit-base-patch32")
    clip.add_argument("--output", required=True)
    tracking = subparsers.add_parser("mediapipe-track")
    tracking.add_argument("--video", required=True)
    tracking.add_argument("--mode", choices=("pose", "face", "hands"), default="pose")
    tracking.add_argument("--output", required=True)
    sam = subparsers.add_parser("sam2-mask")
    sam.add_argument("--image", required=True)
    sam.add_argument("--checkpoint", required=True)
    sam.add_argument("--config", required=True)
    sam.add_argument("--prompt-json", required=True)
    sam.add_argument("--output", required=True)
    moviepy = subparsers.add_parser("moviepy-render")
    moviepy.add_argument("--timeline", required=True)
    moviepy.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "dhash":
        _write_json(args.output, [{"path": path, "dhash": dhash(path)} for path in args.images])
    elif args.command == "clip-score":
        _write_json(args.output, clip_scores(args.images, args.prompt, args.model))
    elif args.command == "mediapipe-track":
        _write_json(args.output, mediapipe_track(args.video, args.mode))
    elif args.command == "sam2-mask":
        sam2_mask(args.image, args.checkpoint, args.config, args.prompt_json, args.output)
    elif args.command == "moviepy-render":
        moviepy_render(args.timeline, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
