import asyncio
import math
import os
import re
import sys
import tempfile
import edge_tts
from pydub import AudioSegment

# Default voice choices
DEFAULT_VOICES = {
    "Ahmed": "en-US-GuyNeural",
    "John": "en-US-ChristopherNeural",
}

FALLBACK_VOICE = "en-US-GuyNeural"


def read_conversation(filename: str) -> str:
    """Read conversation text from file."""
    with open(filename, "r", encoding="utf-8") as file:
        return file.read()


def parse_conversation(text: str):
    """
    Parse text into a list of (speaker, message) tuples.
    Format expected: 'Speaker: Message' on each line.
    """
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        match = re.match(r"^([^:]+):\s*(.+)$", line)
        if not match:
            continue

        speaker = match.group(1).strip()
        message = match.group(2).strip()
        lines.append((speaker, message))

    return lines


def extract_speakers(conversation):
    """Return an ordered list of unique speakers found in the conversation."""
    seen = set()
    speakers = []
    for speaker, _ in conversation:
        if speaker not in seen:
            seen.add(speaker)
            speakers.append(speaker)
    return speakers


def make_safe_sentence_filename(index: int, speaker: str, text: str, max_words: int = 5) -> str:
    """Generate a clean, descriptive MP3 filename for an individual sentence."""
    clean = re.sub(r"['\"’]", "", text)
    words = re.findall(r"\w+", clean)
    snippet = "_".join(words[:max_words])
    safe_speaker = re.sub(r"[^\w\-]", "", speaker)
    if snippet:
        return f"{index + 1:02d}_{safe_speaker}_{snippet}.mp3"
    return f"{index + 1:02d}_{safe_speaker}.mp3"


def sanitize_directory_name(name: str) -> str:
    """Clean a string for use as a folder or file name."""
    clean = re.sub(r"[\\/*?:\'\"<>|]", "", name)
    clean = re.sub(r"\s+", "_", clean.strip())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean if clean else "Conversation"


async def generate_speech_parts(
    conversation,
    voice_map,
    target_dir: str,
    rate="-10%",
    volume="+0%",
    progress_callback=None,
    is_cancelled=None,
):
    """
    Generate audio files for each line using Edge TTS and save into target directory.
    """
    os.makedirs(target_dir, exist_ok=True)
    audio_files = []
    sentence_records = []
    total = len(conversation)

    for index, (speaker, message) in enumerate(conversation):
        if is_cancelled and is_cancelled():
            raise asyncio.CancelledError("Audio generation cancelled by user.")

        voice = voice_map.get(speaker, FALLBACK_VOICE)
        filename = make_safe_sentence_filename(index, speaker, message)
        part_path = os.path.join(target_dir, filename)

        if progress_callback:
            progress_callback(
                f"Generating sentence {index + 1}/{total} ({speaker})...",
                (index + 0.5) / total,
            )

        communicate = edge_tts.Communicate(
            text=message,
            voice=voice,
            rate=rate,
            volume=volume,
        )
        await communicate.save(part_path)
        audio_files.append(part_path)
        sentence_records.append({
            "index": index + 1,
            "speaker": speaker,
            "text": message,
            "filename": filename,
            "file_path": part_path,
        })

        if progress_callback:
            progress_callback(
                f"Completed sentence {index + 1}/{total} ({speaker})",
                (index + 1.0) / total,
            )

    return audio_files, sentence_records


