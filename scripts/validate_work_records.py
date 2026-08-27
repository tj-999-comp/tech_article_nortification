"""Validate a_rendered work-record inputs without third-party dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path


PROJECT_ID = "tech_article_nortification"
RECORD_RE = re.compile(r"^work_record_([0-9]{3})$")
REQUIRED_KEYS = {
    "schema_version",
    "title",
    "date",
    "project_id",
    "tags",
    "publish",
}
TOP_LEVEL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(.*)$")


class ValidationError(ValueError):
    """Raised when a work-record input violates the source contract."""


def _error(path: Path, line: int | None, message: str) -> ValidationError:
    location = f"{path}:{line}" if line is not None else str(path)
    return ValidationError(f"{location}: {message}")


def _scalar(value: str, path: Path, line: int) -> str:
    value = value.strip()
    if not value:
        raise _error(path, line, "value is required")
    if value.startswith(("&", "*", "!", "[", "{", "|", ">")):
        raise _error(path, line, "unsupported YAML scalar syntax")
    if value.startswith('"'):
        if len(value) < 2 or not value.endswith('"'):
            raise _error(path, line, "unterminated double-quoted scalar")
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise _error(path, line, f"invalid double-quoted scalar: {exc.msg}") from exc
        if not isinstance(parsed, str):
            raise _error(path, line, "scalar must be a string")
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise _error(path, line, "unterminated single-quoted scalar")
        return value[1:-1].replace("''", "'")
    if value.endswith(("\t", "\r")) or "\t" in value:
        raise _error(path, line, "tabs are not allowed")
    return value


def _parse_metadata(path: Path) -> dict[str, object]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise _error(path, None, "metadata must be UTF-8") from exc

    values: dict[str, object] = {}
    in_tags = False
    for line_number, raw_line in enumerate(lines, start=1):
        if "\t" in raw_line:
            raise _error(path, line_number, "tabs are not allowed")
        if not raw_line.strip():
            continue
        if raw_line.startswith("  - "):
            if not in_tags:
                raise _error(path, line_number, "list item is outside tags")
            values.setdefault("tags", []).append(
                _scalar(raw_line[4:], path, line_number)
            )
            continue
        if raw_line.startswith(" "):
            raise _error(path, line_number, "unexpected indentation")

        match = TOP_LEVEL_RE.fullmatch(raw_line)
        if not match:
            raise _error(path, line_number, "invalid top-level YAML mapping")
        key, raw_value = match.groups()
        if key in values:
            raise _error(path, line_number, f"duplicate key: {key}")
        if key == "tags":
            if raw_value.strip():
                raise _error(path, line_number, "tags must be a block sequence")
            values[key] = []
            in_tags = True
            continue
        in_tags = False
        values[key] = _scalar(raw_value, path, line_number)

    missing = REQUIRED_KEYS - values.keys()
    unknown = values.keys() - REQUIRED_KEYS
    if missing:
        raise _error(path, None, f"missing metadata keys: {', '.join(sorted(missing))}")
    if unknown:
        raise _error(path, None, f"unknown metadata keys: {', '.join(sorted(unknown))}")

    if values["schema_version"] != "1":
        raise _error(path, None, "schema_version must be 1")
    if not isinstance(values["title"], str) or not values["title"].strip():
        raise _error(path, None, "title must be a non-empty string")
    if values["project_id"] != PROJECT_ID:
        raise _error(path, None, f"project_id must be {PROJECT_ID}")

    date_value = values["date"]
    if not isinstance(date_value, str):
        raise _error(path, None, "date must be a string")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date_value):
        raise _error(path, None, "date must be YYYY-MM-DD")
    try:
        date.fromisoformat(date_value)
    except ValueError as exc:
        raise _error(path, None, "date must be YYYY-MM-DD") from exc

    tags = values["tags"]
    if not isinstance(tags, list) or not tags or any(
        not isinstance(tag, str) or not tag.strip() for tag in tags
    ):
        raise _error(path, None, "tags must be a non-empty string array")
    if len(set(tags)) != len(tags):
        raise _error(path, None, "tags must not contain duplicates")

    publish = values["publish"]
    if publish not in {"true", "false"}:
        raise _error(path, None, "publish must be true or false")
    values["schema_version"] = 1
    values["publish"] = publish == "true"
    return values


def _record_basename(path: Path, suffix: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise _error(path, None, "must be a regular file, not a symlink or directory")
    if path.suffix != suffix:
        raise _error(path, None, f"unexpected file extension; expected {suffix}")
    basename = path.stem
    match = RECORD_RE.fullmatch(basename)
    if not match or not 1 <= int(match.group(1)) <= 999:
        raise _error(path, None, "basename must match work_record_001..work_record_999")
    return basename


def _validate_markdown(path: Path, basename: str) -> None:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise _error(path, None, "Markdown must be UTF-8") from exc
    if "\x00" in content:
        raise _error(path, None, "NUL bytes are not allowed")
    first_line = content.splitlines()[0] if content.splitlines() else ""
    number = basename.rsplit("_", 1)[1]
    if not first_line.startswith(f"# 作業記録 {number}:"):
        raise _error(path, 1, "first heading must match the record basename")
    if re.search(r"(?i)(javascript|vbscript|data):", content):
        raise _error(path, None, "active or data URL schemes are not allowed")
    if re.search(r"\]\(\s*//", content):
        raise _error(path, None, "protocol-relative links are not allowed")


def validate_work_records(root: Path, *, require_publish_false: bool = False) -> list[str]:
    work_records = root / "work-records"
    if not work_records.is_dir() or work_records.is_symlink():
        raise _error(work_records, None, "work-records directory is required")

    entries = {entry.name for entry in work_records.iterdir()}
    if entries != {"md", "metadata"}:
        raise _error(work_records, None, "only md/ and metadata/ are allowed")

    md_dir = work_records / "md"
    metadata_dir = work_records / "metadata"
    if any(entry.is_symlink() or not entry.is_dir() for entry in (md_dir, metadata_dir)):
        raise _error(work_records, None, "md/ and metadata/ must be regular directories")

    md_files = sorted(md_dir.iterdir(), key=lambda path: path.name)
    metadata_files = sorted(metadata_dir.iterdir(), key=lambda path: path.name)
    md_names = {_record_basename(path, ".md") for path in md_files}
    metadata_names = {_record_basename(path, ".yml") for path in metadata_files}
    if md_names != metadata_names:
        missing_md = sorted(metadata_names - md_names)
        missing_metadata = sorted(md_names - metadata_names)
        raise _error(
            work_records,
            None,
            f"Markdown/metadata basenames do not match; missing_md={missing_md}, "
            f"missing_metadata={missing_metadata}",
        )

    for basename in sorted(md_names):
        markdown_path = md_dir / f"{basename}.md"
        metadata_path = metadata_dir / f"{basename}.yml"
        _validate_markdown(markdown_path, basename)
        metadata = _parse_metadata(metadata_path)
        if require_publish_false and metadata["publish"] is not False:
            raise _error(metadata_path, None, "publish must remain false for this validation")
    return sorted(md_names)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--require-publish-false",
        action="store_true",
        help="fail if any metadata requests publication",
    )
    args = parser.parse_args(argv)
    try:
        names = validate_work_records(
            args.root.resolve(), require_publish_false=args.require_publish_false
        )
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"validated {len(names)} work record(s): {', '.join(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
