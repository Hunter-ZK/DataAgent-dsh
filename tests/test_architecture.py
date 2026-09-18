import subprocess
import sys
from pathlib import Path


def test_core_does_not_depend_on_adapters_or_dsh_frameworks() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / "scripts/check_architecture.py")], cwd=root, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
