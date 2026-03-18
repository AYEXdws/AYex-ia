import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import Settings, now_iso, tokenize


class MemoryStore:
    def __init__(self, settings: Settings):
        self.s = settings
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        self.s.data_dir.mkdir(parents=True, exist_ok=True)
        self.s.projects_dir.mkdir(parents=True, exist_ok=True)
        if not self.s.profile_path.exists():
            profile = {
                "name": "Ahmet",
                "assistant_name": "AYEX",
                "tone": "Profesyonel, oz ve terminal-oncelikli",
                "preferences": [],
                "projects": [],
                "current_project": None,
                "updated_at": now_iso(),
            }
            self.s.profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        if not self.s.memory_path.exists():
            self.s.memory_path.write_text("", encoding="utf-8")
        if not self.s.episodes_path.exists():
            self.s.episodes_path.write_text("", encoding="utf-8")

    def load_profile(self) -> Dict[str, Any]:
        return json.loads(self.s.profile_path.read_text(encoding="utf-8"))

    def save_profile(self, profile: Dict[str, Any]) -> None:
        profile["updated_at"] = now_iso()
        self.s.profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    def update_profile(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        profile = self.load_profile()
        profile.update(updates)
        self.save_profile(profile)
        return profile

    def append_memory(self, text: str, kind: str = "fact", tags: Optional[List[str]] = None) -> None:
        entry = {"ts": now_iso(), "kind": kind, "text": text, "tags": tags or []}
        with self.s.memory_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")

    def _iter_memory_entries(self) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for line in self.s.memory_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def _iter_episode_entries(self) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for line in self.s.episodes_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def append_episode(self, topic: str, summary: str, facts: Optional[List[str]] = None) -> None:
        entry = {
            "ts": now_iso(),
            "topic": topic.strip()[:120],
            "summary": summary.strip()[:2000],
            "facts": (facts or [])[:8],
        }
        with self.s.episodes_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")

    def _project_state_path(self, name: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("_")
        if not safe:
            raise ValueError("Invalid project name")
        return self.s.projects_dir / safe / "state.json"

    def project_list(self) -> List[str]:
        return sorted([p.parent.name for p in self.s.projects_dir.glob("*/state.json")])

    def project_open(self, name: str) -> Dict[str, Any]:
        path = self._project_state_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            state = {"name": name, "tasks": [], "notes": [], "status": "active", "updated_at": now_iso()}
            path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        profile = self.load_profile()
        projects = set(profile.get("projects", []))
        projects.add(name)
        profile["projects"] = sorted(projects)
        profile["current_project"] = name
        self.save_profile(profile)
        return json.loads(path.read_text(encoding="utf-8"))

    def load_project_state(self, name: str) -> Dict[str, Any]:
        path = self._project_state_path(name)
        if not path.exists():
            raise ValueError(f"Project does not exist: {name}")
        return json.loads(path.read_text(encoding="utf-8"))

    def save_project_state(self, name: str, state: Dict[str, Any]) -> None:
        path = self._project_state_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = now_iso()
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def task_add(self, name: str, text: str, priority: str = "medium") -> Dict[str, Any]:
        state = self.project_open(name)
        item = {
            "id": len(state.get("tasks", [])) + 1,
            "text": text,
            "priority": priority,
            "status": "todo",
            "created_at": now_iso(),
        }
        state.setdefault("tasks", []).append(item)
        self.save_project_state(name, state)
        return item

    def task_list(self, name: str) -> List[Dict[str, Any]]:
        return self.load_project_state(name).get("tasks", [])

    def retrieve(self, query: str, limit: int = 8) -> List[str]:
        qtokens = set(tokenize(query))
        scored: List[Tuple[int, str]] = []

        profile = self.load_profile()
        profile_lines = [
            f"profile.name: {profile.get('name', '')}",
            f"profile.tone: {profile.get('tone', '')}",
            f"profile.preferences: {', '.join(profile.get('preferences', []))}",
            f"profile.current_project: {profile.get('current_project', '')}",
            f"profile.projects: {', '.join(profile.get('projects', []))}",
        ]
        for line in profile_lines:
            score = len(qtokens.intersection(tokenize(line)))
            if score > 0:
                scored.append((score + 1, line))

        for entry in self._iter_memory_entries():
            text = f"memory[{entry.get('kind', 'fact')}]: {entry.get('text', '')}"
            score = len(qtokens.intersection(tokenize(text)))
            if score > 0:
                scored.append((score + 2, text))

        episodes = self._iter_episode_entries()
        ep_total = len(episodes)
        for idx, ep in enumerate(episodes):
            topic = ep.get("topic", "")
            summary = ep.get("summary", "")
            facts_list = ep.get("facts", [])
            facts = ", ".join(facts_list)
            text = f"episode[{topic}]: {summary} | facts: {facts}"
            # Skorlamada sabit kaliplari degil, konu ve olgulari agirliklandir.
            score_text = f"{topic} {' '.join(facts_list)}"
            score = len(qtokens.intersection(tokenize(score_text)))
            recency_bonus = 2 if idx >= max(0, ep_total - 3) else (1 if idx >= max(0, ep_total - 8) else 0)
            if score > 0:
                scored.append((score + 5 + recency_bonus, text))

        for name in self.project_list():
            state = self.load_project_state(name)
            lines = [f"project[{name}] status: {state.get('status', '')}"]
            for task in state.get("tasks", [])[-20:]:
                lines.append(f"project[{name}] task {task.get('id')}: {task.get('text')} ({task.get('status')})")
            for note in state.get("notes", [])[-10:]:
                lines.append(f"project[{name}] note: {note}")
            for line in lines:
                score = len(qtokens.intersection(tokenize(line)))
                if score > 0:
                    scored.append((score + 1, line))

        if not scored:
            return ["Dogrudan ilgili bellek bulunamadi."]
        scored.sort(key=lambda x: x[0], reverse=True)
        unique: List[str] = []
        seen = set()
        for _, snippet in scored:
            if snippet not in seen:
                seen.add(snippet)
                unique.append(snippet)
            if len(unique) >= limit:
                break
        return unique
