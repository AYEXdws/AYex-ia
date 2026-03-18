import shlex
import subprocess
from pathlib import Path
from typing import Callable, List, Tuple


def confirm_input(prompt: str) -> bool:
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def run_cmd(args: List[str], cwd: Path, timeout: int = 120) -> Tuple[int, str, str]:
    proc = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def split_shell(command: str) -> List[str]:
    return shlex.split(command)


ConfirmFn = Callable[[str], bool]
