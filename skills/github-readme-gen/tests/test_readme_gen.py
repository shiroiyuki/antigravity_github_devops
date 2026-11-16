#!/usr/bin/env python3
"""Unit tests for github-readme-gen."""

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "readme_gen.py"
spec = importlib.util.spec_from_file_location("readme_gen", SCRIPT_PATH)
readme_gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readme_gen)


class TestReadmeGen(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_scan_and_render_plugin_readme(self):
        (self.test_dir / "plugin.json").write_text(
            json.dumps({
                "name": "sample-toolkit",
                "displayName": "Sample Toolkit",
                "version": "1.2.3",
                "description": "Sample plugin description.",
            }),
            encoding="utf-8",
        )
        skill_dir = self.test_dir / "skills" / "demo-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: demo-skill\ndescription: Demo skill action\n---\n# Demo\n",
            encoding="utf-8",
        )
        rules_dir = self.test_dir / "rules"
        rules_dir.mkdir()
        (rules_dir / "workflow.md").write_text(
            "---\ntrigger: model_decision\ndescription: Workflow rule\n---\n# Rule\n",
            encoding="utf-8",
        )
        (self.test_dir / "install.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        (self.test_dir / "run_tests.py").write_text("print('ok')\n", encoding="utf-8")
        (self.test_dir / "LICENSE").write_text("MIT\n", encoding="utf-8")

        out_file = readme_gen.generate_readme(self.test_dir, force=True)
        self.assertTrue(out_file.is_file())
        content = out_file.read_text(encoding="utf-8")
        self.assertIn("# Sample Toolkit (`sample-toolkit`)", content)
        self.assertIn("demo-skill", content)
        self.assertIn("workflow.md", content)
        self.assertIn("agy plugin validate . --strict", content)
        self.assertIn("sha256sum -c", content)


if __name__ == "__main__":
    unittest.main()
