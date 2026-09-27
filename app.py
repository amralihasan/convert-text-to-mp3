import asyncio
import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from conversation_to_mp3 import (
    parse_conversation,
    extract_speakers,
    convert_conversation,
    FALLBACK_VOICE,
)

# Curated High-Quality Voices categorized by Gender
MALE_VOICES = [
    ("Guy (US)", "en-US-GuyNeural"),
    ("Christopher (US)", "en-US-ChristopherNeural"),
    ("Andrew (US)", "en-US-AndrewNeural"),
    ("Eric (US)", "en-US-EricNeural"),
    ("Brian (US)", "en-US-BrianNeural"),
    ("Ryan (UK)", "en-GB-RyanNeural"),
    ("Thomas (UK)", "en-GB-ThomasNeural"),
    ("William (Australia)", "en-AU-WilliamMultilingualNeural"),
    ("Liam (Canada)", "en-CA-LiamNeural"),
    ("Shakir (Arabic Egypt)", "ar-EG-ShakirNeural"),
]

FEMALE_VOICES = [
    ("Jenny (US)", "en-US-JennyNeural"),
    ("Ava (US)", "en-US-AvaNeural"),
    ("Emma (US)", "en-US-EmmaNeural"),
    ("Aria (US)", "en-US-AriaNeural"),
    ("Michelle (US)", "en-US-MichelleNeural"),
    ("Sonia (UK)", "en-GB-SoniaNeural"),
    ("Libby (UK)", "en-GB-LibbyNeural"),
    ("Maisie (UK)", "en-GB-MaisieNeural"),
    ("Natasha (Australia)", "en-AU-NatashaNeural"),
    ("Clara (Canada)", "en-CA-ClaraNeural"),
    ("Salma (Arabic Egypt)", "ar-EG-SalmaNeural"),
]

MALE_LABELS = [label for label, _ in MALE_VOICES]
FEMALE_LABELS = [label for label, _ in FEMALE_VOICES]

MALE_VOICE_MAP = {label: vid for label, vid in MALE_VOICES}
FEMALE_VOICE_MAP = {label: vid for label, vid in FEMALE_VOICES}
ALL_VOICE_MAP = {**MALE_VOICE_MAP, **FEMALE_VOICE_MAP}

FEMALE_NAMES = {
    "sarah", "sara", "mary", "anna", "emma", "jenny", "laila", "layla",
    "salma", "fatima", "nour", "mona", "amira", "jane", "lisa", "emily",
    "rachel", "maria", "clara", "sonia", "libby", "eva", "ava", "hoda",
    "nadia", "dina", "yasmin", "yasmine", "reem", "mariam", "marwa",
    "alice", "sophia", "olivia", "charlotte", "mia", "harper", "evelyn",
}


def guess_gender(speaker_name: str) -> str:
    cleaned = speaker_name.lower().strip()
    return "Female" if cleaned in FEMALE_NAMES else "Male"


SAMPLE_CONVERSATION = """Ahmed: Hey, Sarah! How are you doing today?

Sarah: Hey, Ahmed! I'm doing pretty well. How about you?

Ahmed: I'm good, thanks. What are you working on these days?

Sarah: I'm working on a new software project. It's a little difficult, but I'm enjoying it.

Ahmed: That sounds interesting. What kind of software are you building?

Sarah: It's a small project management system. I'm building the backend with Laravel.

Ahmed: Nice! How long have you been working on it?

Sarah: About two months. I'm hoping to finish the first version next month.

Ahmed: That's great. Are you working on it alone?

Sarah: Mostly, yes. But sometimes I ask a friend to help me with the frontend.

Ahmed: That's a good idea. Building a project alone can be challenging.

Sarah: Exactly. But I'm learning a lot from it.

Ahmed: That's what matters. Keep going!

Sarah: Thanks! I really appreciate that."""


class ConversationApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Configuration
        self.title("Conversation to MP3 Studio")
        self.geometry("1120 x 800")
        self.minsize(960, 680)

        # Application state
        self.is_generating = False
        self.cancel_requested = False
        self.speaker_controls = {}  # speaker_name -> dict of widgets & state
        self.last_detected_speakers = []
        self.current_player_process = None
        self.last_generated_file = None

        # Base directories
        self.default_destination = os.path.abspath(os.path.dirname(__file__))

        self._setup_ui()
        self._load_initial_text()

    def _setup_ui(self):
        # Configure grid weight
        self.grid_columnconfigure(0, weight=6, minsize=440)
        self.grid_columnconfigure(1, weight=5, minsize=440)
        self.grid_rowconfigure(1, weight=1)

        # ------------------ Top Header ------------------
        header_frame = ctk.CTkFrame(self, fg_color="transparent", height=60)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(16, 8))
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            header_frame,
            text="🎙️ Conversation to MP3 Studio",
            font=ctk.CTkFont(size=24, weight="bold"),
            anchor="w",
        )
        title_label.grid(row=0, column=0, sticky="w")

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Convert multi-speaker dialogue text into natural, multi-voice audio with Microsoft Edge TTS",
            font=ctk.CTkFont(size=13),
            text_color="gray",
            anchor="w",
        )
        subtitle_label.grid(row=1, column=0, sticky="w")

        # ------------------ Left: Script Editor ------------------
        left_frame = ctk.CTkFrame(self, corner_radius=12)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(24, 12), pady=(0, 20))
        left_frame.grid_rowconfigure(2, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        # Toolbar above editor
        editor_header = ctk.CTkFrame(left_frame, fg_color="transparent")
        editor_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        editor_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            editor_header,
            text="📝 Dialogue Script",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        btn_bar = ctk.CTkFrame(editor_header, fg_color="transparent")
        btn_bar.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(
            btn_bar,
            text="📋 Paste",
            width=70,
            height=28,
            command=self._paste_clipboard,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_bar,
            text="📂 Load File",
            width=85,
            height=28,
            command=self._load_file_dialog,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_bar,
            text="✨ Sample",
            width=75,
            height=28,
            command=self._load_sample,
            fg_color="#3B82F6",
            hover_color="#2563EB",
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_bar,
            text="🗑️ Clear",
            width=65,
            height=28,
            command=self._clear_text,
            fg_color="#EF4444",
            hover_color="#DC2626",
        ).pack(side="left", padx=4)

        # Instructions hint
        ctk.CTkLabel(
            left_frame,
            text="Format: 'SpeakerName: Text to speak' on each line. Empty lines are ignored.",
            font=ctk.CTkFont(size=11),
            text_color="#9CA3AF",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 6))

        # Big Text Area
        self.text_editor = ctk.CTkTextbox(
            left_frame,
            font=ctk.CTkFont(family="Menlo", size=13),
            wrap="word",
            corner_radius=8,
        )
        self.text_editor.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 10))
        self.text_editor.bind("<KeyRelease>", lambda e: self._on_text_changed())

        # Editor Footer (Stats & Speaker count)
        self.editor_stats_label = ctk.CTkLabel(
            left_frame,
            text="Lines: 0 | Speakers detected: 0",
            font=ctk.CTkFont(size=12),
            text_color="#A1A1AA",
            anchor="w",
        )
        self.editor_stats_label.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 14))

        # ------------------ Right: Settings & Actions ------------------
        right_scroll = ctk.CTkScrollableFrame(self, corner_radius=12)
        right_scroll.grid(row=1, column=1, sticky="nsew", padx=(12, 24), pady=(0, 20))
        right_scroll.grid_columnconfigure(0, weight=1)

        # 1. Speaker Voice Assignment Card
        voices_card = ctk.CTkFrame(right_scroll, corner_radius=10)
        voices_card.pack(fill="x", pady=(0, 14))
        voices_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            voices_card,
            text="👥 Speaker Voice & Gender",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 2))

        ctk.CTkLabel(
            voices_card,
            text="Select Male or Female for each speaker to customize their voice:",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 10))

        self.speakers_container = ctk.CTkFrame(voices_card, fg_color="transparent")
        self.speakers_container.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        self.speakers_container.grid_columnconfigure(0, weight=1)

        # 2. Audio Settings Card
        audio_card = ctk.CTkFrame(right_scroll, corner_radius=10)
        audio_card.pack(fill="x", pady=(0, 14))
        audio_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            audio_card,
            text="⚙️ Audio Customization",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 10))

        # Speed / Rate Slider
        self.rate_label = ctk.CTkLabel(audio_card, text="Speaking Speed: -10% (Recommended for practice)", anchor="w")
        self.rate_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 4))

        self.rate_slider = ctk.CTkSlider(
            audio_card,
            from_=-30,
            to=30,
            number_of_steps=12,
            command=self._on_rate_slider_changed,
        )
        self.rate_slider.set(-10)
        self.rate_slider.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 12))

        # Pause Between Speakers Slider
        self.pause_label = ctk.CTkLabel(audio_card, text="Pause Between Speakers: 500 ms", anchor="w")
        self.pause_label.grid(row=3, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 4))

        self.pause_slider = ctk.CTkSlider(
            audio_card,
            from_=100,
            to=1500,
            number_of_steps=14,
            command=self._on_pause_slider_changed,
        )
        self.pause_slider.set(500)
        self.pause_slider.grid(row=4, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 16))

        # 3. Output Destination Card
        dest_card = ctk.CTkFrame(right_scroll, corner_radius=10)
        dest_card.pack(fill="x", pady=(0, 14))
        dest_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dest_card,
            text="📁 Destination & Filename",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 8))

        # Folder row
        folder_row = ctk.CTkFrame(dest_card, fg_color="transparent")
        folder_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))
        folder_row.grid_columnconfigure(0, weight=1)

        self.folder_entry = ctk.CTkEntry(
            folder_row,
            placeholder_text="Select destination folder...",
            height=34,
        )
        self.folder_entry.insert(0, self.default_destination)
        self.folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            folder_row,
            text="Browse...",
            width=90,
            height=34,
            command=self._browse_destination_folder,
        ).grid(row=0, column=1)

        # Filename row
        file_row = ctk.CTkFrame(dest_card, fg_color="transparent")
        file_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))
        file_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(file_row, text="File Name:").grid(row=0, column=0, padx=(0, 8))
        self.filename_entry = ctk.CTkEntry(
            file_row,
            placeholder_text="conversation.mp3",
            height=34,
        )
        self.filename_entry.insert(0, "conversation.mp3")
        self.filename_entry.grid(row=0, column=1, sticky="ew")

        # 4. Generate Action & Progress Card
        action_card = ctk.CTkFrame(right_scroll, corner_radius=10)
        action_card.pack(fill="x", pady=(0, 8))
        action_card.grid_columnconfigure(0, weight=1)

        self.generate_btn = ctk.CTkButton(
            action_card,
            text="🚀 Generate MP3",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=46,
            fg_color="#10B981",
            hover_color="#059669",
            command=self._start_generation,
        )
        self.generate_btn.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))

        self.cancel_btn = ctk.CTkButton(
            action_card,
            text="Cancel Generation",
            font=ctk.CTkFont(size=13),
            height=32,
            fg_color="#EF4444",
            hover_color="#DC2626",
            command=self._cancel_generation,
        )

        self.progress_bar = ctk.CTkProgressBar(action_card, height=12)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        self.status_label = ctk.CTkLabel(
            action_card,
            text="Ready to generate audio",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF",
        )
        self.status_label.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 14))

        # Result actions (Open in Finder / Play Audio)
        self.result_frame = ctk.CTkFrame(action_card, fg_color="transparent")
        self.result_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 14))
        self.result_frame.grid_columnconfigure(0, weight=1)
        self.result_frame.grid_columnconfigure(1, weight=1)

        self.play_btn = ctk.CTkButton(
            self.result_frame,
            text="▶️ Play Audio",
            height=36,
            fg_color="#4F46E5",
            hover_color="#4338CA",
            command=self._toggle_playback,
        )
        self.play_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.open_finder_btn = ctk.CTkButton(
            self.result_frame,
            text="📂 Open in Finder",
            height=36,
            command=self._open_in_finder,
        )
        self.open_finder_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.result_frame.grid_remove()  # Hide until MP3 is generated

    # ------------------ Text Editor Handlers ------------------
    def _load_initial_text(self):
        conv_path = os.path.join(self.default_destination, "conversation.txt")
        if os.path.exists(conv_path):
            with open(conv_path, "r", encoding="utf-8") as f:
                self.text_editor.insert("1.0", f.read())
        else:
            self.text_editor.insert("1.0", SAMPLE_CONVERSATION)

        self._on_text_changed()

    def _load_sample(self):
        self.text_editor.delete("1.0", "end")
        self.text_editor.insert("1.0", SAMPLE_CONVERSATION)
        self._on_text_changed()

    def _clear_text(self):
        self.text_editor.delete("1.0", "end")
        self._on_text_changed()

    def _paste_clipboard(self):
        try:
            clipboard_content = self.clipboard_get()
            self.text_editor.insert("insert", clipboard_content)
            self._on_text_changed()
        except tk.TclError:
            pass

    def _load_file_dialog(self):
        file_path = filedialog.askopenfilename(
            title="Open Conversation Text File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialdir=self.folder_entry.get().strip() or self.default_destination,
        )
        if file_path:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                self.text_editor.delete("1.0", "end")
                self.text_editor.insert("1.0", f.read())
            self._on_text_changed()

    def _on_text_changed(self):
        raw_text = self.text_editor.get("1.0", "end-1c")
        conversation = parse_conversation(raw_text)
        speakers = extract_speakers(conversation)

        # Update stats
        self.editor_stats_label.configure(
            text=f"Dialogue lines: {len(conversation)} | Speakers detected: {len(speakers)} ({', '.join(speakers) if speakers else 'None'})"
        )

        # Rebuild speaker voice selector if speaker list changed
        if speakers != self.last_detected_speakers:
            self.last_detected_speakers = speakers
            self._rebuild_speaker_selectors(speakers)

    # ------------------ Speaker Voice & Gender Management ------------------
    def _rebuild_speaker_selectors(self, speakers):
        # Preserve existing speaker choices if already configured
        old_controls = dict(self.speaker_controls)

        # Clear existing rows
        for widget in self.speakers_container.winfo_children():
            widget.destroy()

        self.speaker_controls = {}

        if not speakers:
            empty_lbl = ctk.CTkLabel(
                self.speakers_container,
                text="No speakers detected yet. Format lines as 'Speaker: Dialogue'.",
                font=ctk.CTkFont(size=12, slant="italic"),
                text_color="#71717A",
            )
            empty_lbl.grid(row=0, column=0, sticky="w", pady=6)
            return

        for i, speaker in enumerate(speakers):
            prev = old_controls.get(speaker, {})
            prev_gender = prev.get("gender")
            prev_voice = prev.get("voice_label")

            # Initial gender determination
            gender = prev_gender if prev_gender else guess_gender(speaker)
            gender_val = "👨 Male" if gender == "Male" else "👩 Female"

            # Speaker Card container
            card = ctk.CTkFrame(
                self.speakers_container,
                corner_radius=10,
                fg_color=("#F3F4F6", "#1E293B"),
            )
            card.pack(fill="x", pady=6)

            # Top Row: Speaker Name & Gender Toggle
            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=12, pady=(10, 6))
            top_row.grid_columnconfigure(0, weight=1)

            name_lbl = ctk.CTkLabel(
                top_row,
                text=f"👤 {speaker}",
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w",
            )
            name_lbl.grid(row=0, column=0, sticky="w")

            gender_seg = ctk.CTkSegmentedButton(
                top_row,
                values=["👨 Male", "👩 Female"],
                font=ctk.CTkFont(size=12, weight="bold"),
                width=170,
                height=30,
                selected_color="#2563EB",
                selected_hover_color="#1D4ED8",
                command=lambda val, s=speaker: self._on_gender_changed(s, val),
            )
            gender_seg.set(gender_val)
            gender_seg.grid(row=0, column=1, sticky="e")

            # Bottom Row: Voice Label, Dropdown & Test Button
            bottom_row = ctk.CTkFrame(card, fg_color="transparent")
            bottom_row.pack(fill="x", padx=12, pady=(0, 10))
            bottom_row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                bottom_row,
                text="Voice:",
                font=ctk.CTkFont(size=12),
                text_color="#94A3B8",
            ).grid(row=0, column=0, padx=(0, 6), sticky="w")

            # Available voice options based on gender
            voice_options = MALE_LABELS if gender == "Male" else FEMALE_LABELS

            if prev_voice and prev_voice in voice_options:
                default_voice = prev_voice
            else:
                # Default voice assignments
                if gender == "Male":
                    if speaker.lower() in ("ahmed", "guy"):
                        default_voice = "Guy (US)"
                    elif speaker.lower() in ("john", "chris", "christopher"):
                        default_voice = "Christopher (US)"
                    else:
                        default_voice = MALE_LABELS[i % len(MALE_LABELS)]
                else:
                    if speaker.lower() in ("sarah", "sara", "jenny"):
                        default_voice = "Jenny (US)"
                    elif speaker.lower() in ("emma",):
                        default_voice = "Emma (US)"
                    else:
                        default_voice = FEMALE_LABELS[i % len(FEMALE_LABELS)]

            voice_menu = ctk.CTkOptionMenu(
                bottom_row,
                values=voice_options,
                height=30,
                dynamic_resizing=False,
            )
            voice_menu.set(default_voice)
            voice_menu.grid(row=0, column=1, sticky="ew", padx=(0, 8))

            test_btn = ctk.CTkButton(
                bottom_row,
                text="🔊 Test",
                width=65,
                height=30,
                fg_color="#334155",
                hover_color="#475569",
                command=lambda s=speaker, vm=voice_menu: self._audition_voice(s, vm),
            )
            test_btn.grid(row=0, column=2, sticky="e")

            self.speaker_controls[speaker] = {
                "card": card,
                "gender_seg": gender_seg,
                "voice_menu": voice_menu,
                "gender": gender,
                "voice_label": default_voice,
            }

    def _on_gender_changed(self, speaker, selected_val):
        controls = self.speaker_controls.get(speaker)
        if not controls:
            return

        is_male = "Male" in selected_val
        gender = "Male" if is_male else "Female"
        controls["gender"] = gender

        voice_options = MALE_LABELS if is_male else FEMALE_LABELS
        voice_menu = controls["voice_menu"]

        idx = 0
        if speaker in self.last_detected_speakers:
            idx = self.last_detected_speakers.index(speaker)

        if is_male:
            new_voice = MALE_LABELS[idx % len(MALE_LABELS)]
        else:
            new_voice = FEMALE_LABELS[idx % len(FEMALE_LABELS)]

        voice_menu.configure(values=voice_options)
        voice_menu.set(new_voice)
        controls["voice_label"] = new_voice

        self.status_label.configure(
            text=f"Set {speaker} to {gender} ({new_voice})",
            text_color="#60A5FA",
        )

    def _audition_voice(self, speaker, voice_menu):
        voice_label = voice_menu.get()
        voice_id = ALL_VOICE_MAP.get(voice_label, FALLBACK_VOICE)

        controls = self.speaker_controls.get(speaker, {})
        gender = controls.get("gender", "Male")
        title_gender = "male" if gender == "Male" else "female"

        self.status_label.configure(
            text=f"Auditioning {voice_label} ({title_gender} voice for {speaker})...",
            text_color="#60A5FA",
        )

        def _test_speech():
            import edge_tts
            import tempfile

            test_text = f"Hello! I am {speaker}. This is my voice."
            temp_file = tempfile.mktemp(suffix=".mp3")
            try:
                communicate = edge_tts.Communicate(test_text, voice=voice_id, rate="-5%")
                asyncio.run(communicate.save(temp_file))
                subprocess.run(["afplay", temp_file])
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Audio Test Error", str(e)))
            finally:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text="Ready to generate audio", text_color="#9CA3AF"
                    ),
                )

        threading.Thread(target=_test_speech, daemon=True).start()

    # ------------------ Settings Slider Callbacks ------------------
    def _on_rate_slider_changed(self, value):
        val = int(value)
        sign = "+" if val > 0 else ""
        label_extra = " (Recommended for practice)" if val == -10 else ""
        self.rate_label.configure(text=f"Speaking Speed: {sign}{val}%{label_extra}")

    def _on_pause_slider_changed(self, value):
        val = int(value)
        self.pause_label.configure(text=f"Pause Between Speakers: {val} ms")

    # ------------------ Destination Picker ------------------
    def _browse_destination_folder(self):
        chosen = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=self.folder_entry.get().strip() or self.default_destination,
        )
        if chosen:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, chosen)

    # ------------------ Generation Workflow ------------------
    def _start_generation(self):
        if self.is_generating:
            return

        text = self.text_editor.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Empty Script", "Please enter or paste conversation dialogue first.")
            return

        folder = self.folder_entry.get().strip()
        if not folder:
            messagebox.showwarning("Missing Destination", "Please choose an output folder.")
            return

        filename = self.filename_entry.get().strip()
        if not filename:
            filename = "conversation.mp3"
        if not filename.lower().endswith(".mp3"):
            filename += ".mp3"

        full_output_path = os.path.join(folder, filename)

        # Build voice map
        voice_map = {}
        for speaker, controls in self.speaker_controls.items():
            label = controls["voice_menu"].get()
            voice_map[speaker] = ALL_VOICE_MAP.get(label, FALLBACK_VOICE)

        # Rate and pause
        rate_val = int(self.rate_slider.get())
        rate_str = f"{'+' if rate_val > 0 else ''}{rate_val}%"
        pause_ms = int(self.pause_slider.get())

        # Set UI to running state
        self.is_generating = True
        self.cancel_requested = False
        self.generate_btn.configure(state="disabled", text="⏳ Generating Audio...")
        self.cancel_btn.grid(row=0, column=1, padx=(6, 16), pady=(16, 10))
        self.progress_bar.set(0)
        self.status_label.configure(text="Initializing generation...", text_color="#60A5FA")
        self.result_frame.grid_remove()

        # Stop any ongoing playback
        self._stop_playback()

        # Run background thread
        thread = threading.Thread(
            target=self._run_generation_thread,
            args=(text, voice_map, full_output_path, rate_str, pause_ms),
            daemon=True,
        )
        thread.start()

    def _cancel_generation(self):
        if self.is_generating:
            self.cancel_requested = True
            self.status_label.configure(text="Cancelling generation...", text_color="#EF4444")

    def _run_generation_thread(self, text, voice_map, output_file, rate_str, pause_ms):
        def progress_callback(status_msg, progress_fraction):
            self.after(
                0,
                lambda: self._update_progress_ui(status_msg, progress_fraction),
            )

        def is_cancelled():
            return self.cancel_requested

        error_message = None
        result = None

        try:
            result = asyncio.run(
                convert_conversation(
                    text=text,
                    voice_map=voice_map,
                    output_file=output_file,
                    rate=rate_str,
                    pause_ms=pause_ms,
                    progress_callback=progress_callback,
                    is_cancelled=is_cancelled,
                )
            )
        except Exception as e:
            error_message = str(e)

        self.after(
            0,
            lambda: self._finish_generation_ui(result, error_message, output_file),
        )

    def _update_progress_ui(self, status_msg, progress_fraction):
        self.progress_bar.set(progress_fraction)
        self.status_label.configure(text=status_msg)

    def _finish_generation_ui(self, result, error_message, output_file):
        self.is_generating = False
        self.generate_btn.configure(state="normal", text="🚀 Generate MP3")
        self.cancel_btn.grid_remove()

        if error_message:
            self.progress_bar.set(0)
            if "cancelled" in error_message.lower():
                self.status_label.configure(text="Generation was cancelled.", text_color="#F59E0B")
            else:
                self.status_label.configure(text=f"Error: {error_message}", text_color="#EF4444")
                messagebox.showerror("Generation Failed", error_message)
        else:
            self.last_generated_file = output_file
            self.progress_bar.set(1.0)
            dur = result["duration_sec"]
            size_kb = result["file_size_bytes"] / 1024
            self.status_label.configure(
                text=f"🎉 Successfully created {os.path.basename(output_file)} ({dur:.1f}s, {size_kb:.1f} KB)",
                text_color="#10B981",
            )
            self.result_frame.grid()

    # ------------------ Post-Generation Actions ------------------
    def _open_in_finder(self):
        if self.last_generated_file and os.path.exists(self.last_generated_file):
            subprocess.run(["open", "-R", self.last_generated_file])
        else:
            folder = self.folder_entry.get().strip()
            if os.path.exists(folder):
                subprocess.run(["open", folder])

    def _toggle_playback(self):
        if self.current_player_process and self.current_player_process.poll() is None:
            self._stop_playback()
        else:
            self._start_playback()

    def _start_playback(self):
        if not self.last_generated_file or not os.path.exists(self.last_generated_file):
            return

        self._stop_playback()
        self.play_btn.configure(text="⏹️ Stop", fg_color="#DC2626", hover_color="#B91C1C")

        def _play():
            self.current_player_process = subprocess.Popen(["afplay", self.last_generated_file])
            self.current_player_process.wait()
            self.after(
                0,
                lambda: self.play_btn.configure(
                    text="▶️ Play Audio", fg_color="#4F46E5", hover_color="#4338CA"
                ),
            )

        threading.Thread(target=_play, daemon=True).start()

    def _stop_playback(self):
        if self.current_player_process and self.current_player_process.poll() is None:
            self.current_player_process.terminate()
            self.current_player_process = None
        self.play_btn.configure(text="▶️ Play Audio", fg_color="#4F46E5", hover_color="#4338CA")


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = ConversationApp()
    app.mainloop()


if __name__ == "__main__":
    main()
