# 🎙️ Conversation to MP3 Studio

A desktop application and CLI tool that converts conversational dialogue scripts into natural-sounding multi-speaker MP3 audio using **Microsoft Edge TTS** and **pydub**.

---

## ✨ Features

- **Modern Desktop UI**: Built with `CustomTkinter` featuring dark mode macOS styling.
- **Dynamic Speaker Recognition**: Automatically detects speakers (e.g., `Ahmed`, `Sarah`, `John`) from your pasted or typed text.
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
- **Post-Generation Actions**: Listen to generated audio directly with one click or open the file in macOS Finder.
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
