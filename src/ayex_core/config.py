import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


MAX_CHAT_WORDS = 80
DEFAULT_MODEL = "gpt-4.1"
DEFAULT_CHAT_MODEL = "gpt-4.1-mini"
DEFAULT_REASONING_MODEL = "gpt-4.1"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_CHAT_MAX_TOKENS = 180
DEFAULT_PLAN_MAX_TOKENS = 220
DEFAULT_SUMMARY_MAX_TOKENS = 160
DEFAULT_NUM_CTX = 2048
QUALITY_MIN_SCORE = 70
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "we",
    "what",
    "when",
    "where",
    "who",
    "why",
    "with",
    "you",
}


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def tokenize(text: str) -> List[str]:
    words = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    return [w for w in words if len(w) > 2 and w not in STOPWORDS]


@dataclass
class Settings:
    workspace: Path
    data_dir: Path
    profile_path: Path
    memory_path: Path
    episodes_path: Path
    projects_dir: Path

    @staticmethod
    def from_workspace(workspace: Path) -> "Settings":
        data_dir = workspace / ".ayex"
        return Settings(
            workspace=workspace,
            data_dir=data_dir,
            profile_path=data_dir / "profile.json",
            memory_path=data_dir / "memory.jsonl",
            episodes_path=data_dir / "episodes.jsonl",
            projects_dir=data_dir / "projects",
        )
