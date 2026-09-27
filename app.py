import asyncio
import math
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
    sanitize_directory_name,
    FALLBACK_VOICE,
)
from history_manager import HistoryManager

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

# Ambient Soundscape Presets
BACKGROUND_PRESETS = [
    ("🚫 None (Pure speech)", None),
    ("☕ Coffee shop (Café ambience)", "backgrounds/coffee_shop.mp3"),
    ("🏢 Office (Office ambience)", "backgrounds/office.mp3"),
    ("🚗 Car (Road/car ambience)", "backgrounds/car.mp3"),
    ("🏠 Home (Quiet room)", "backgrounds/home.mp3"),
    ("🛒 Shopping (Store ambience)", "backgrounds/shopping.mp3"),
    ("🌳 Outside (Park/outdoor ambience)", "backgrounds/outside.mp3"),
    ("📁 Custom audio file...", "CUSTOM"),
]

BG_LABEL_TO_PATH = {label: path for label, path in BACKGROUND_PRESETS}
BG_LABELS = [label for label, _ in BACKGROUND_PRESETS]


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
        self.geometry("1160 x 860")
        self.minsize(980, 720)

        # Base directory
        self.base_dir = os.path.abspath(os.path.dirname(__file__))

        # Persistence & History
        self.history_mgr = HistoryManager(self.base_dir)

        # Application state
        self.is_generating = False
        self.cancel_requested = False
        self.speaker_controls = {}  # speaker_name -> dict of widgets & state
        self.last_detected_speakers = []
        self.current_player_process = None
        self.playing_file_path = None
        self.last_generated_dir = None
        self.last_generated_full_file = None
        self.history_play_buttons = {}  # file_path -> button widget

        # Custom background audio path if chosen
        self.custom_bg_path = None
        self.bg_preview_process = None

        self._setup_ui()
        self._load_initial_text()
        self._refresh_history_tab()

    def _setup_ui(self):
        # Master container grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ------------------ Top Header ------------------
        header_frame = ctk.CTkFrame(self, fg_color="transparent", height=50)
        header_frame.grid(row=0, column=0, sticky="ew", padx=24, pady=(14, 4))
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            header_frame,
            text="🎙️ Conversation to MP3 Studio",
            font=ctk.CTkFont(size=23, weight="bold"),
            anchor="w",
        )
        title_label.grid(row=0, column=0, sticky="w")

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Export full dialogues to a single MP3 or a complete project directory with individual sentence clips",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w",
        )
        subtitle_label.grid(row=1, column=0, sticky="w")

        # ------------------ Main Tabview ------------------
        self.tabview = ctk.CTkTabview(self, corner_radius=12)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 16))

        # Add tabs
        self.tab_studio = self.tabview.add("🎙️ Studio")
        self.tab_history = self.tabview.add("📜 History (0)")

        self._setup_studio_tab()
        self._setup_history_tab()

    def _setup_studio_tab(self):
        tab = self.tab_studio
        tab.grid_columnconfigure(0, weight=6, minsize=440)
        tab.grid_columnconfigure(1, weight=5, minsize=440)
        tab.grid_rowconfigure(0, weight=1)

        # ------------------ Left: Script Editor ------------------
        left_frame = ctk.CTkFrame(tab, corner_radius=10)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(6, 8), pady=8)
        left_frame.grid_rowconfigure(2, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        # Toolbar above editor
        editor_header = ctk.CTkFrame(left_frame, fg_color="transparent")
        editor_header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        editor_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            editor_header,
            text="📝 Dialogue Script",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        btn_bar = ctk.CTkFrame(editor_header, fg_color="transparent")
        btn_bar.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(
            btn_bar,
            text="📋 Paste",
            width=68,
            height=28,
            command=self._paste_clipboard,
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btn_bar,
            text="📂 Load File",
            width=80,
            height=28,
            command=self._load_file_dialog,
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btn_bar,
            text="✨ Sample",
            width=70,
            height=28,
            command=self._load_sample,
            fg_color="#3B82F6",
            hover_color="#2563EB",
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btn_bar,
            text="🗑️ Clear",
            width=60,
            height=28,
            command=self._clear_text,
            fg_color="#EF4444",
            hover_color="#DC2626",
        ).pack(side="left", padx=3)

        # Hint
        ctk.CTkLabel(
            left_frame,
            text="Format: 'Speaker: Message' on each line. Empty lines are ignored.",
            font=ctk.CTkFont(size=11),
            text_color="#9CA3AF",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 6))

        # Big Text Area
        self.text_editor = ctk.CTkTextbox(
            left_frame,
            font=ctk.CTkFont(family="Menlo", size=13),
            wrap="word",
            corner_radius=8,
        )
        self.text_editor.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 10))
        self.text_editor.bind("<KeyRelease>", lambda e: self._on_text_changed())

        # Editor Footer (Stats & Speaker count)
        self.editor_stats_label = ctk.CTkLabel(
            left_frame,
            text="Lines: 0 | Speakers detected: 0",
            font=ctk.CTkFont(size=12),
            text_color="#A1A1AA",
            anchor="w",
        )
        self.editor_stats_label.grid(row=3, column=0, sticky="w", padx=14, pady=(0, 12))

        # ------------------ Right: Settings & Actions ------------------
        right_scroll = ctk.CTkScrollableFrame(tab, corner_radius=10)
        right_scroll.grid(row=0, column=1, sticky="nsew", padx=(8, 6), pady=8)
        right_scroll.grid_columnconfigure(0, weight=1)

        # 1. Speaker Voice & Gender Card
        voices_card = ctk.CTkFrame(right_scroll, corner_radius=10)
        voices_card.pack(fill="x", pady=(0, 12))
        voices_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            voices_card,
            text="👥 Speaker Voice & Gender",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 2))

        ctk.CTkLabel(
            voices_card,
            text="Choose Male or Female for each speaker to customize their voice:",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 8))

        self.speakers_container = ctk.CTkFrame(voices_card, fg_color="transparent")
        self.speakers_container.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 12))
        self.speakers_container.grid_columnconfigure(0, weight=1)

        # 2. Ambient Background Card
        bg_card = ctk.CTkFrame(right_scroll, corner_radius=10)
        bg_card.pack(fill="x", pady=(0, 12))
        bg_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            bg_card,
            text="☕ Scene Background Ambience",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 2))

        ctk.CTkLabel(
            bg_card,
            text="Add realistic environment sound behind the dialogue (Café, Car, Office, Park):",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF",
            anchor="w",
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 8))

        # Ambience Selector Row
        bg_row = ctk.CTkFrame(bg_card, fg_color="transparent")
        bg_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8))
        bg_row.grid_columnconfigure(0, weight=1)

        self.bg_menu = ctk.CTkOptionMenu(
            bg_row,
            values=BG_LABELS,
            height=34,
            command=self._on_bg_preset_selected,
        )
        self.bg_menu.set("☕ Coffee shop (Café ambience)")
        self.bg_menu.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.bg_preview_btn = ctk.CTkButton(
            bg_row,
            text="🔊 Audition",
            width=90,
            height=34,
            fg_color="#334155",
            hover_color="#475569",
            command=self._toggle_bg_preview,
        )
        self.bg_preview_btn.grid(row=0, column=1)

        # Ambience Volume Slider
        self.bg_volume_label = ctk.CTkLabel(
            bg_card,
            text="Ambience Volume: 15% (Subtle background - Recommended)",
            anchor="w",
        )
        self.bg_volume_label.grid(row=3, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 2))

        self.bg_volume_slider = ctk.CTkSlider(
            bg_card,
            from_=5,
            to=45,
            number_of_steps=40,
            command=self._on_bg_volume_slider_changed,
        )
        self.bg_volume_slider.set(15)
        self.bg_volume_slider.grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 14))

        # 3. Audio Customization Card (Speed & Pause)
        audio_card = ctk.CTkFrame(right_scroll, corner_radius=10)
        audio_card.pack(fill="x", pady=(0, 12))
        audio_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            audio_card,
            text="⚙️ Speech Pace & Pauses",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 8))

        # Speed / Rate Slider
        self.rate_label = ctk.CTkLabel(audio_card, text="Speaking Speed: -10% (Recommended for practice)", anchor="w")
        self.rate_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 2))

        self.rate_slider = ctk.CTkSlider(
            audio_card,
            from_=-30,
            to=30,
            number_of_steps=12,
            command=self._on_rate_slider_changed,
        )
        self.rate_slider.set(-10)
        self.rate_slider.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))

        # Pause Between Speakers Slider
        self.pause_label = ctk.CTkLabel(audio_card, text="Pause Between Speakers: 500 ms", anchor="w")
        self.pause_label.grid(row=3, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 2))

        self.pause_slider = ctk.CTkSlider(
            audio_card,
            from_=100,
            to=1500,
            number_of_steps=14,
            command=self._on_pause_slider_changed,
        )
        self.pause_slider.set(500)
        self.pause_slider.grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 14))

        # 4. Output Destination Card (Switch: Single MP3 File vs Full Project Directory)
        dest_card = ctk.CTkFrame(right_scroll, corner_radius=10)
        dest_card.pack(fill="x", pady=(0, 12))
        dest_card.grid_columnconfigure(0, weight=1)

        self.dest_card_title = ctk.CTkLabel(
            dest_card,
            text="📁 Export Mode & Destination",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        )
        self.dest_card_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 2))

        self.dest_card_desc = ctk.CTkLabel(
            dest_card,
            text="Creates a dedicated folder containing the full dialogue MP3, transcript text file, and sentences folder:",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF",
            anchor="w",
        )
        self.dest_card_desc.grid(row=1, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 8))

        # Mode Selector (Segmented Button: Single MP3 vs Full Project Directory)
        mode_row = ctk.CTkFrame(dest_card, fg_color="transparent")
        mode_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))
        mode_row.grid_columnconfigure(0, weight=1)

        self.export_mode_seg = ctk.CTkSegmentedButton(
            mode_row,
            values=["🎵 Single MP3 File", "📁 Full Project Directory"],
            font=ctk.CTkFont(size=13, weight="bold"),
            height=34,
            selected_color="#4F46E5",
            selected_hover_color="#4338CA",
            command=self._on_export_mode_changed,
        )
        self.export_mode_seg.set("📁 Full Project Directory")
        self.export_mode_seg.grid(row=0, column=0, sticky="ew")

        # Name Row (Dynamic: File Name vs Conversation Name)
        self.name_row = ctk.CTkFrame(dest_card, fg_color="transparent")
        self.name_row.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8))
        self.name_row.grid_columnconfigure(1, weight=1)

        self.target_name_label = ctk.CTkLabel(self.name_row, text="🏷️ Conversation Name:")
        self.target_name_label.grid(row=0, column=0, padx=(0, 8), sticky="w")

        self.target_name_entry = ctk.CTkEntry(
            self.name_row,
            placeholder_text="e.g. Software_Project_Chat",
            height=34,
        )
        self.target_name_entry.insert(0, "Software_Project_Chat")
        self.target_name_entry.grid(row=0, column=1, sticky="ew")
        self.target_name_entry.bind("<KeyRelease>", lambda e: self._update_path_preview())

        # Backwards compatibility alias
        self.conv_name_entry = self.target_name_entry

        # Base Destination Folder Row
        folder_row = ctk.CTkFrame(dest_card, fg_color="transparent")
        folder_row.grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8))
        folder_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(folder_row, text="📁 Destination Folder:").grid(row=0, column=0, padx=(0, 8), sticky="w")
        self.folder_entry = ctk.CTkEntry(
            folder_row,
            placeholder_text="Select destination folder...",
            height=34,
        )
        self.folder_entry.insert(0, self.base_dir)
        self.folder_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.folder_entry.bind("<KeyRelease>", lambda e: self._update_path_preview())

        ctk.CTkButton(
            folder_row,
            text="Browse...",
            width=85,
            height=34,
            command=self._browse_destination_folder,
        ).grid(row=0, column=2)

        # Output preview label
        self.path_preview_label = ctk.CTkLabel(
            dest_card,
            text="",
            font=ctk.CTkFont(family="Menlo", size=11),
            text_color="#38BDF8",
            justify="left",
            anchor="w",
        )
        self.path_preview_label.grid(row=5, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 12))
        self._update_path_preview()

        # 5. Generate Action & Progress Card
        action_card = ctk.CTkFrame(right_scroll, corner_radius=10)
        action_card.pack(fill="x", pady=(0, 6))
        action_card.grid_columnconfigure(0, weight=1)

        self.generate_btn = ctk.CTkButton(
            action_card,
            text="🚀 Generate Project Directory",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=46,
            fg_color="#10B981",
            hover_color="#059669",
            command=self._start_generation,
        )
        self.generate_btn.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))

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
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))

        self.status_label = ctk.CTkLabel(
            action_card,
            text="Ready to generate audio",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF",
        )
        self.status_label.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 12))

        # Result actions (Open Folder / Play Full Audio / View in History)
        self.result_frame = ctk.CTkFrame(action_card, fg_color="transparent")
        self.result_frame.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 14))
        self.result_frame.grid_columnconfigure(0, weight=1)
        self.result_frame.grid_columnconfigure(1, weight=1)
        self.result_frame.grid_columnconfigure(2, weight=1)

        self.play_btn = ctk.CTkButton(
            self.result_frame,
            text="▶️ Play Audio",
            height=36,
            fg_color="#4F46E5",
            hover_color="#4338CA",
            command=self._toggle_playback,
        )
        self.play_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.open_finder_btn = ctk.CTkButton(
            self.result_frame,
            text="📂 Open Folder",
            height=36,
            command=self._open_in_finder,
        )
        self.open_finder_btn.grid(row=0, column=1, sticky="ew", padx=4)

        self.view_history_btn = ctk.CTkButton(
            self.result_frame,
            text="📜 In History",
            height=36,
            fg_color="#0D9488",
            hover_color="#0F766E",
            command=lambda: self.tabview.set(self._get_history_tab_name()),
        )
        self.view_history_btn.grid(row=0, column=2, sticky="ew", padx=(4, 0))

        self.result_frame.grid_remove()  # Hide until generated

    def _on_export_mode_changed(self, mode_val):
        is_single = "Single" in mode_val
        current_val = self.target_name_entry.get().strip()

        if is_single:
            self.dest_card_title.configure(text="🎵 Output MP3 Audio File")
            self.dest_card_desc.configure(
                text="Generates a single MP3 audio file containing the entire dialogue merged with background sound:"
            )
            self.target_name_label.configure(text="🎵 MP3 File Name:")
            self.target_name_entry.configure(placeholder_text="e.g. conversation.mp3")
            if not current_val.endswith(".mp3"):
                sanitized = sanitize_directory_name(current_val) if current_val else "conversation"
                self.target_name_entry.delete(0, "end")
                self.target_name_entry.insert(0, f"{sanitized}.mp3")
            self.generate_btn.configure(text="🚀 Generate Single MP3 File")
        else:
            self.dest_card_title.configure(text="📁 Output Project Directory")
            self.dest_card_desc.configure(
                text="Creates a dedicated folder containing the full dialogue MP3, transcript text file, and sentences folder:"
            )
            self.target_name_label.configure(text="🏷️ Conversation Name:")
            self.target_name_entry.configure(placeholder_text="e.g. Software_Project_Chat")
            if current_val.endswith(".mp3"):
                clean_name = sanitize_directory_name(current_val[:-4])
                self.target_name_entry.delete(0, "end")
                self.target_name_entry.insert(0, clean_name or "Software_Project_Chat")
            self.generate_btn.configure(text="🚀 Generate Project Directory")

        self._update_path_preview()

    def _update_path_preview(self):
        base_dir = self.folder_entry.get().strip() or self.base_dir
        is_single = hasattr(self, "export_mode_seg") and ("Single" in self.export_mode_seg.get())
        raw_name = self.target_name_entry.get().strip() if hasattr(self, "target_name_entry") else "conversation"

        if is_single:
            file_name = raw_name if raw_name else "conversation.mp3"
            if not file_name.endswith(".mp3"):
                file_name = f"{file_name}.mp3"
            full_path = os.path.join(base_dir, file_name)
            preview = f"🎵 File: {full_path}\n   └── Generates 1 consolidated MP3 file (no extra folders or sub-files)"
        else:
            conv_name = sanitize_directory_name(raw_name or "Conversation")
            full_dir = os.path.join(base_dir, conv_name)
            preview = f"📂 Folder: {full_dir}/\n   ├── full_conversation.mp3\n   ├── conversation.txt\n   └── sentences/ (separate MP3 for each line)"

        self.path_preview_label.configure(text=preview)

    # ------------------ History Tab Setup ------------------
    def _setup_history_tab(self):
        tab = self.tab_history
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # Header with Search & Refresh
        top_bar = ctk.CTkFrame(tab, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 12))
        top_bar.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            top_bar,
            placeholder_text="🔍 Search past conversations by name, speaker, ambience, or date...",
            height=36,
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_history_list())

        ctk.CTkButton(
            top_bar,
            text="🔄 Refresh",
            width=90,
            height=36,
            command=self._refresh_history_tab,
        ).grid(row=0, column=1)

        # Scrollable list of history items
        self.history_scroll = ctk.CTkScrollableFrame(tab, corner_radius=10)
        self.history_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.history_scroll.grid_columnconfigure(0, weight=1)

    def _get_history_tab_name(self):
        for name in self.tabview._name_list:
            if "History" in name:
                return name
        return "📜 History"

    def _refresh_history_tab(self):
        entries = self.history_mgr.get_all()
        count = len(entries)

        try:
            for tab_name in list(self.tabview._name_list):
                if "History" in tab_name:
                    new_tab_name = f"📜 History ({count})"
                    if tab_name != new_tab_name:
                        self.tabview._segmented_button._buttons_dict[tab_name].configure(text=new_tab_name)
                    break
        except Exception:
            pass

        self._render_history_items(entries)

    def _filter_history_list(self):
        query = self.search_entry.get().strip().lower()
        all_entries = self.history_mgr.get_all()
        if not query:
            self._render_history_items(all_entries)
            return

        filtered = []
        for e in all_entries:
            title = e.get("title", "").lower()
            conv_name = e.get("conversation_name", "").lower()
            speakers_str = " ".join([s.get("name", "") for s in e.get("speakers", [])]).lower()
            date_str = e.get("created_at", "").lower()
            bg_str = (e.get("background", {}) or {}).get("name", "").lower()

            if query in title or query in conv_name or query in speakers_str or query in date_str or query in bg_str:
                filtered.append(e)

        self._render_history_items(filtered)

    def _render_history_items(self, entries):
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

        self.history_play_buttons = {}

        if not entries:
            empty_frame = ctk.CTkFrame(self.history_scroll, fg_color="transparent")
            empty_frame.pack(fill="both", expand=True, pady=60)

            ctk.CTkLabel(
                empty_frame,
                text="📜 No Saved Conversations Yet",
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color="#9CA3AF",
            ).pack(pady=(0, 6))

            ctk.CTkLabel(
                empty_frame,
                text="When you click 'Generate Conversation & Sentences' in the Studio, both the full conversation\nand separate sentence audio files will be organized and archived here.",
                font=ctk.CTkFont(size=13),
                text_color="#6B7280",
                justify="center",
            ).pack()

            ctk.CTkButton(
                empty_frame,
                text="Go to Studio",
                width=120,
                height=34,
                command=lambda: self.tabview.set("🎙️ Studio"),
            ).pack(pady=16)
            return

        for entry in entries:
            self._create_history_card(entry)

    def _create_history_card(self, entry):
        entry_id = entry["id"]
        title = entry.get("title", "Conversation")
        conv_name = entry.get("conversation_name", "Conversation")
        conv_dir = entry.get("conversation_dir", "")
        created_at = entry.get("created_at", "")
        duration_sec = entry.get("duration_sec", 0)
        lines_count = entry.get("lines_count", 0)
        file_size_kb = entry.get("file_size_bytes", 0) / 1024
        audio_file = entry.get("audio_file", "")
        sentence_files = entry.get("sentence_files", [])
        speakers = entry.get("speakers", [])
        bg_info = entry.get("background")

        card = ctk.CTkFrame(
            self.history_scroll,
            corner_radius=10,
            fg_color=("#F9FAFB", "#1E293B"),
        )
        card.pack(fill="x", pady=6, padx=4)
        card.grid_columnconfigure(0, weight=1)

        mode = entry.get("mode", "project" if sentence_files else "single")
        is_single = (mode == "single")

        # Header Row: Folder Name / File Name, Title & Date
        hdr_row = ctk.CTkFrame(card, fg_color="transparent")
        hdr_row.pack(fill="x", padx=14, pady=(10, 4))
        hdr_row.grid_columnconfigure(0, weight=1)

        display_name = os.path.basename(entry.get("original_destination", audio_file)) if is_single else conv_name
        icon = "🎵" if is_single else "📁"
        title_lbl = ctk.CTkLabel(
            hdr_row,
            text=f"{icon} {display_name}  •  {title}",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, sticky="w")

        date_lbl = ctk.CTkLabel(
            hdr_row,
            text=f"📅 {created_at}",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8",
        )
        date_lbl.grid(row=0, column=1, sticky="e")

        # Metadata Row: Tags (Duration, Size, Lines, Speakers, Ambience)
        meta_row = ctk.CTkFrame(card, fg_color="transparent")
        meta_row.pack(fill="x", padx=14, pady=(0, 8))

        speakers_desc = []
        for s in speakers:
            s_name = s.get("name", "")
            s_gender = "♂" if s.get("gender") == "Male" else "♀"
            s_voice = s.get("voice", "").split("(")[0].strip()
            speakers_desc.append(f"{s_name} ({s_gender} {s_voice})")

        speakers_text = " • ".join(speakers_desc) if speakers_desc else "Dialogue"

        bg_text = "🚫 Pure Speech"
        if bg_info and isinstance(bg_info, dict):
            bg_name = bg_info.get("name", "").split("(")[0].strip()
            bg_vol = bg_info.get("volume", 15)
            if bg_name and "None" not in bg_name:
                bg_text = f"🎶 {bg_name} ({bg_vol}%)"

        mode_badge = "🎵 Single MP3 File" if is_single else f"🗣️ {lines_count} Sentences + Full MP3"
        meta_text = f"⏱️ {duration_sec:.1f}s   |   💾 {file_size_kb:.1f} KB   |   {mode_badge}   |   {bg_text}"
        ctk.CTkLabel(
            meta_row,
            text=meta_text,
            font=ctk.CTkFont(size=11),
            text_color="#64748B",
            anchor="w",
        ).pack(side="left")

        # Action Buttons Row
        action_row = ctk.CTkFrame(card, fg_color="transparent")
        action_row.pack(fill="x", padx=14, pady=(0, 10))

        is_playing_this = (self.playing_file_path == audio_file and self.current_player_process and self.current_player_process.poll() is None)
        play_text = "⏹️ Stop" if is_playing_this else "▶️ Play Full"
        play_color = "#DC2626" if is_playing_this else "#4F46E5"
        play_hover = "#B91C1C" if is_playing_this else "#4338CA"

        play_btn = ctk.CTkButton(
            action_row,
            text=play_text,
            width=90,
            height=28,
            fg_color=play_color,
            hover_color=play_hover,
            command=lambda aid=entry_id, apath=audio_file: self._toggle_history_playback(aid, apath),
        )
        play_btn.pack(side="left", padx=(0, 6))
        self.history_play_buttons[audio_file] = play_btn

        # Open Folder in Finder
        target_dir = conv_dir if (conv_dir and os.path.exists(conv_dir)) else os.path.dirname(audio_file)
        ctk.CTkButton(
            action_row,
            text="📂 Open Folder",
            width=100,
            height=28,
            fg_color="#334155",
            hover_color="#475569",
            command=lambda p=target_dir: subprocess.run(["open", p]),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            action_row,
            text="📝 Load to Studio",
            width=115,
            height=28,
            command=lambda eid=entry_id: self._load_history_to_studio(eid),
        ).pack(side="left", padx=4)

        # Expand Sentences Accordion / Drawer
        if sentence_files:
            sentences_toggle_btn = ctk.CTkButton(
                action_row,
                text=f"🎧 Sentences ({len(sentence_files)}) ▾",
                width=125,
                height=28,
                fg_color="#0D9488",
                hover_color="#0F766E",
            )
            sentences_toggle_btn.pack(side="left", padx=4)

            # Sub-frame for individual sentences (initially hidden)
            sentences_frame = ctk.CTkFrame(card, fg_color=("#E5E7EB", "#0F172A"), corner_radius=8)
            sentences_toggle_btn.configure(
                command=lambda sf=sentences_frame, btn=sentences_toggle_btn, n=len(sentence_files): self._toggle_sentences_drawer(sf, btn, n)
            )

            # Populate sentence rows inside sub-frame
            for s_rec in sentence_files:
                s_idx = s_rec.get("index", 1)
                s_spk = s_rec.get("speaker", "")
                s_txt = s_rec.get("text", "")
                s_path = s_rec.get("file_path", "")

                s_row = ctk.CTkFrame(sentences_frame, fg_color="transparent")
                s_row.pack(fill="x", padx=10, pady=3)
                s_row.grid_columnconfigure(1, weight=1)

                s_play_btn = ctk.CTkButton(
                    s_row,
                    text="▶️",
                    width=32,
                    height=24,
                    fg_color="#4F46E5",
                    hover_color="#4338CA",
                    command=lambda p=s_path: self._play_single_sentence(p),
                )
                s_play_btn.grid(row=0, column=0, padx=(0, 6))
                self.history_play_buttons[s_path] = s_play_btn

                s_lbl = ctk.CTkLabel(
                    s_row,
                    text=f"{s_idx:02d}. {s_spk}: {s_txt}",
                    font=ctk.CTkFont(size=12),
                    anchor="w",
                )
                s_lbl.grid(row=0, column=1, sticky="w")

        ctk.CTkButton(
            action_row,
            text="🗑️ Delete",
            width=70,
            height=28,
            fg_color="#7F1D1D",
            hover_color="#991B1B",
            command=lambda eid=entry_id: self._delete_history_item(eid),
        ).pack(side="right")

    def _toggle_sentences_drawer(self, frame, btn, count):
        if frame.winfo_ismapped():
            frame.pack_forget()
            btn.configure(text=f"🎧 Sentences ({count}) ▾")
        else:
            frame.pack(fill="x", padx=14, pady=(0, 10))
            btn.configure(text=f"🎧 Sentences ({count}) ▴")

    def _play_single_sentence(self, sentence_path):
        if not os.path.exists(sentence_path):
            messagebox.showwarning("File Missing", f"Audio file not found:\n{sentence_path}")
            return

        self._stop_playback()
        self._stop_bg_preview()
        self.playing_file_path = sentence_path

        btn = self.history_play_buttons.get(sentence_path)
        if btn:
            btn.configure(text="⏹️", fg_color="#DC2626", hover_color="#B91C1C")

        def _play():
            self.current_player_process = subprocess.Popen(["afplay", sentence_path])
            self.current_player_process.wait()
            self.after(0, self._on_playback_finished)

        threading.Thread(target=_play, daemon=True).start()

    def _toggle_history_playback(self, entry_id, audio_file):
        if self.playing_file_path == audio_file and self.current_player_process and self.current_player_process.poll() is None:
            self._stop_playback()
            return

        self._stop_playback()
        self._stop_bg_preview()

        if not os.path.exists(audio_file):
            messagebox.showwarning("File Missing", "The audio file for this recording could not be found.")
            return

        btn = self.history_play_buttons.get(audio_file)
        if btn:
            btn.configure(text="⏹️ Stop", fg_color="#DC2626", hover_color="#B91C1C")

        self.playing_file_path = audio_file

        def _play():
            self.current_player_process = subprocess.Popen(["afplay", audio_file])
            self.current_player_process.wait()
            self.after(0, self._on_playback_finished)

        threading.Thread(target=_play, daemon=True).start()

    def _on_playback_finished(self):
        self.playing_file_path = None
        self.play_btn.configure(text="▶️ Play Full Audio", fg_color="#4F46E5", hover_color="#4338CA")
        for file_path, btn in self.history_play_buttons.items():
            try:
                if btn.cget("text") in ("⏹️ Stop", "⏹️"):
                    btn.configure(
                        text="▶️" if btn.cget("width") < 50 else "▶️ Play Full",
                        fg_color="#4F46E5",
                        hover_color="#4338CA",
                    )
            except Exception:
                pass

    def _load_history_to_studio(self, entry_id):
        entry = self.history_mgr.get_entry(entry_id)
        if not entry:
            return

        text = self.history_mgr.get_text(entry_id)
        if not text:
            messagebox.showwarning("Error", "Could not load conversation text.")
            return

        self.text_editor.delete("1.0", "end")
        self.text_editor.insert("1.0", text)
        self._on_text_changed()

        # Restore export mode and target name
        mode = entry.get("mode", "project" if entry.get("sentence_files") else "single")
        is_single = (mode == "single")
        mode_str = "🎵 Single MP3 File" if is_single else "📁 Full Project Directory"
        self.export_mode_seg.set(mode_str)
        self._on_export_mode_changed(mode_str)

        self.target_name_entry.delete(0, "end")
        if is_single:
            orig = entry.get("original_destination")
            fname = os.path.basename(orig) if orig else f"{entry.get('conversation_name', 'conversation')}.mp3"
            self.target_name_entry.insert(0, fname)
        else:
            conv_name = entry.get("conversation_name") or "Software_Project_Chat"
            self.target_name_entry.insert(0, conv_name)

        self._update_path_preview()

        # Restore background ambience if available
        bg_meta = entry.get("background")
        if bg_meta and isinstance(bg_meta, dict):
            bg_name = bg_meta.get("name")
            if bg_name in BG_LABELS:
                self.bg_menu.set(bg_name)
            bg_vol = bg_meta.get("volume", 15)
            self.bg_volume_slider.set(bg_vol)
            self._on_bg_volume_slider_changed(bg_vol)

        # Switch to Studio tab
        self.tabview.set("🎙️ Studio")

    def _delete_history_item(self, entry_id):
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this recorded conversation from history?"):
            self._stop_playback()
            self.history_mgr.delete(entry_id)
            self._refresh_history_tab()

    # ------------------ Background Ambience Handlers ------------------
    def _on_bg_preset_selected(self, choice):
        self._stop_bg_preview()
        if choice == "📁 Custom audio file...":
            chosen_file = filedialog.askopenfilename(
                title="Select Custom Background Audio",
                filetypes=[
                    ("Audio Files", "*.mp3 *.wav *.m4a *.ogg *.flac *.aac"),
                    ("All Files", "*.*"),
                ],
                initialdir=self.base_dir,
            )
            if chosen_file:
                self.custom_bg_path = chosen_file
                self.status_label.configure(
                    text=f"Selected custom background: {os.path.basename(chosen_file)}",
                    text_color="#60A5FA",
                )
            else:
                self.bg_menu.set("🚫 None (Pure speech)")
                self.custom_bg_path = None
        else:
            self.custom_bg_path = None
            self.status_label.configure(
                text=f"Selected ambience: {choice.split('(')[0].strip()}",
                text_color="#60A5FA",
            )

    def _on_bg_volume_slider_changed(self, value):
        val = int(value)
        desc = "Subtle background (Recommended)" if 10 <= val <= 20 else ("Very soft" if val < 10 else "Noticeable atmosphere")
        self.bg_volume_label.configure(text=f"Ambience Volume: {val}% ({desc})")

    def _toggle_bg_preview(self):
        if self.bg_preview_process and self.bg_preview_process.poll() is None:
            self._stop_bg_preview()
        else:
            self._start_bg_preview()

    def _start_bg_preview(self):
        bg_path = self._get_selected_bg_path()
        if not bg_path or not os.path.exists(bg_path):
            messagebox.showinfo("Ambience Preview", "Please select an ambient background first (e.g. Coffee shop, Car, Office).")
            return

        self._stop_playback()
        self._stop_bg_preview()

        self.bg_preview_btn.configure(text="⏹️ Stop", fg_color="#DC2626", hover_color="#B91C1C")
        vol_pct = int(self.bg_volume_slider.get())
        self.status_label.configure(text=f"Auditioning background ambience at {vol_pct}% volume...", text_color="#60A5FA")

        def _preview():
            import tempfile
            from pydub import AudioSegment

            try:
                raw_bg = AudioSegment.from_file(bg_path)[:6000]
                ratio = max(0.01, min(1.0, vol_pct / 100.0))
                volume_db = 20 * math.log10(ratio) - 4
                sample = (raw_bg + volume_db).fade_in(500).fade_out(1000)

                temp_f = tempfile.mktemp(suffix=".mp3")
                sample.export(temp_f, format="mp3")

                self.bg_preview_process = subprocess.Popen(["afplay", temp_f])
                self.bg_preview_process.wait()

                if os.path.exists(temp_f):
                    os.remove(temp_f)
            except Exception as e:
                print("Preview error:", e)
            finally:
                self.after(0, self._stop_bg_preview)

        threading.Thread(target=_preview, daemon=True).start()

    def _stop_bg_preview(self):
        if self.bg_preview_process and self.bg_preview_process.poll() is None:
            self.bg_preview_process.terminate()
            self.bg_preview_process = None
        self.bg_preview_btn.configure(text="🔊 Audition", fg_color="#334155", hover_color="#475569")
        self.status_label.configure(text="Ready to generate audio", text_color="#9CA3AF")

    def _get_selected_bg_path(self):
        choice = self.bg_menu.get()
        if choice == "📁 Custom audio file...":
            return self.custom_bg_path
        rel_path = BG_LABEL_TO_PATH.get(choice)
        if rel_path:
            return os.path.join(self.base_dir, rel_path)
        return None

    # ------------------ Text Editor Handlers ------------------
    def _load_initial_text(self):
        conv_path = os.path.join(self.base_dir, "conversation.txt")
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
            initialdir=self.folder_entry.get().strip() or self.base_dir,
        )
        if file_path:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                self.text_editor.delete("1.0", "end")
                self.text_editor.insert("1.0", f.read())
            # Auto-suggest file name or directory name depending on active mode
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            is_single = "Single" in self.export_mode_seg.get()
            self.target_name_entry.delete(0, "end")
            if is_single:
                self.target_name_entry.insert(0, f"{sanitize_directory_name(base_name)}.mp3")
            else:
                self.target_name_entry.insert(0, sanitize_directory_name(base_name))
            self._update_path_preview()
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
        old_controls = dict(self.speaker_controls)

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

            gender = prev_gender if prev_gender else guess_gender(speaker)
            gender_val = "👨 Male" if gender == "Male" else "👩 Female"

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

            voice_options = MALE_LABELS if gender == "Male" else FEMALE_LABELS

            if prev_voice and prev_voice in voice_options:
                default_voice = prev_voice
            else:
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
            title="Select Base Destination Folder",
            initialdir=self.folder_entry.get().strip() or self.base_dir,
        )
        if chosen:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, chosen)
            self._update_path_preview()

    # ------------------ Generation Workflow ------------------
    def _start_generation(self):
        if self.is_generating:
            return

        text = self.text_editor.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Empty Script", "Please enter or paste conversation dialogue first.")
            return

        base_folder = self.folder_entry.get().strip()
        if not base_folder:
            messagebox.showwarning("Missing Destination", "Please choose a destination folder.")
            return

        is_single = "Single" in self.export_mode_seg.get()
        mode = "single" if is_single else "project"
        raw_target_name = self.target_name_entry.get().strip()

        if is_single:
            file_name = raw_target_name if raw_target_name else "conversation.mp3"
            if not file_name.endswith(".mp3"):
                file_name = f"{file_name}.mp3"
            target_single_file = os.path.join(base_folder, file_name)
            target_dir = base_folder
            conv_name = os.path.splitext(file_name)[0]
        else:
            conv_name = sanitize_directory_name(raw_target_name or "Conversation")
            target_dir = os.path.join(base_folder, conv_name)
            target_single_file = None

        # Build voice map and speakers metadata for history
        voice_map = {}
        speakers_meta = []
        for speaker, controls in self.speaker_controls.items():
            label = controls["voice_menu"].get()
            voice_map[speaker] = ALL_VOICE_MAP.get(label, FALLBACK_VOICE)
            speakers_meta.append({
                "name": speaker,
                "gender": controls.get("gender", "Male"),
                "voice": label,
            })

        # Rate and pause
        rate_val = int(self.rate_slider.get())
        rate_str = f"{'+' if rate_val > 0 else ''}{rate_val}%"
        pause_ms = int(self.pause_slider.get())

        # Ambient background settings
        bg_path = self._get_selected_bg_path()
        bg_vol = int(self.bg_volume_slider.get())
        bg_meta = {
            "name": self.bg_menu.get(),
            "volume": bg_vol,
            "path": bg_path,
        }

        # Set UI to running state
        self.is_generating = True
        self.cancel_requested = False
        self.generate_btn.configure(state="disabled", text="⏳ Generating Audio...")
        self.cancel_btn.grid(row=0, column=1, padx=(6, 14), pady=(14, 8))
        self.progress_bar.set(0)
        self.status_label.configure(text="Initializing generation...", text_color="#60A5FA")
        self.result_frame.grid_remove()

        # Stop any ongoing playback
        self._stop_playback()
        self._stop_bg_preview()

        # Run background thread
        thread = threading.Thread(
            target=self._run_generation_thread,
            args=(text, voice_map, mode, target_dir, target_single_file, conv_name, rate_str, pause_ms, bg_path, bg_vol, speakers_meta, bg_meta),
            daemon=True,
        )
        thread.start()

    def _cancel_generation(self):
        if self.is_generating:
            self.cancel_requested = True
            self.status_label.configure(text="Cancelling generation...", text_color="#EF4444")

    def _run_generation_thread(self, text, voice_map, mode, target_dir, target_single_file, conv_name, rate_str, pause_ms, bg_path, bg_vol, speakers_meta, bg_meta):
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
                    mode=mode,
                    output_dir=target_dir,
                    conversation_name=conv_name,
                    single_output_file=target_single_file,
                    rate=rate_str,
                    pause_ms=pause_ms,
                    background_path=bg_path,
                    background_volume=bg_vol,
                    progress_callback=progress_callback,
                    is_cancelled=is_cancelled,
                )
            )

            # Auto-save to history on success
            if result:
                self.history_mgr.save_generation(
                    text=text,
                    audio_source_path=result["full_audio_file"],
                    duration_sec=result["duration_sec"],
                    speakers_meta=speakers_meta,
                    background_meta=bg_meta,
                    conversation_dir=result["conversation_dir"],
                    sentence_files=result.get("sentence_files", []),
                    mode=result.get("mode", mode),
                )
        except Exception as e:
            error_message = str(e)

        self.after(
            0,
            lambda: self._finish_generation_ui(result, error_message),
        )

    def _update_progress_ui(self, status_msg, progress_fraction):
        self.progress_bar.set(progress_fraction)
        self.status_label.configure(text=status_msg)

    def _finish_generation_ui(self, result, error_message):
        self.is_generating = False
        is_single = "Single" in self.export_mode_seg.get()
        default_btn_text = "🚀 Generate Single MP3 File" if is_single else "🚀 Generate Project Directory"
        self.generate_btn.configure(state="normal", text=default_btn_text)
        self.cancel_btn.grid_remove()

        if error_message:
            self.progress_bar.set(0)
            if "cancelled" in error_message.lower():
                self.status_label.configure(text="Generation was cancelled.", text_color="#F59E0B")
            else:
                self.status_label.configure(text=f"Error: {error_message}", text_color="#EF4444")
                messagebox.showerror("Generation Failed", error_message)
        else:
            self.last_generated_dir = result["conversation_dir"]
            self.last_generated_full_file = result["full_audio_file"]
            self.progress_bar.set(1.0)
            dur = result["duration_sec"]

            if result.get("mode") == "single":
                file_name = os.path.basename(result["full_audio_file"])
                kb = result["file_size_bytes"] / 1024
                self.status_label.configure(
                    text=f"🎉 Created '{file_name}' (Single MP3 • {dur:.1f}s • {kb:.1f} KB)",
                    text_color="#10B981",
                )
            else:
                n_sentences = len(result.get("sentence_files", []))
                self.status_label.configure(
                    text=f"🎉 Created '{os.path.basename(result['conversation_dir'])}' (Full MP3 {dur:.1f}s + {n_sentences} Sentence MP3s)",
                    text_color="#10B981",
                )
            self.result_frame.grid()
            # Refresh history tab content
            self._refresh_history_tab()

    # ------------------ Post-Generation Actions ------------------
    def _open_in_finder(self):
        target = self.last_generated_dir or self.folder_entry.get().strip() or self.base_dir
        if os.path.exists(target):
            subprocess.run(["open", target])

    def _toggle_playback(self):
        target_file = self.last_generated_full_file
        if not target_file or not os.path.exists(target_file):
            return

        if self.playing_file_path == target_file and self.current_player_process and self.current_player_process.poll() is None:
            self._stop_playback()
        else:
            self._start_playback(target_file)

    def _start_playback(self, file_path):
        self._stop_playback()
        self._stop_bg_preview()
        self.playing_file_path = file_path
        self.play_btn.configure(text="⏹️ Stop", fg_color="#DC2626", hover_color="#B91C1C")

        def _play():
            self.current_player_process = subprocess.Popen(["afplay", file_path])
            self.current_player_process.wait()
            self.after(0, self._on_playback_finished)

        threading.Thread(target=_play, daemon=True).start()

    def _stop_playback(self):
        if self.current_player_process and self.current_player_process.poll() is None:
            self.current_player_process.terminate()
            self.current_player_process = None
        self._on_playback_finished()


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = ConversationApp()
    app.mainloop()


if __name__ == "__main__":
    main()
