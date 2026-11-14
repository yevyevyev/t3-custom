"""Behavioral tests for the release-attestation publication wait."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_verifier", ROOT / "scripts/verify-release-attestation.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
SHA = "a" * 40
TAG = "custom-t3-v0.1.9-123456789abc"
ABSENT = f"no attestations for tag {TAG} (sha1:{SHA})\n"


class Clock:
    def __init__(self):
        self.current = 0
        self.sleeps = []

    def now(self):
        return self.current

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.current += seconds


class VerifyTests(unittest.TestCase):
    def execute(self, results):
        clock = Clock()
        calls = []
        sequence = iter(results)

        def run(command, **kwargs):
            calls.append((command, kwargs))
            item = next(sequence)
            if isinstance(item, Exception):
                raise item
            return item

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = verifier.verify("owner/repo", TAG, SHA, run=run, now=clock.now, sleep=clock.sleep)
        return result, calls, clock

    @staticmethod
    def response(code, stderr="", stdout=""):
        return subprocess.CompletedProcess([], code, stdout=stdout, stderr=stderr)

    def test_waits_for_exact_absence_then_verifies(self):
        result, calls, clock = self.execute([self.response(1, ABSENT), self.response(0, stdout="verified\n")])
        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 2)
        self.assertEqual(clock.sleeps, [5])
        self.assertEqual(calls[0][0], ["gh", "release", "verify", TAG, "--repo", "owner/repo"])
        self.assertLessEqual(calls[0][1]["timeout"], verifier.COMMAND_TIMEOUT_SECONDS)

    def test_other_failures_fail_without_retry(self):
        for response in (
            self.response(1, "signature verification failed\n"),
            self.response(1, ABSENT.replace(SHA, "b" * 40)),
            self.response(1, ABSENT + "unexpected diagnostic\n"),
            self.response(1, ABSENT, stdout="unexpected output"),
            self.response(2, ABSENT),
        ):
            with self.subTest(response=response):
                result, calls, clock = self.execute([response])
                self.assertEqual(result, 1)
                self.assertEqual(len(calls), 1)
                self.assertEqual(clock.sleeps, [])

    def test_absence_has_bounded_wait_and_fails_closed(self):
        result, calls, clock = self.execute([self.response(1, ABSENT)] * 25)
        self.assertEqual(result, 1)
        self.assertEqual(clock.current, verifier.WAIT_SECONDS)
        self.assertEqual(len(calls), 24)

    def test_command_timeout_fails_without_retry(self):
        result, calls, clock = self.execute([subprocess.TimeoutExpired("gh", 20)])
        self.assertEqual(result, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(clock.sleeps, [])

    def test_invalid_sha_is_rejected(self):
        with self.assertRaises(ValueError):
            verifier.verify("owner/repo", TAG, "main")


if __name__ == "__main__":
    unittest.main()
