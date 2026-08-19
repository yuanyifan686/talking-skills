from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_FILES = [
    ROOT / "skills" / "viral-script" / "tests" / "test_viral_script.py",
    ROOT / "skills" / "score-viral-script" / "tests" / "test_score_viral_script.py",
    ROOT / "skills" / "optimize-viral-script" / "tests" / "test_optimize_viral_script.py",
    ROOT / "skills" / "question-hook" / "tests" / "test_question_hook.py",
    ROOT / "skills" / "person-intro" / "tests" / "test_person_intro.py",
    ROOT / "runtime" / "tests" / "test_runtime.py",
    ROOT / "tests" / "test_protocol_and_adapters.py",
]


def main() -> int:
    failures = []
    for test_file in TEST_FILES:
        print(f"\n== {test_file.relative_to(ROOT)} ==", flush=True)
        completed = subprocess.run([sys.executable, str(test_file)], cwd=ROOT)
        if completed.returncode:
            failures.append(str(test_file))
    if failures:
        print("\nFailed test files:")
        print("\n".join(failures))
        return 1
    print("\nAll Talking Skills tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
