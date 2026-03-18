import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from .config import Settings
from .memory import MemoryStore
from .system import ConfirmFn, run_cmd, split_shell


class ToolManager:
    def __init__(self, settings: Settings, memory: MemoryStore, confirm_fn: ConfirmFn):
        self.s = settings
        self.memory = memory
        self.confirm_fn = confirm_fn

    def _resolve(self, path: str) -> Path:
        p = (self.s.workspace / path).resolve() if not os.path.isabs(path) else Path(path).resolve()
        if self.s.workspace not in p.parents and p != self.s.workspace:
            raise ValueError("Path is outside workspace")
        return p

    def read_file(self, path: str) -> str:
        p = self._resolve(path)
        if not p.exists():
            raise FileNotFoundError(path)
        return p.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str, require_confirm: bool = True) -> str:
        p = self._resolve(path)
        if require_confirm and not self.confirm_fn(f"Ahmet, {p} dosyasina yazmayi onayliyor musun?"):
            return "Yazma islemi iptal edildi."
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Yazildi: {p}"

    def list_files(self, directory: str = ".") -> List[str]:
        d = self._resolve(directory)
        if not d.exists():
            raise FileNotFoundError(directory)
        out: List[str] = []
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x != ".git"]
            for f in files:
                p = Path(root) / f
                out.append(str(p.relative_to(self.s.workspace)))
                if len(out) >= 500:
                    return out
        return out

    def search_in_files(self, pattern: str) -> str:
        if not pattern.strip():
            return ""
        try:
            code, out, err = run_cmd(
                ["rg", "--line-number", "--hidden", "--glob", "!.git", pattern, "."],
                self.s.workspace,
            )
            if code not in {0, 1}:
                return f"Arama basarisiz: {err.strip()}"
            return out.strip()
        except FileNotFoundError:
            matches: List[str] = []
            regex = re.compile(pattern)
            for rel in self.list_files("."):
                p = self.s.workspace / rel
                try:
                    text = p.read_text(encoding="utf-8")
                except Exception:
                    continue
                for i, line in enumerate(text.splitlines(), start=1):
                    if regex.search(line):
                        matches.append(f"{rel}:{i}:{line}")
            return "\n".join(matches)

    def git_status(self) -> str:
        _, out, err = run_cmd(["git", "status", "--short"], self.s.workspace)
        return out.strip() if out.strip() else err.strip()

    def git_diff(self) -> str:
        _, out, err = run_cmd(["git", "diff"], self.s.workspace)
        return out if out.strip() else err

    def git_commit(self, message: str, require_confirm: bool = True) -> str:
        if require_confirm and not self.confirm_fn(f'Ahmet, "{message}" mesaji ile commit olusturulsun mu?'):
            return "Commit iptal edildi."
        code, _, err = run_cmd(["git", "commit", "-m", message], self.s.workspace)
        if code != 0:
            return f"Commit basarisiz: {err.strip()}"
        return "Commit olusturuldu."

    def run_tests(self, command: str) -> str:
        args = split_shell(command)
        if not args:
            return "Test komutu verilmedi."
        allowed = {"pytest", "npm", "pnpm", "yarn", "uv", "python"}
        if args[0] not in allowed:
            return f"Test komutu engellendi. Izinli onekler: {', '.join(sorted(allowed))}"
        code, out, err = run_cmd(args, self.s.workspace, timeout=600)
        return f"[exit={code}]\n{out}{err}"

    def project_list(self) -> List[str]:
        return self.memory.project_list()

    def project_open(self, name: str) -> Dict[str, Any]:
        return self.memory.project_open(name)

    def task_add(self, name: str, text: str, priority: str = "medium") -> Dict[str, Any]:
        return self.memory.task_add(name, text, priority)

    def task_list(self, name: str) -> List[Dict[str, Any]]:
        return self.memory.task_list(name)

    def apply_unified_diff(self, patch_text: str, require_confirm: bool = True) -> str:
        if require_confirm and not self.confirm_fn("Ahmet, onerilen diff dosyalara uygulansin mi?"):
            return "Patch uygulama iptal edildi."
        with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False, encoding="utf-8") as tf:
            tf.write(patch_text)
            tmp_path = tf.name
        try:
            code, _, err = run_cmd(["git", "apply", "--whitespace=nowarn", tmp_path], self.s.workspace)
            if code != 0:
                return f"Patch uygulama basarisiz: {err.strip()}"
            return "Patch basariyla uygulandi."
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def dispatch_shell_style(self, line: str) -> str:
        args = split_shell(line)
        if not args:
            return "Arac komutu yok."
        cmd = args[0]
        rest = args[1:]
        try:
            if cmd == "read_file" and len(rest) == 1:
                return self.read_file(rest[0])
            if cmd == "write_file" and len(rest) >= 2:
                path = rest[0]
                content = " ".join(rest[1:])
                return self.write_file(path, content, require_confirm=True)
            if cmd == "list_files":
                directory = rest[0] if rest else "."
                return "\n".join(self.list_files(directory))
            if cmd == "search_in_files" and rest:
                return self.search_in_files(" ".join(rest))
            if cmd == "git_status":
                return self.git_status()
            if cmd == "git_diff":
                return self.git_diff()
            if cmd == "git_commit" and rest:
                return self.git_commit(" ".join(rest), require_confirm=True)
            if cmd == "run_tests" and rest:
                return self.run_tests(" ".join(rest))
            if cmd == "project_list":
                return "\n".join(self.project_list())
            if cmd == "project_open" and len(rest) == 1:
                return json.dumps(self.project_open(rest[0]), indent=2)
            if cmd == "task_add" and len(rest) >= 2:
                name = rest[0]
                priority = "medium"
                text_parts = rest[1:]
                if text_parts and text_parts[0].startswith("priority="):
                    priority = text_parts[0].split("=", 1)[1]
                    text_parts = text_parts[1:]
                return json.dumps(self.task_add(name, " ".join(text_parts), priority), indent=2)
            if cmd == "task_list" and len(rest) == 1:
                return json.dumps(self.task_list(rest[0]), indent=2)
        except Exception as e:
            return f"Arac hatasi: {e}"
        return "Bilinmeyen arac kullanimi."
