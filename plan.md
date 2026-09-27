أكيد يا Amr. خلّينا نعملها بشكل بسيط باستخدام **Microsoft Edge TTS**؛ ميزته إن فيه أصوات English طبيعية جدًا ومجانية للاستخدام الشخصي، والسكريبت يقدر يختار Voice مختلف لكل شخص.

### 1. Install the package

```bash
pip install edge-tts
```

### 2. Create `conversation.txt`

مثلاً:

```text
Ahmed: Hey, John! How are you doing today?

John: Hey, Ahmed! I'm doing pretty well. How about you?

Ahmed: I'm good, thanks. What are you working on these days?

John: I'm working on a new software project. It's a little difficult, but I'm enjoying it.

Ahmed: That sounds interesting. What kind of software are you building?

John: It's a small project management system. I'm building the backend with Laravel.

Ahmed: Nice! How long have you been working on it?

John: About two months. I'm hoping to finish the first version next month.

Ahmed: That's great. Are you working on it alone?

John: Mostly, yes. But sometimes I ask a friend to help me with the frontend.

Ahmed: That's a good idea. Building a project alone can be challenging.

John: Exactly. But I'm learning a lot from it.

Ahmed: That's what matters. Keep going!

John: Thanks! I really appreciate that.
```

### 3. Create `conversation_to_mp3.py`

```python
import asyncio
import re
import edge_tts


# =========================
# Configuration
# =========================

INPUT_FILE = "conversation.txt"
OUTPUT_FILE = "conversation.mp3"

# Different voices for each speaker
VOICES = {
    "Ahmed": "en-US-GuyNeural",
    "John": "en-US-ChristopherNeural",
}

# Speaking speed
# Examples:
# "-20%" = slower
# "0%"   = normal
# "+10%" = faster
RATE = "-10%"

# Volume
VOLUME = "+0%"


# =========================
# Read conversation
# =========================

def read_conversation(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return file.read()


# =========================
# Parse conversation
# =========================

def parse_conversation(text):
    lines = []

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        match = re.match(r"^([^:]+):\s*(.+)$", line)

        if not match:
            print(f"Skipping invalid line: {line}")
            continue

        speaker = match.group(1).strip()
        message = match.group(2).strip()

        lines.append((speaker, message))

    return lines


# =========================
# Generate audio
# =========================

async def generate_audio(conversation):

    # We generate each speaker's sentence separately
    # and then combine the audio files.

    audio_files = []

    for index, (speaker, message) in enumerate(conversation):

        voice = VOICES.get(speaker)

        if not voice:
            print(f"Warning: No voice configured for '{speaker}'")
            print("Using default voice.")
            voice = "en-US-GuyNeural"

        filename = f"_part_{index}.mp3"

        print(f"Generating: {speaker} -> {message}")

        communicate = edge_tts.Communicate(
            message,
            voice=voice,
            rate=RATE,
            volume=VOLUME,
        )

        await communicate.save(filename)

        audio_files.append(filename)

    return audio_files


# =========================
# Combine MP3 files
# =========================

def combine_audio(files, output_file):

    try:
        from pydub import AudioSegment
    except ImportError:
        print("\nMissing pydub.")
        print("Install it with:")
        print("pip install pydub")
        return

    final_audio = AudioSegment.empty()

    # Pause between speakers
    pause = AudioSegment.silent(duration=500)

    for filename in files:
        audio = AudioSegment.from_mp3(filename)

        final_audio += audio
        final_audio += pause

    final_audio.export(
        output_file,
        format="mp3",
        bitrate="192k"
    )

    print(f"\nDone! 🎉")
    print(f"MP3 created: {output_file}")


# =========================
# Cleanup
# =========================

def cleanup(files):

    import os

    for filename in files:
        if os.path.exists(filename):
            os.remove(filename)


# =========================
# Main
# =========================

async def main():

    print("Reading conversation...")

    text = read_conversation(INPUT_FILE)

    conversation = parse_conversation(text)

    if not conversation:
        print("No valid conversation found.")
        return

    print(f"Found {len(conversation)} lines.\n")

    files = await generate_audio(conversation)

    combine_audio(files, OUTPUT_FILE)

    cleanup(files)


if __name__ == "__main__":
    asyncio.run(main())
```

### 4. Install `pydub`

```bash
pip install pydub
```

You'll also need **FFmpeg** because `pydub` uses it for MP3 processing.

On macOS:

```bash
brew install ffmpeg
```

### 5. Run it

Put these files in the same directory:

```text
english-practice/
├── conversation.txt
└── conversation_to_mp3.py
```

Then:

```bash
python conversation_to_mp3.py
```

You'll get:

```text
conversation.mp3
```

### 🎧 For your English learning

I'd actually recommend setting:

```python
RATE = "-15%"
```

initially. That makes the conversation slightly slower while still sounding natural.

Once you're comfortable, change it to:

```python
RATE = "0%"
```

for normal-speed English.

**One improvement I'd make next:** instead of requiring `Ahmed:` and `John:` to be hard-coded, we can make this a proper little CLI tool where you run:

```bash
python conversation.py my_conversation.txt --slow
```

and it automatically detects the speakers and generates the MP3.
