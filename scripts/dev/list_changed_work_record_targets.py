"""List changed, explicitly publishable work-record basenames as JSON."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.validate_work_records import _parse_metadata  # noqa: E402


RECORD_PATH_RE = re.compile(
    r"^work-records/(?:md|metadata)/(work_record_[0-9]{3})\.(?:md|yml)$"
)


def changed_basenames(before: str, after: str, root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", before, after],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    basenames = {
        match.group(1)
        for path in result.stdout.splitlines()
        if (match := RECORD_PATH_RE.fullmatch(path))
    }
    return sorted(basenames)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--publish-only", action="store_true")
    args = parser.parse_args()

    basenames = changed_basenames(args.before, args.after, ROOT)
    if args.publish_only:
        basenames = [
            basename
            for basename in basenames
            if _parse_metadata(
                ROOT / "work-records" / "metadata" / f"{basename}.yml"
            )["publish"]
            is True
        ]
    print(json.dumps(basenames, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
