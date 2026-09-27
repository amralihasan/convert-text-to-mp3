# 🎙️ Conversation to MP3 Studio

A desktop application and CLI tool that converts conversational dialogue scripts into natural-sounding multi-speaker MP3 audio using **Microsoft Edge TTS** and **pydub**. Includes atmospheric **Background Soundscapes** and an automatic **History Library** that saves and organizes your past conversation scripts and generated audio recordings for anytime playback.

---

## ✨ Features

- **Modern Desktop UI with Tabs**:
  - **🎙️ Studio Tab**: Interactive conversation editor, dynamic speaker recognition, gender/voice selectors, scene background ambience, and audio generator.
  - **📜 History Library Tab**: Persistent archive of every generated conversation with an embedded audio player and management tools.
- **☕ Scene Background Ambience (Soundscapes)**:
  - Add realistic environment sounds behind your dialogue to set the scene:
    - ☕ **Coffee shop**: Café ambience (chatter, cups, cafe murmurs)
    - 🏢 **Office**: Office ambience (typing, air, subtle murmur)
    - 🚗 **Car**: Road & car driving ambience (engine drone, highway road noise)
    - 🏠 **Home**: Quiet room (natural room tone)
    - 🛒 **Shopping**: Store & mall ambience (spacious reverberation, cart motion)
    - 🌳 **Outside**: Park & outdoor nature ambience (birds singing, gentle breeze)
    - 🚫 **None**: Pure clean speech
    - 📁 **Custom Audio File**: Use any `.mp3`, `.wav`, or `.m4a` file on your computer.
  - **🔊 Audition Ambience**: Preview a 5-second sample of any background track before generating.
  - **Ambience Volume Slider**: Seamlessly control background level (5% to 45%, default 15% for subtle backing).
- **Persistent History & Playback**:
  - Automatically saves conversation text, generated MP3 audio, and background settings into local history archives.
  - **Embedded Player**: Play, stop, or re-listen to any past recording directly inside the app.
  - **📝 Load to Studio**: Reload any past conversation script and its ambience back into the Studio editor with one click.
  - **🔍 Search & Filter**: Search your history by title, speaker names, ambience, or creation date.
  - **📂 Reveal in Finder**: Instantly reveal any saved audio recording in macOS Finder.
- **👨 Male / 👩 Female Gender Selector**:
  - Easily toggle each speaker between Male and Female using an interactive segmented button.
  - Automatically filters and populates the voice list with top-quality neural voices tailored to that gender.
- **High-Quality Neural Voices**:
  - **Male Voices**: Guy (US), Christopher (US), Andrew (US), Eric (US), Brian (US), Ryan (UK), Thomas (UK), William (AU), Liam (CA), Shakir (Arabic EG).
  - **Female Voices**: Jenny (US), Ava (US), Emma (US), Aria (US), Michelle (US), Sonia (UK), Libby (UK), Maisie (UK), Natasha (AU), Clara (CA), Salma (Arabic EG).
- **🔊 Voice Audition**: Click "Test" next to any speaker to audition their voice before generating.
- **Speed & Pause Control**: Adjust speaking rate (-30% to +30%) and silence pause duration between speakers.
- **Destination Folder Picker**: Select any folder on your Mac and specify the output filename.
- **Background Generation**: Threaded execution ensures the GUI never freezes. Includes smooth progress bar and line-by-line status.
- **CLI Mode**: Run headlessly from the terminal whenever needed.

---

## 🚀 Quick Start (Desktop UI)

### Launch with one command:
```bash
./run.sh
```

Or run via the virtual environment:
```bash
.venv/bin/python app.py
```

---

## 🛠️ CLI Usage

You can also convert text files directly from your terminal:

```bash
# Using default conversation.txt and conversation.mp3:
.venv/bin/python conversation_to_mp3.py

# Or specify custom input and output paths:
.venv/bin/python conversation_to_mp3.py my_dialogue.txt /Users/username/Desktop/output.mp3
```

---

## 📋 Dialogue Format

Lines should follow the `Speaker: Message` format:

```text
Ahmed: Hey, Sarah! How are you doing today?

Sarah: Hey, Ahmed! I'm doing pretty well. How about you?

Ahmed: I'm good, thanks. What are you working on these days?
```
*(Empty lines and extra spacing are handled automatically)*
