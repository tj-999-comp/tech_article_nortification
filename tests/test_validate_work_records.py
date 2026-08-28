import tempfile
import unittest
from pathlib import Path

from scripts.validate_publish_request import validate_publish_request
from scripts.validate_work_records import ValidationError, validate_work_records


ROOT = Path(__file__).resolve().parents[1]


class WorkRecordValidatorTests(unittest.TestCase):
    def test_current_records_match_and_are_not_publishable(self):
        names = validate_work_records(ROOT, require_publish_false=True)
        self.assertEqual(names[0], "work_record_001")
        self.assertEqual(names[-1], "work_record_013")
        self.assertEqual(len(names), 13)

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

    def test_publish_request_accepts_only_an_explicitly_enabled_target(self):
        with self._fixture_root() as root:
            metadata = root / "work-records" / "metadata" / "work_record_001.yml"
            metadata.write_text(
                metadata.read_text(encoding="utf-8").replace(
                    "publish: false", "publish: true"
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                validate_publish_request(
                    root,
                    project_id="tech_article_nortification",
                    source_commit_sha="a" * 40,
                    target_basename="work_record_001",
                ),
                "work_record_001",
            )

    def test_publish_request_rejects_disabled_target_and_untrusted_inputs(self):
        with self._fixture_root() as root:
            with self.assertRaisesRegex(ValidationError, "project_id"):
                validate_publish_request(
                    root,
                    project_id="another-project",
                    source_commit_sha="a" * 40,
                    target_basename="work_record_001",
                )
            with self.assertRaisesRegex(ValidationError, "publish must be true"):
                validate_publish_request(
                    root,
                    project_id="tech_article_nortification",
                    source_commit_sha="a" * 40,
                    target_basename="work_record_001",
                )
            with self.assertRaisesRegex(ValidationError, "40-character commit SHA"):
                validate_publish_request(
                    root,
                    project_id="tech_article_nortification",
                    source_commit_sha="main",
                    target_basename="work_record_001",
                )
            with self.assertRaisesRegex(ValidationError, "does not exist"):
                validate_publish_request(
                    root,
                    project_id="tech_article_nortification",
                    source_commit_sha="a" * 40,
                    target_basename="work_record_002",
                )
            with self.assertRaisesRegex(ValidationError, "basename"):
                validate_publish_request(
                    root,
                    project_id="tech_article_nortification",
                    source_commit_sha="a" * 40,
                    target_basename="work-records/md/work_record_001",
                )

    def test_workflow_is_read_only_and_has_exact_dispatch_contract(self):
        workflow = (ROOT / ".github/workflows/validate-work-records.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertNotIn("repository_dispatch", workflow)

    def test_publish_workflow_has_exact_inputs_and_no_contents_write(self):
        workflow = (ROOT / ".github/workflows/publish-work-record.yml").read_text(
            encoding="utf-8"
        )
        inputs_section = workflow.split("    inputs:\n", 1)[1].split(
            "\n\npermissions:", 1
        )[0]
        input_names = {
            line.strip()[:-1]
            for line in inputs_section.splitlines()
            if line.startswith("      ")
            and not line.startswith("        ")
            and line.endswith(":")
        }
        self.assertEqual(
            input_names, {"project_id", "source_commit_sha", "target_basename"}
        )
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("repository_dispatch", workflow)
        self.assertIn("accept-source.yml", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("SANDBOX_PAGES_DISPATCH_TOKEN", workflow)


if __name__ == "__main__":
    unittest.main()
