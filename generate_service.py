#!/usr/bin/env python3
"""
Headless Audio Generation Service for English Notebook Conversations.
Generates full dialogue MP3 and individual sentence turn MP3s using Edge TTS and pydub.
Can output presets or accept JSON configuration via stdin.
"""

import asyncio
import json
import math
import os
import re
import sys
import time

# Ensure Homebrew and standard bin paths are in PATH so pydub finds ffmpeg
os.environ["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:{os.environ.get('PATH', '')}"

import edge_tts
from pydub import AudioSegment

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKGROUNDS_DIR = os.path.join(SCRIPT_DIR, "backgrounds")

MALE_VOICES = [
    {"label": "Guy (US - Natural)", "id": "en-US-GuyNeural", "gender": "male", "accent": "US"},
    {"label": "Christopher (US - Friendly)", "id": "en-US-ChristopherNeural", "gender": "male", "accent": "US"},
    {"label": "Andrew (US - Confident)", "id": "en-US-AndrewNeural", "gender": "male", "accent": "US"},
    {"label": "Eric (US - Crisp)", "id": "en-US-EricNeural", "gender": "male", "accent": "US"},
    {"label": "Brian (US - Deep)", "id": "en-US-BrianNeural", "gender": "male", "accent": "US"},
    {"label": "Ryan (UK - British)", "id": "en-GB-RyanNeural", "gender": "male", "accent": "UK"},
    {"label": "Thomas (UK - Formal)", "id": "en-GB-ThomasNeural", "gender": "male", "accent": "UK"},
    {"label": "William (Australia)", "id": "en-AU-WilliamMultilingualNeural", "gender": "male", "accent": "AU"},
    {"label": "Liam (Canada)", "id": "en-CA-LiamNeural", "gender": "male", "accent": "CA"},
    {"label": "Shakir (Arabic - Egypt)", "id": "ar-EG-ShakirNeural", "gender": "male", "accent": "EG"},
]

FEMALE_VOICES = [
    {"label": "Jenny (US - Warm)", "id": "en-US-JennyNeural", "gender": "female", "accent": "US"},
    {"label": "Ava (US - Expressive)", "id": "en-US-AvaNeural", "gender": "female", "accent": "US"},
    {"label": "Emma (US - Casual)", "id": "en-US-EmmaNeural", "gender": "female", "accent": "US"},
    {"label": "Aria (US - Enthusiastic)", "id": "en-US-AriaNeural", "gender": "female", "accent": "US"},
    {"label": "Michelle (US - Clear)", "id": "en-US-MichelleNeural", "gender": "female", "accent": "US"},
    {"label": "Sonia (UK - British)", "id": "en-GB-SoniaNeural", "gender": "female", "accent": "UK"},
    {"label": "Libby (UK - Crisp)", "id": "en-GB-LibbyNeural", "gender": "female", "accent": "UK"},
    {"label": "Maisie (UK - Youthful)", "id": "en-GB-MaisieNeural", "gender": "female", "accent": "UK"},
    {"label": "Natasha (Australia)", "id": "en-AU-NatashaNeural", "gender": "female", "accent": "AU"},
    {"label": "Clara (Canada)", "id": "en-CA-ClaraNeural", "gender": "female", "accent": "CA"},
    {"label": "Salma (Arabic - Egypt)", "id": "ar-EG-SalmaNeural", "gender": "female", "accent": "EG"},
]

ALL_VOICES = MALE_VOICES + FEMALE_VOICES

BACKGROUND_PRESETS = [
    {"id": "none", "label": "🚫 None (Pure speech)", "filename": None},
    {"id": "coffee_shop", "label": "☕ Coffee shop (Café ambience)", "filename": "coffee_shop.mp3"},
    {"id": "office", "label": "🏢 Office (Office ambience)", "filename": "office.mp3"},
    {"id": "car", "label": "🚗 Car (Road/travel ambience)", "filename": "car.mp3"},
    {"id": "home", "label": "🏠 Home (Quiet room ambience)", "filename": "home.mp3"},
    {"id": "shopping", "label": "🛒 Shopping (Store/mall ambience)", "filename": "shopping.mp3"},
    {"id": "outside", "label": "🌳 Outside (Park/outdoor ambience)", "filename": "outside.mp3"},
]

FEMALE_NAMES = {
    "sarah", "sara", "mary", "anna", "emma", "jenny", "laila", "layla",
    "salma", "fatima", "nour", "mona", "amira", "jane", "lisa", "emily",
    "rachel", "maria", "clara", "sonia", "libby", "eva", "ava", "hoda",
    "nadia", "dina", "yasmin", "yasmine", "reem", "mariam", "marwa",
    "alice", "sophia", "olivia", "charlotte", "mia", "harper", "evelyn",
    "woman", "girl", "speaker b", "partner", "waitress", "teacher"
}


def guess_gender(speaker_name: str) -> str:
    cleaned = (speaker_name or "").lower().strip()
    return "female" if cleaned in FEMALE_NAMES else "male"


def emit_json(payload):
    print(json.dumps(payload), flush=True)


def get_presets():
    return {
        "voices": {
            "male": MALE_VOICES,
            "female": FEMALE_VOICES,
            "all": ALL_VOICES,
        },
        "backgrounds": BACKGROUND_PRESETS,
        "defaults": {
            "rate": "-10%",
            "volume": "+0%",
            "pauseMs": 500,
            "backgroundVolume": 15,
            "defaultMaleVoice": "en-US-GuyNeural",
            "defaultFemaleVoice": "en-US-JennyNeural",
        },
    }


def clean_text_snippet(text: str, max_words: int = 4) -> str:
    cleaned = re.sub(r"[^\w\s]", "", text)
    words = cleaned.split()[:max_words]
    snippet = "_".join(words).lower()
    return snippet or "turn"


def mix_background(speech_audio: AudioSegment, background_path: str, volume_percent: int = 15) -> AudioSegment:
    if not background_path or not os.path.exists(background_path) or volume_percent <= 0:
        return speech_audio

    try:
        bg = AudioSegment.from_file(background_path)
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to load background audio: {e}\n")
        return speech_audio

    ratio = max(0.01, min(1.0, volume_percent / 100.0))
    volume_db = 20 * math.log10(ratio) - 4
    bg = bg + volume_db

    target_duration = len(speech_audio) + 500
    if len(bg) < target_duration:
        loops = (target_duration // len(bg)) + 2
        bg = (bg * loops)[:target_duration]
    else:
        bg = bg[:target_duration]

    bg = bg.fade_in(600).fade_out(1500)
    return bg.overlay(speech_audio)


async def generate_turn_audio(text: str, voice: str, rate: str, volume: str, out_path: str):
    comm = edge_tts.Communicate(text=text, voice=voice, rate=rate, volume=volume)
    await comm.save(out_path)


async def run_generation(config):
    conv_id = config.get("conversationId") or f"new_{int(time.time())}"
    raw_lines = config.get("lines") or []
    voice_map = config.get("voiceMap") or {}
    rate = config.get("rate") or "-10%"
    volume = config.get("volume") or "+0%"
    pause_ms = int(config.get("pauseMs") if config.get("pauseMs") is not None else 500)
    bg_preset = config.get("backgroundPreset") or "none"
    bg_volume = int(config.get("backgroundVolume") if config.get("backgroundVolume") is not None else 15)
    output_dir = config.get("outputDir")

    if not output_dir or not os.path.isdir(output_dir):
        raise ValueError(f"Invalid output directory: {output_dir}")

    valid_lines = [l for l in raw_lines if (l.get("en") or "").strip()]
    if not valid_lines:
        raise ValueError("No valid dialogue lines with English text provided.")

    total_turns = len(valid_lines)
    timestamp = int(time.time() * 1000)

    # Resolve voices for each speaker
    # Auto-assign alternating voices if speaker voices not explicitly mapped
    male_defaults = ["en-US-GuyNeural", "en-US-ChristopherNeural", "en-US-AndrewNeural"]
    female_defaults = ["en-US-JennyNeural", "en-US-AvaNeural", "en-US-EmmaNeural"]
    used_speakers = {}
    m_idx = 0
    f_idx = 0

    for line in valid_lines:
        spk = (line.get("speaker") or "Speaker").strip()
        if spk not in used_speakers:
            if spk in voice_map and voice_map[spk]:
                used_speakers[spk] = voice_map[spk]
            else:
                gender = guess_gender(spk)
                if gender == "female":
                    used_speakers[spk] = female_defaults[f_idx % len(female_defaults)]
                    f_idx += 1
                else:
                    used_speakers[spk] = male_defaults[m_idx % len(male_defaults)]
                    m_idx += 1

    emit_json({
        "type": "start",
        "total": total_turns,
        "speakers": used_speakers,
        "message": f"Starting generation for {total_turns} dialogue turns...",
    })

    generated_parts = []
    updated_lines = []

    # 1. Generate individual turn MP3s
    for idx, line in enumerate(valid_lines):
        line_id = line.get("id") or (idx + 1)
        speaker = (line.get("speaker") or "Speaker").strip()
        text = line.get("en").strip()
        voice = used_speakers.get(speaker, "en-US-GuyNeural")

        snippet = clean_text_snippet(text)
        filename = f"conv_{conv_id}_turn_{line_id}_{timestamp}_{snippet}.mp3"
        out_path = os.path.join(output_dir, filename)

        progress_pct = round(((idx + 1) / (total_turns + 1.2)) * 100)
        emit_json({
            "type": "progress",
            "current": idx + 1,
            "total": total_turns,
            "percent": progress_pct,
            "message": f"Generating turn {idx + 1}/{total_turns} ({speaker})...",
        })

        await generate_turn_audio(text=text, voice=voice, rate=rate, volume=volume, out_path=out_path)
        generated_parts.append(out_path)

        updated_line = dict(line)
        updated_line["audioFilename"] = filename
        updated_line["audioUrl"] = f"/uploads/{filename}"
        updated_line["speaker"] = speaker
        updated_lines.append(updated_line)

    # 2. Combine all parts into full conversation audio
    emit_json({
        "type": "progress",
        "current": total_turns,
        "total": total_turns,
        "percent": 90,
        "message": "Stitching turns and applying background sound...",
    })

    full_audio = AudioSegment.empty()
    pause = AudioSegment.silent(duration=max(0, pause_ms))

    for i, part_path in enumerate(generated_parts):
        seg = AudioSegment.from_mp3(part_path)
        full_audio += seg
        if i < len(generated_parts) - 1:
            full_audio += pause

    # Mix background audio if requested
    if bg_preset and bg_preset != "none":
        preset_item = next((p for p in BACKGROUND_PRESETS if p["id"] == bg_preset), None)
        if preset_item and preset_item["filename"]:
            bg_path = os.path.join(BACKGROUNDS_DIR, preset_item["filename"])
            if os.path.exists(bg_path):
                emit_json({
                    "type": "progress",
                    "current": total_turns,
                    "total": total_turns,
                    "percent": 95,
                    "message": f"Mixing ambient ambience ({preset_item['label']})...",
                })
                full_audio = mix_background(full_audio, bg_path, bg_volume)

    full_filename = f"conv_{conv_id}_full_{timestamp}.mp3"
    full_path = os.path.join(output_dir, full_filename)
    full_audio.export(full_path, format="mp3", bitrate="192k")

    duration_sec = len(full_audio) / 1000.0

    emit_json({
        "type": "result",
        "status": "success",
        "fullAudioFilename": full_filename,
        "fullAudioUrl": f"/uploads/{full_filename}",
        "durationSec": duration_sec,
        "lines": updated_lines,
        "message": f"Successfully generated full audio ({duration_sec:.1f}s) and {total_turns} turn audio files!",
    })


def main():
    if "--presets" in sys.argv:
        emit_json(get_presets())
        return

    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            emit_json({"type": "error", "message": "No input JSON received on stdin."})
            sys.exit(1)

        config = json.loads(raw_input)
        asyncio.run(run_generation(config))
    except Exception as e:
        emit_json({
            "type": "error",
            "message": str(e),
        })
        sys.exit(1)


if __name__ == "__main__":
    main()