def mix_background_audio(
    speech_audio: AudioSegment,
    background_path: str,
    volume_percent: int = 15,
) -> AudioSegment:
    """
    Mix background ambience into speech audio.
    """
    if not background_path or not os.path.exists(background_path) or volume_percent <= 0:
        return speech_audio

    try:
        bg = AudioSegment.from_file(background_path)
    except Exception as e:
        print(f"Warning: Could not load background audio '{background_path}': {e}")
        return speech_audio

    ratio = max(0.01, min(1.0, volume_percent / 100.0))
    volume_db = 20 * math.log10(ratio) - 4
    bg = bg + volume_db

    target_duration_ms = len(speech_audio) + 500

    if len(bg) < target_duration_ms:
        loops_needed = (target_duration_ms // len(bg)) + 2
        bg = (bg * loops_needed)[:target_duration_ms]
    else:
        bg = bg[:target_duration_ms]

    bg = bg.fade_in(600).fade_out(1500)
    return bg.overlay(speech_audio)


def combine_audio_files(
    files,
    output_file: str,
    pause_ms: int = 500,
    background_path: str = None,
    background_volume: int = 15,
    progress_callback=None,
    is_cancelled=None,
):
    """
    Combine individual MP3 files with a silence pause between speakers and optional ambient background.
    """
    if not files:
        raise ValueError("No audio parts to combine.")

    if progress_callback:
        progress_callback("Merging audio clips and applying pause gaps...", 0.88)

    final_audio = AudioSegment.empty()
    pause = AudioSegment.silent(duration=max(0, pause_ms))

    total = len(files)
    for idx, filename in enumerate(files):
        if is_cancelled and is_cancelled():
            raise RuntimeError("Audio combining cancelled by user.")

        audio = AudioSegment.from_mp3(filename)
        final_audio += audio
        if idx < total - 1:  # Don't add pause at the very end
            final_audio += pause

    # Mix background audio if provided
    if background_path and os.path.exists(background_path) and background_volume > 0:
        if progress_callback:
            progress_callback("Mixing ambient background audio...", 0.93)
        final_audio = mix_background_audio(
            final_audio,
            background_path=background_path,
            volume_percent=background_volume,
        )

    output_dir = os.path.dirname(os.path.abspath(output_file))
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    if progress_callback:
        progress_callback("Exporting MP3...", 0.96)

    final_audio.export(output_file, format="mp3", bitrate="192k")

    duration_sec = len(final_audio) / 1000.0
    file_size_bytes = os.path.getsize(output_file)

    if progress_callback:
        progress_callback("Done!", 1.0)

    return {
        "output_file": output_file,
        "duration_sec": duration_sec,
        "file_size_bytes": file_size_bytes,
        "total_lines": total,
    }


def cleanup_temp_files(files, temp_dir=None):
    """Safely remove temporary MP3 parts and temp directory."""
    for filename in files:
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except OSError:
            pass

    if temp_dir and os.path.exists(temp_dir):
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass


async def convert_conversation(
    text: str,
    voice_map: dict,
    mode: str = "project",  # "single" (one MP3 file) or "project" (directory with full, text & sentences)
    output_dir: str = None,
    conversation_name: str = None,
    single_output_file: str = None,
    rate: str = "-10%",
    volume: str = "+0%",
    pause_ms: int = 500,
    background_path: str = None,
    background_volume: int = 15,
    progress_callback=None,
    is_cancelled=None,
):
    """
    End-to-end conversation generation:
    - Mode 'single': Generates a single MP3 audio file directly.
    - Mode 'project': Creates a dedicated directory containing:
        1. full_conversation.mp3 (complete dialogue with background ambience)
        2. conversation.txt (full dialogue transcript)
        3. sentences/ (folder with individual MP3 files for every sentence)
    """
    conversation = parse_conversation(text)
    if not conversation:
        raise ValueError("No valid dialogue lines found in format 'Speaker: message'.")

    # MODE 1: Single MP3 File Mode
    if mode == "single":
        if not single_output_file:
            single_output_file = os.path.abspath("conversation.mp3")

        out_path = os.path.abspath(single_output_file)
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        temp_dir = tempfile.mkdtemp(prefix="conv_tts_single_")
        audio_files = []
        try:
            audio_files, _ = await generate_speech_parts(
                conversation=conversation,
                voice_map=voice_map,
                target_dir=temp_dir,
                rate=rate,
                volume=volume,
                progress_callback=progress_callback,
                is_cancelled=is_cancelled,
            )

            combine_result = combine_audio_files(
                files=audio_files,
                output_file=out_path,
                pause_ms=pause_ms,
                background_path=background_path,
                background_volume=background_volume,
                progress_callback=progress_callback,
                is_cancelled=is_cancelled,
            )

            return {
                "mode": "single",
                "full_audio_file": out_path,
                "output_file": out_path,
                "duration_sec": combine_result["duration_sec"],
                "file_size_bytes": combine_result["file_size_bytes"],
                "total_lines": len(conversation),
                "sentence_files": [],
                "conversation_dir": out_dir,
                "conversation_name": os.path.splitext(os.path.basename(out_path))[0],
            }
        finally:
            cleanup_temp_files(audio_files, temp_dir)

    # MODE 2: Full Project Directory Mode
    else:
        if not conversation_name:
            first_line = conversation[0][1] if conversation else "Conversation"
            conversation_name = sanitize_directory_name(first_line[:30])

        if not output_dir:
            output_dir = os.path.abspath(conversation_name)

        conv_dir = os.path.abspath(output_dir)
        os.makedirs(conv_dir, exist_ok=True)

        # 1. Save dialogue transcript in the directory
        transcript_path = os.path.join(conv_dir, "conversation.txt")
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(text.strip() + "\n")

        # 2. Generate individual sentence MP3 files into sentences/ subfolder
        sentences_dir = os.path.join(conv_dir, "sentences")
        audio_files, sentence_records = await generate_speech_parts(
            conversation=conversation,
            voice_map=voice_map,
            target_dir=sentences_dir,
            rate=rate,
            volume=volume,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
        )

        # 3. Combine into full conversation MP3 in the root of the folder
        full_output_file = os.path.join(conv_dir, "full_conversation.mp3")
        combine_result = combine_audio_files(
            files=audio_files,
            output_file=full_output_file,
            pause_ms=pause_ms,
            background_path=background_path,
            background_volume=background_volume,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
        )

        return {
            "mode": "project",
            "conversation_dir": conv_dir,
            "conversation_name": os.path.basename(conv_dir),
            "full_audio_file": full_output_file,
            "text_file": transcript_path,
            "sentences_dir": sentences_dir,
            "sentence_files": sentence_records,
            "duration_sec": combine_result["duration_sec"],
            "file_size_bytes": combine_result["file_size_bytes"],
            "total_lines": len(conversation),
        }


# CLI Execution
async def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else "conversation.txt"
    target = sys.argv[2] if len(sys.argv) > 2 else "conversation.mp3"

    print(f"Reading conversation from '{input_file}'...")
    text = read_conversation(input_file)
    conversation = parse_conversation(text)

    if not conversation:
        print("No valid conversation found.")
        return

    print(f"Found {len(conversation)} dialogue lines.\n")

    def cli_progress(status_msg, progress_fraction):
        print(f"[{int(progress_fraction * 100):3d}%] {status_msg}")

    # Determine mode based on target (if ends with .mp3 -> single file mode, else project dir mode)
    if target.endswith(".mp3"):
        mode = "single"
        print(f"Exporting in SINGLE FILE mode to: {target}")
        result = await convert_conversation(
            text=text,
            voice_map=DEFAULT_VOICES,
            mode="single",
            single_output_file=os.path.abspath(target),
            rate="-10%",
            volume="+0%",
            pause_ms=500,
            progress_callback=cli_progress,
        )
        print(f"\nDone! 🎉")
        print(f"MP3 created: {result['full_audio_file']}")
        print(f"Duration: {result['duration_sec']:.1f}s | Size: {result['file_size_bytes'] / 1024:.1f} KB")
    else:
        mode = "project"
        print(f"Exporting in FULL PROJECT DIRECTORY mode to: {target}")
        result = await convert_conversation(
            text=text,
            voice_map=DEFAULT_VOICES,
            mode="project",
            output_dir=os.path.abspath(target),
            conversation_name=target,
            rate="-10%",
            volume="+0%",
            pause_ms=500,
            progress_callback=cli_progress,
        )
        print(f"\nDone! 🎉")
        print(f"Directory: {result['conversation_dir']}")
        print(f"Full MP3: {result['full_audio_file']}")
        print(f"Sentences: {len(result['sentence_files'])} individual files in {result['sentences_dir']}")
        print(f"Duration: {result['duration_sec']:.1f}s | Size: {result['file_size_bytes'] / 1024:.1f} KB")


if __name__ == "__main__":
    asyncio.run(main())
