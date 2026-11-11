#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test runner for github-devops plugin."""

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Discover tests in plugin root tests/ and all skill test directories
    test_dirs = [ROOT / "tests"]
    for s_test in (ROOT / "skills").glob("*/tests"):
        test_dirs.append(s_test)

    for d in test_dirs:
        if d.is_dir():
            suite.addTests(loader.discover(start_dir=str(d), pattern="test_*.py", top_level_dir=str(d)))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    main()
