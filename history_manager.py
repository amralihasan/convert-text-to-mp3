import json
import os
import shutil
import time
from datetime import datetime


class HistoryManager:
    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        self.history_dir = os.path.join(base_dir, "history")
        self.audio_dir = os.path.join(self.history_dir, "audio")
        self.texts_dir = os.path.join(self.history_dir, "texts")
        self.index_file = os.path.join(self.history_dir, "index.json")

        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(self.audio_dir, exist_ok=True)
        os.makedirs(self.texts_dir, exist_ok=True)
        if not os.path.exists(self.index_file):
            self._save_index([])

    def _load_index(self):
        try:
            if os.path.exists(self.index_file):
                with open(self.index_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_index(self, data):
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_generation(
        self,
        text: str,
        audio_source_path: str,
        duration_sec: float,
        speakers_meta: list = None,
        background_meta: dict = None,
        conversation_dir: str = None,
        sentence_files: list = None,
        custom_title: str = None,
        mode: str = "project",
    ):
        """
        Saves a conversation text, full MP3, and sentence files into persistent history.
        """
        now = datetime.now()
        entry_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 10000:04d}"

        # Clean title from text
        first_line = ""
        for line in text.strip().splitlines():
            line = line.strip()
            if line:
                first_line = line
                break
        if not first_line:
            first_line = "Conversation"

        title = custom_title if custom_title else (first_line[:80] + ("..." if len(first_line) > 80 else ""))

        # Save text file in history
        text_filename = f"{entry_id}.txt"
        text_dest = os.path.join(self.texts_dir, text_filename)
        with open(text_dest, "w", encoding="utf-8") as f:
            f.write(text)

        # Copy full audio file to history
        audio_filename = f"{entry_id}.mp3"
        audio_dest = os.path.join(self.audio_dir, audio_filename)
        if os.path.exists(audio_source_path):
            shutil.copy2(audio_source_path, audio_dest)
        else:
            raise FileNotFoundError(f"Source audio file not found: {audio_source_path}")

        file_size_bytes = os.path.getsize(audio_dest)
        total_lines = len([l for l in text.splitlines() if l.strip()])

        entry = {
            "id": entry_id,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "title": title,
            "mode": mode,
            "conversation_dir": conversation_dir or os.path.dirname(audio_source_path),
            "conversation_name": os.path.basename(conversation_dir) if conversation_dir else "Conversation",
            "text_file": text_dest,
            "audio_file": audio_dest,
            "duration_sec": round(duration_sec, 1),
            "file_size_bytes": file_size_bytes,
            "speakers": speakers_meta or [],
            "background": background_meta or None,
            "lines_count": total_lines,
            "sentence_files": sentence_files or [],
            "original_destination": audio_source_path,
        }

        records = self._load_index()
        records.insert(0, entry)  # Prepend newest first
        self._save_index(records)

        return entry

    def get_all(self):
        """Returns all entries, validating that audio files exist."""
        records = self._load_index()
        valid = []
        changed = False

        for r in records:
            if os.path.exists(r["audio_file"]) and os.path.exists(r["text_file"]):
                valid.append(r)
            else:
                changed = True

        if changed:
            self._save_index(valid)

        return valid

    def get_entry(self, entry_id: str):
        """Get a single entry by id."""
        for r in self.get_all():
            if r["id"] == entry_id:
                return r
        return None

    def delete(self, entry_id: str):
        """Deletes an entry and its associated files."""
        records = self._load_index()
        new_records = []

        for r in records:
            if r["id"] == entry_id:
                try:
                    if os.path.exists(r["audio_file"]):
                        os.remove(r["audio_file"])
                except OSError:
                    pass
                try:
                    if os.path.exists(r["text_file"]):
                        os.remove(r["text_file"])
                except OSError:
                    pass
            else:
                new_records.append(r)

        self._save_index(new_records)
        return new_records

    def get_text(self, entry_id: str) -> str:
        """Read the conversation text for an entry."""
        entry = self.get_entry(entry_id)
        if entry and os.path.exists(entry["text_file"]):
            with open(entry["text_file"], "r", encoding="utf-8") as f:
                return f.read()
        return ""
