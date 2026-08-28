"""Validate a single, explicitly requested work-record publication."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    from .validate_work_records import (
        PROJECT_ID,
        ValidationError,
        _error,
        _parse_metadata,
        _validate_markdown,
        validate_work_records,
    )
except ImportError:  # pragma: no cover - exercised when run as a script
    from validate_work_records import (  # type: ignore[no-redef]
        PROJECT_ID,
        ValidationError,
        _error,
        _parse_metadata,
        _validate_markdown,
        validate_work_records,
    )


SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
RECORD_RE = re.compile(r"^work_record_([0-9]{3})$")


def validate_publish_request(
    root: Path,
    *,
    project_id: str,
    source_commit_sha: str,
    target_basename: str,
) -> str:
    """Validate request inputs and the selected record.

    The complete source tree is validated first. The selected record must then
    explicitly opt in with ``publish: true``; this prevents a request from
    publishing a disabled record or an arbitrary path.
    """

    if project_id != PROJECT_ID:
        raise _error(root, None, f"project_id must be {PROJECT_ID}")
    if not SHA_RE.fullmatch(source_commit_sha):
        raise _error(root, None, "source_commit_sha must be a 40-character commit SHA")

    record_match = RECORD_RE.fullmatch(target_basename)
    if not record_match or not 1 <= int(record_match.group(1)) <= 999:
        raise _error(
            root,
            None,
            "target_basename must match work_record_001..work_record_999",
        )

    names = validate_work_records(root)
    if target_basename not in names:
        raise _error(root / "work-records", None, "target_basename does not exist")

    markdown_path = root / "work-records" / "md" / f"{target_basename}.md"
    metadata_path = root / "work-records" / "metadata" / f"{target_basename}.yml"
    _validate_markdown(markdown_path, target_basename)
    metadata = _parse_metadata(metadata_path)
    if metadata["publish"] is not True:
        raise _error(
            metadata_path,
            None,
            "publish must be true for an explicit publication request",
        )
    return target_basename


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--source-commit-sha", required=True)
    parser.add_argument("--target-basename", required=True)
    args = parser.parse_args(argv)

    try:
        basename = validate_publish_request(
            args.root.resolve(),
            project_id=args.project_id,
            source_commit_sha=args.source_commit_sha,
            target_basename=args.target_basename,
        )
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"validated publication request: {basename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
