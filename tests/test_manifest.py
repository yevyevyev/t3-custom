"""Local contract tests for pinned T3 source builds."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("manifest_validator", ROOT / "scripts/validate-manifest.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
validate = validator.validate


class ManifestTests(unittest.TestCase):
    def test_checked_in_manifest(self):
        manifest = validate(str(ROOT / "manifest.json"))
        self.assertEqual(manifest["repository"], "pingdotgg/t3code")
        self.assertEqual([p["number"] for p in manifest["pullRequests"]], [31304, 32524, 32862])

    def test_reject_non_commit_pr_pins(self):
        with TemporaryDirectory() as d:
            f = Path(d) / "manifest.json"
            manifest = validate(str(ROOT / "manifest.json"))
            manifest["pullRequests"][0]["headSha"] = "main"
            f.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                validate(str(f))

    def test_reject_duplicate_prs(self):
        with TemporaryDirectory() as d:
            f = Path(d) / "manifest.json"
            manifest = validate(str(ROOT / "manifest.json"))
            manifest["pullRequests"].append(dict(manifest["pullRequests"][0]))
            f.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                validate(str(f))

    def test_reject_extra_manifest_fields(self):
        with TemporaryDirectory() as d:
            f = Path(d) / "manifest.json"
            manifest = validate(str(ROOT / "manifest.json"))
            manifest["unreviewedSource"] = "main"
            f.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                validate(str(f))

    def test_source_build_and_release_are_separate(self):
        workflow = (ROOT / ".github/workflows/build-release.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("if: ", workflow)
        self.assertIn("sha256sum -c SHA256SUMS", workflow)
        self.assertIn("scripts/provenance.py --verify", workflow)
        self.assertIn("scripts/assemble.sh manifest.json", workflow)
        self.assertIn("nix", (ROOT / "README.md").read_text())
        self.assertNotIn("nixos-rebuild switch", workflow)
        self.assertNotIn("nixos-rebuild switch", workflow)


if __name__ == "__main__":
    unittest.main()
