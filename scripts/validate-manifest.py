#!/usr/bin/env python3
"""Validate the entire pinned T3 build manifest before any network use."""
import json
import re
import sys
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")


def validate(path: str) -> dict:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict) or set(value) != {"schema", "repository", "upstreamSha", "version", "pullRequests"}:
        raise ValueError("Unexpected/missing manifest keys")
    if value["schema"] != 1 or value["repository"] != "pingdotgg/t3code":
        raise ValueError("Unsupported manifest schema/repository")
    if not isinstance(value["upstreamSha"], str) or not SHA.fullmatch(value["upstreamSha"]):
        raise ValueError("Invalid pinned upstream SHA")
    if not isinstance(value["version"], str) or not VERSION.fullmatch(value["version"]):
        raise ValueError("Invalid release version")
    prs = value["pullRequests"]
    if not isinstance(prs, list) or not prs:
        raise ValueError("Need at least one pinned PR")
    ids = set()
    for pr in prs:
        if not isinstance(pr, dict) or set(pr) != {"number", "headSha"}:
            raise ValueError("Unexpected PR fields")
        if type(pr["number"]) is not int or pr["number"] <= 0 or pr["number"] in ids:
            raise ValueError("Invalid/duplicate PR number")
        ids.add(pr["number"])
        if not isinstance(pr["headSha"], str) or not SHA.fullmatch(pr["headSha"]):
            raise ValueError("Invalid pinned PR head SHA")
    return value


if __name__ == "__main__":
    try:
        v = validate(sys.argv[1] if len(sys.argv) > 1 else "manifest.json")
        print(f"Valid pinned T3 manifest: {v['upstreamSha']} + {len(v['pullRequests'])} PRs")
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as ex:
        print(f"Invalid manifest: {ex}", file=sys.stderr)
        raise SystemExit(1)
