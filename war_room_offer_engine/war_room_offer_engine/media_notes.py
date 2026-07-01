import os
import io
import base64
import tempfile
from typing import List, Any

from PIL import Image
import cv2
from openai import OpenAI

from data_sources import get_secret


MODEL_NAME = "gpt-4.1-mini"

MAX_PHOTOS_TO_ANALYZE = 40
PHOTO_BATCH_SIZE = 6
MAX_VIDEO_FRAMES = 10


def _get_openai_client():
    api_key = get_secret("OPENAI_API_KEY", "")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _uploaded_name(uploaded_file: Any) -> str:
    return str(getattr(uploaded_file, "name", "") or "")


def _is_photo(uploaded_file: Any) -> bool:
    name = _uploaded_name(uploaded_file).lower()
    return name.endswith((".jpg", ".jpeg", ".png", ".webp"))


def _is_video(uploaded_file: Any) -> bool:
    name = _uploaded_name(uploaded_file).lower()
    return name.endswith((".mp4", ".mov", ".m4v", ".avi"))


def _compress_image_to_base64(uploaded_file: Any, max_width: int = 1200) -> str:
    uploaded_file.seek(0)

    image = Image.open(uploaded_file).convert("RGB")

    width, height = image.size
    if width > max_width:
        new_height = int(height * (max_width / width))
        image = image.resize((max_width, new_height))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=78)

    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _save_uploaded_video(uploaded_file: Any) -> str:
    suffix = os.path.splitext(_uploaded_name(uploaded_file))[1] or ".mp4"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        uploaded_file.seek(0)
        tmp.write(uploaded_file.read())
        return tmp.name


def _extract_video_frames(video_path: str, max_frames: int = MAX_VIDEO_FRAMES) -> List[str]:
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        return []

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    if frame_count <= 0:
        cap.release()
        return []

    if frame_count <= max_frames:
        indices = list(range(frame_count))
    else:
        step = max(1, frame_count // max_frames)
        indices = [i * step for i in range(max_frames)]

    frames_b64: List[str] = []

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


def _chunk_list(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _analyze_media_batch(client: OpenAI, batch_files: list[Any], batch_number: int) -> str:
    content = [
        {
            "type": "input_text",
            "text": (
                "You are reviewing real estate boots-on-the-ground property photos for an investor. "
                "Write practical condition notes only from what is visible. "
                "Do not exaggerate. Do not guess hidden repairs. "
                "Call out visible repair items, investor concerns, and what needs contractor verification. "
                "Use plain English. "
                f"This is photo batch {batch_number}. "
                "Organize under headings when possible: Exterior, Roof, Windows, Interior, Kitchen, Bathrooms, "
                "Flooring, Plumbing, Electrical, HVAC, Water Heater, Foundation, Cleanout/Trash, Safety Issues, "
                "Livability, Follow-Up Needed."
            ),
        }
    ]

    for uploaded_file in batch_files:
        try:
            image_b64 = _compress_image_to_base64(uploaded_file)
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{image_b64}",
                }
            )
        except Exception as exc:
            content.append(
                {
                    "type": "input_text",
                    "text": f"Could not process image {_uploaded_name(uploaded_file)}. Error: {exc}",
                }
            )

    response = client.responses.create(
        model=MODEL_NAME,
        input=[
            {
                "role": "user",
                "content": content,
            }
        ],
        max_output_tokens=1200,
    )

    return response.output_text.strip()


def _analyze_video_frames(client: OpenAI, video_file: Any) -> str:
    if video_file is None:
        return ""

    video_path = _save_uploaded_video(video_file)
    frames = _extract_video_frames(video_path, max_frames=MAX_VIDEO_FRAMES)

    if not frames:
        return "Video was uploaded, but no readable frames could be extracted."

    content = [
        {
            "type": "input_text",
            "text": (
                "You are reviewing sampled frames from a real estate boots-on-the-ground walkthrough video. "
                "Write practical investor repair notes only from what is visible in these frames. "
                "This is not full audio transcription yet. "
                "Focus on visible condition, damage, mechanicals, trash, flooring, kitchen, bathrooms, water damage, "
                "livability, and follow-up items."
            ),
        }
    ]

    for frame_b64 in frames:
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{frame_b64}",
            }
        )

    response = client.responses.create(
        model=MODEL_NAME,
        input=[
            {
                "role": "user",
                "content": content,
            }
        ],
        max_output_tokens=1200,
    )

    return response.output_text.strip()


def _combine_notes(client: OpenAI, photo_notes: list[str], video_notes: str, total_photos: int) -> str:
    combined_source_text = ""

    for idx, notes in enumerate(photo_notes, start=1):
        combined_source_text += f"\n\nPHOTO BATCH {idx} NOTES:\n{notes}"

    if video_notes:
        combined_source_text += f"\n\nVIDEO FRAME NOTES:\n{video_notes}"

    prompt = (
        "You are the final boots-on-the-ground report writer for a real estate investor. "
        "Combine the batch notes into one clean, useful property condition report. "
        "Do not duplicate the same repair item over and over. "
        "Make it useful for estimating repairs and deciding whether to make an offer. "
        "Use plain English. "
        "Be specific where possible. "
        "Call out visible red flags and contractor follow-up items. "
        "End with a short investor summary explaining whether this looks light, medium, or heavy repair based on the media.\n\n"
        f"Total photos uploaded: {total_photos}\n"
        f"Photos analyzed: {min(total_photos, MAX_PHOTOS_TO_ANALYZE)}\n"
        f"{combined_source_text}"
    )

    response = client.responses.create(
        model=MODEL_NAME,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt,
                    }
                ],
            }
        ],
        max_output_tokens=1800,
    )

    return response.output_text.strip()


def generate_boots_on_ground_notes(photo_files, video_file=None) -> str:
    client = _get_openai_client()

    if client is None:
        return (
            "No OPENAI_API_KEY found in Streamlit secrets. "
            "Add OPENAI_API_KEY in Streamlit Secrets, save, and reboot the app."
        )

    photo_files = [f for f in (photo_files or []) if _is_photo(f)]
    video_file = video_file if video_file is not None and _is_video(video_file) else None

    if not photo_files and video_file is None:
        return "No photos or video were uploaded."

    photos_to_analyze = photo_files[:MAX_PHOTOS_TO_ANALYZE]
    photo_batches = _chunk_list(photos_to_analyze, PHOTO_BATCH_SIZE)

    photo_notes: list[str] = []

    for batch_number, batch in enumerate(photo_batches, start=1):
        notes = _analyze_media_batch(client, batch, batch_number)
        photo_notes.append(notes)

    video_notes = ""
    if video_file is not None:
        video_notes = _analyze_video_frames(client, video_file)

    final_notes = _combine_notes(
        client=client,
        photo_notes=photo_notes,
        video_notes=video_notes,
        total_photos=len(photo_files),
    )

    if len(photo_files) > MAX_PHOTOS_TO_ANALYZE:
        final_notes += (
            f"\n\nNote: {len(photo_files)} photos were uploaded, but only the first "
            f"{MAX_PHOTOS_TO_ANALYZE} were analyzed to avoid timeout/cost issues."
        )

    if video_file is not None:
        final_notes += (
            "\n\nVideo note: This version reviews sampled video frames. "
            "Audio transcription of what the boots-on-ground person says will be added next."
        )

    return final_notes
