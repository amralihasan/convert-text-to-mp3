import asyncio
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


async def generate_speech_parts(
    conversation,
    voice_map,
    rate="-10%",
    volume="+0%",
    progress_callback=None,
    is_cancelled=None,
    temp_dir=None,
):
    """
    Generate temporary audio files for each line using Edge TTS.
    """
    if temp_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="conv_tts_")

    audio_files = []
    total = len(conversation)

    for index, (speaker, message) in enumerate(conversation):
        if is_cancelled and is_cancelled():
            raise asyncio.CancelledError("Audio generation cancelled by user.")

        voice = voice_map.get(speaker, FALLBACK_VOICE)
        part_path = os.path.join(temp_dir, f"part_{index:04d}.mp3")

        if progress_callback:
            progress_callback(
                f"Generating audio for line {index + 1}/{total} ({speaker})...",
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

        if progress_callback:
            progress_callback(
                f"Completed line {index + 1}/{total} ({speaker})",
                (index + 1.0) / total,
            )

    return audio_files, temp_dir


def combine_audio_files(
    files,
    output_file: str,
    pause_ms: int = 500,
    progress_callback=None,
    is_cancelled=None,
):
    """
    Combine individual MP3 files with a silence pause between speakers.
    """
    if not files:
        raise ValueError("No audio parts to combine.")

    if progress_callback:
        progress_callback("Merging audio clips and applying pause gaps...", 0.9)

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

    output_dir = os.path.dirname(os.path.abspath(output_file))
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    if progress_callback:
        progress_callback("Exporting final MP3...", 0.95)

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
    output_file: str = "conversation.mp3",
    rate: str = "-10%",
    volume: str = "+0%",
    pause_ms: int = 500,
    progress_callback=None,
    is_cancelled=None,
):
    """
    End-to-end conversion from raw text to combined MP3.
    """
    conversation = parse_conversation(text)
    if not conversation:
        raise ValueError("No valid dialogue lines found in format 'Speaker: message'.")

    audio_files, temp_dir = await generate_speech_parts(
        conversation,
        voice_map=voice_map,
        rate=rate,
        volume=volume,
        progress_callback=progress_callback,
        is_cancelled=is_cancelled,
    )

    try:
        result = combine_audio_files(
            audio_files,
            output_file=output_file,
            pause_ms=pause_ms,
            progress_callback=progress_callback,
            is_cancelled=is_cancelled,
        )
        return result
    finally:
        cleanup_temp_files(audio_files, temp_dir)


# CLI Execution
async def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else "conversation.txt"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "conversation.mp3"

    print(f"Reading conversation from '{input_file}'...")
    text = read_conversation(input_file)
    conversation = parse_conversation(text)

    if not conversation:
        print("No valid conversation found.")
        return

    print(f"Found {len(conversation)} dialogue lines.\n")

    def cli_progress(status_msg, progress_fraction):
        print(f"[{int(progress_fraction * 100):3d}%] {status_msg}")

    result = await convert_conversation(
        text=text,
        voice_map=DEFAULT_VOICES,
        output_file=output_file,
        rate="-10%",
        volume="+0%",
        pause_ms=500,
        progress_callback=cli_progress,
    )

    print(f"\nDone! 🎉")
    print(f"MP3 created: {result['output_file']}")
    print(f"Duration: {result['duration_sec']:.1f}s | Size: {result['file_size_bytes'] / 1024:.1f} KB")


if __name__ == "__main__":
    asyncio.run(main())
