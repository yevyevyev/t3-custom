#!/usr/bin/env python3
"""Verify the release attestation, allowing only its known publication delay."""
import argparse
import re
import subprocess
import sys
import time

WAIT_SECONDS = 120
POLL_SECONDS = 5
COMMAND_TIMEOUT_SECONDS = 20


def verify(repo, tag, source_sha, *, run=subprocess.run, now=time.monotonic, sleep=time.sleep):
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("Expected a full lowercase source commit SHA")
    command = ["gh", "release", "verify", tag, "--repo", repo]
    absent = f"no attestations for tag {tag} (sha1:{source_sha})"
    deadline = now() + WAIT_SECONDS
    while True:
        remaining = deadline - now()
        if remaining <= 0:
            print("Release attestation did not become available within the deadline", file=sys.stderr)
            return 1
        try:
            result = run(command, capture_output=True, text=True,
                         timeout=min(COMMAND_TIMEOUT_SECONDS, remaining), check=False)
        except subprocess.TimeoutExpired:
            print("Release attestation verification timed out", file=sys.stderr)
            return 1
        if result.returncode == 0:
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
            return 0
        # The gh CLI reports this exact message when GitHub has not yet made
        # the new immutable release attestation available. Never treat other
        # errors, an unexpected commit, or extra diagnostics as transient.
        if result.returncode != 1 or result.stdout or result.stderr.rstrip("\n") != absent:
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
            return 1
        remaining = deadline - now()
        if remaining <= 0:
            print("Release attestation did not become available within the deadline", file=sys.stderr)
            return 1
        print("Release attestation is not available yet; checking again", file=sys.stderr)
        sleep(min(POLL_SECONDS, remaining))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    try:
        return verify(args.repo, args.tag, args.source_sha)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
