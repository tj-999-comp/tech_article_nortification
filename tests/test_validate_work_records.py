import tempfile
import unittest
from pathlib import Path

from scripts.validate_work_records import ValidationError, validate_work_records


ROOT = Path(__file__).resolve().parents[1]


class WorkRecordValidatorTests(unittest.TestCase):
    def test_current_records_match_and_are_not_publishable(self):
        names = validate_work_records(ROOT, require_publish_false=True)
        self.assertEqual(names[0], "work_record_001")
        self.assertEqual(names[-1], "work_record_010")
        self.assertEqual(len(names), 10)

    def test_rejects_mismatched_metadata_basename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            md_dir = root / "work-records" / "md"
            metadata_dir = root / "work-records" / "metadata"
            md_dir.mkdir(parents=True)
            metadata_dir.mkdir()
            (md_dir / "work_record_001.md").write_text(
                "# 作業記録 001: テスト\n", encoding="utf-8"
            )
            (metadata_dir / "work_record_002.yml").write_text(
                "schema_version: 1\n"
                "title: テスト\n"
                "date: \"2026-08-27\"\n"
                "project_id: tech_article_nortification\n"
                "tags:\n  - test\n"
                "publish: false\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValidationError):
                validate_work_records(root)


if __name__ == "__main__":
    unittest.main()
