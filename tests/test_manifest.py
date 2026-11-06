"""Reolink in Core is the only owner of the shared library version."""

import json
from pathlib import Path
import unittest


class ManifestTests(unittest.TestCase):
    def test_reolink_supplies_shared_library(self):
        path = Path(__file__).resolve().parents[1] / "custom_components/ptz_telemetry/manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("reolink", manifest["after_dependencies"])
        self.assertFalse(any(req.lower().replace("_", "-").startswith("reolink-aio")
                             for req in manifest.get("requirements", [])))
