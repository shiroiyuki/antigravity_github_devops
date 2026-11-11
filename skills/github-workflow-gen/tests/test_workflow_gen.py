#!/usr/bin/env python3
"""
Unit tests for github-workflow-gen
"""

import unittest
import tempfile
import shutil
from pathlib import Path

# 動態加載 workflow_gen
import importlib.util
SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "workflow_gen.py"
spec = importlib.util.spec_from_file_location("workflow_gen", SCRIPT_PATH)
workflow_gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow_gen)


class TestWorkflowGen(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_generate_workflow_file(self):
        wf_file = workflow_gen.generate_workflow(self.test_path)
        self.assertTrue(wf_file.exists())
        self.assertEqual(wf_file.name, "ci.yml")

        content = wf_file.read_text(encoding="utf-8")
        # 驗證關鍵步驟
        self.assertIn("Run Unit Tests", content)
        self.assertIn("Validate Standards", content)
        self.assertIn("Generate Release Notes from Commits", content)
        self.assertIn("sha256sum", content)
        self.assertIn("generate_release_notes: true", content)


if __name__ == "__main__":
    unittest.main()
