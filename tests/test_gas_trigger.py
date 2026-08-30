import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAS_SOURCE = ROOT / "gas" / "trigger_github_workflow.gs"
WORKFLOW = ROOT / ".github" / "workflows" / "daily-qiita-notify.yml"


class GasTriggerContractTests(unittest.TestCase):
    def test_gas_script_uses_script_property_and_dispatch_endpoint(self):
        source = GAS_SOURCE.read_text(encoding="utf-8")

        self.assertIn('getProperty("GITHUB_TOKEN")', source)
        self.assertIn("/actions/workflows/", source)
        self.assertIn('"/dispatches"', source)
        self.assertIn('JSON.stringify({ref: ref})', source)
        self.assertIn('"X-GitHub-Api-Version": "2022-11-28"', source)
        self.assertIn("muteHttpExceptions: true", source)
        self.assertIn("status === 204", source)
        self.assertIn("installTimeTriggers", source)
        self.assertNotRegex(source, r"(?:YOUR_|ghp_|github_pat_)[A-Za-z0-9_]+")

    def test_workflow_is_dispatch_only_and_read_only(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertIn("run: python run_pipeline.py", workflow)

    def test_notification_workflow_does_not_depend_on_retired_github_models(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn('SUMMARIZER_MODE: "rule"', workflow)
        self.assertIn('REQUIRE_LLM_SUCCESS: "false"', workflow)
        self.assertNotIn("GHUB_MODELS_API_KEY", workflow)
        self.assertNotIn("models.inference.ai.azure.com", workflow)


if __name__ == "__main__":
    unittest.main()
