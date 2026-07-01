import os
import io
import base64
import tempfile
from typing import List

import streamlit as st
from PIL import Image
import cv2
from openai import OpenAI

from data_sources import get_secret


def _get_openai_client():
    api_key = get_secret("OPENAI_API_KEY", "")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _image_to_base64(uploaded_file) -> str:
    uploaded_file.seek(0)
    return base64.b64encode(uploaded_file.read()).decode("utf-8")


def _save_uploaded_video(uploaded_file) -> str:
    suffix = os.path.splitext(uploaded_file.name)[1] or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        uploaded_file.seek(0)
        tmp.write(uploaded_file.read())
        return tmp.name


def _extract_video_frames(video_path: str, max_frames: int = 6) -> List[str]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_count <= 0:
        cap.release()
        return []

    indices = []
    if frame_count <= max_frames:
        indices = list(range(frame_count))
    else:
        step = max(1, frame_count // max_frames)
        indices = [i * step for i in range(max_frames)]

    frames_b64 = []

    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue

        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            continue

        frames_b64.append(base64.b64encode(buffer.tobytes()).decode("utf-8"))

    cap.release()
    return frames_b64


def generate_boots_on_ground_notes(photo_files, video_file=None) -> str:
    client = _get_openai_client()
    if client is None:
        return "No OPENAI_API_KEY found in Streamlit secrets."

    content = [
        {
            "type": "input_text",
            "text": (
                "You are a real estate boots-on-the-ground note writer. "
                "Review the provided property photos and video frames and write clean, practical field notes "
                "for an investor analyzing repairs. "
                "Focus on visible condition only. "
                "Do not guess beyond what is reasonably visible. "
                "Organize the notes under these headings if relevant: "
                "Exterior, Roof, Windows, Interior, Kitchen, Bathrooms, Flooring, Plumbing, Electrical, HVAC, "
                "Water Heater, Foundation, Cleanout/Trash, Safety Issues, General Livability, Recommended Follow-Up. "
                "Write concise but useful investor notes in plain English."
            ),
        }
    ]

    for photo in photo_files or []:
        img_b64 = _image_to_base64(photo)
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{img_b64}",
            }
        )

    if video_file is not None:
        video_path = _save_uploaded_video(video_file)
        frame_b64_list = _extract_video_frames(video_path, max_frames=6)
        for frame_b64 in frame_b64_list:
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{frame_b64}",
                }
            )

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": content,
            }
        ],
        max_output_tokens=1200,
    )

    return response.output_text.strip()
