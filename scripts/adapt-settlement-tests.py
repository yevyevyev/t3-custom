#!/usr/bin/env python3
"""Explicit compatibility adaptation for the #32524 test patch on pinned newer T3.

The upstream test suite refactored existing Effect.scoped wrappers after this
PR branched, so a three-way patch reports a conflict in a test-only hunk.
This adapter preserves the newer test file, retains cleanly applied PR changes,
and transplants exactly the four new regression cases from the immutable PR
commit. Do not use it for other PRs without reviewing the adaptation.
"""
import re
import subprocess
import sys
from pathlib import Path

TEST_PATH = "apps/server/src/orchestration-v2/ThreadSettlementService.test.ts"
PINNED_PR = "0d00de53b41238dc9a58e2269fec48ca04a2974f"
CASE_NAMES = (
    "keeps the devices of a thread re-engaged while a release waits on the lock",
    "closes another thread's terminals while a device release waits on the lock",
    "releases a settled thread's devices without shutting them down",
    "releases the other devices and runs the settle script when one release fails",
)
NEW_FIRST = '  it.effect("' + CASE_NAMES[0] + '"'
NEXT_EXISTING = '  it.effect("runs the settle script in the thread\'s own worktree"'
SKIP_START = '  it.effect("skips the settle script for a thread re-engaged while its shells close"'
SKIP_END = '  it.effect("skips the settle script for a subagent in its parent\'s worktree"'


def exactly_once(text: str, pattern: str) -> int:
    count = text.count(pattern)
    if count != 1:
        raise ValueError(f"Expected 1 occurrence of {pattern!r}, got {count}")
    return text.index(pattern)


def adapt(checkout: Path, pr_sha: str) -> None:
    if pr_sha != PINNED_PR:
        raise ValueError("Unsupported PR #32524 revision; review its test diff first")
    path = checkout / TEST_PATH
    reject = path.with_name(path.name + ".rej")
    if not reject.is_file():
        raise ValueError("Expected a reviewable rejected test-only hunk")
    rejected = reject.read_text()
    hunks = len(re.findall(r"(?m)^@@", rejected))
    if not 1 <= hunks <= 2 or CASE_NAMES[0] not in rejected:
        raise ValueError(f"Unexpected #32524 rejected hunks: {hunks} hunks")
    # The PR test fixture updates must already have applied normally.
    current = path.read_text()
    expected_fixture_parts = (
        'import * as DeviceService from "../device/DeviceService.ts";',
        '  DeviceHostUnavailableError,',
        "  readonly onDeviceClose?:",
        "  const deviceCloses = yield* Ref.make<",
        "    Layer.mock(DeviceService.DeviceService)({",
        "    deviceCloses,",
    )
    for marker in expected_fixture_parts:
        if marker not in current:
            raise ValueError(f"Missing cleanly patched fixture prerequisite: {marker}")
    if any(case in current for case in CASE_NAMES):
        raise ValueError("Test insertion already applied or duplicate patch")

    pr = subprocess.check_output(
        ["git", "-C", str(checkout), "show", f"{pr_sha}:{TEST_PATH}"], text=True
    )
    first = exactly_once(pr, NEW_FIRST)
    end = exactly_once(pr, NEXT_EXISTING)
    if not first < end:
        raise ValueError("Unexpected PR test ordering")
    block = pr[first:end]
    if any(block.count(name) != 1 for name in CASE_NAMES):
        raise ValueError("PR regression block contains missing/duplicate test cases")
    insert_at = exactly_once(current, NEXT_EXISTING)
    current = current[:insert_at] + block + current[insert_at:]

    skip_start = exactly_once(current, SKIP_START)
    skip_end = exactly_once(current, SKIP_END)
    if skip_start >= skip_end:
        raise ValueError("Unexpected existing test ordering")
    skip = current[skip_start:skip_end]
    needle = '        assert.strictEqual((yield* Queue.take(fixture.scriptRuns)).threadId, marker.id);'
    if needle not in skip:
        # Upstream may change indentation; this is intentionally fail-closed.
        raise ValueError("Cannot locate re-engaged thread assertion to strengthen")
    new_assertion = (
        '\n        yield* service.drain;'
        '\n        assert.deepStrictEqual('
        '\n          (yield* Ref.get(fixture.deviceCloses)).filter((close) => close.threadId === settled.id),'
        '\n          [],'
        '\n        );'
    )
    if "yield* service.drain;" not in skip:
        skip = skip.replace(needle, needle + new_assertion, 1)
    elif "fixture.deviceCloses" not in skip:
        raise ValueError("Unexpected existing drain assertion without device check")
    current = current[:skip_start] + skip + current[skip_end:]
    for name in CASE_NAMES:
        exactly_once(current, name)
    path.write_text(current)
    reject.unlink()
    subprocess.run(["git", "-C", str(checkout), "add", "--", TEST_PATH], check=True)
    print("Applied reviewed #32524 settlement test adaptation")


if __name__ == "__main__":
    try:
        adapt(Path(sys.argv[1]), sys.argv[2])
    except (OSError, ValueError, subprocess.CalledProcessError, IndexError) as error:
        print(f"Settlement test adaptation blocked: {error}", file=sys.stderr)
        raise SystemExit(1)
