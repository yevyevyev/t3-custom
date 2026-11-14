#!/usr/bin/env bash
# Assemble one reviewed source tree; never touch an existing destination.
set -euo pipefail
manifest="${1:-manifest.json}"
dest="${2:-}"
if [[ "$dest" != /* || -e "$dest" ]]; then
  echo 'Usage: scripts/assemble.sh manifest.json /absolute/non-existing/path' >&2
  exit 2
fi
command -v git >/dev/null
command -v python3 >/dev/null
python3 "$(dirname "$0")/validate-manifest.py" "$manifest"
readarray -t pins < <(python3 - "$manifest" <<'PY'
import json, sys
v = json.load(open(sys.argv[1]))
print(v['upstreamSha'])
for pr in v['pullRequests']:
    print(str(pr['number']) + ' ' + pr['headSha'])
PY
)
upstream="${pins[0]}"
# No shallow clone: merge-base needs ancestry. Blob-filtered to keep transfer smaller.
git clone --filter=blob:none --no-checkout https://github.com/pingdotgg/t3code.git "$dest"
git -C "$dest" checkout --detach "$upstream"
test "$(git -C "$dest" rev-parse HEAD)" = "$upstream"
for item in "${pins[@]:1}"; do
  read -r number pin <<< "$item"
  echo "Apply PR #$number pinned at $pin"
  git -C "$dest" fetch --no-tags origin "$pin"
  test "$(git -C "$dest" rev-parse FETCH_HEAD)" = "$pin"
  base="$(git -C "$dest" merge-base "$upstream" "$pin")"
  test -n "$base"
  # First prefer exact patch context. --3way can report false conflicts
  # when upstream has unrelated edits elsewhere in the same large test file.
  # On context mismatch, fall back to a real three-way merge; conflicts still
  # fail closed and require an explicitly reviewed pin/patch update.
  patch="$(mktemp)"
  git -C "$dest" diff --binary "$base" "$pin" -- > "$patch"
  if git -C "$dest" apply --index --check "$patch"; then
    git -C "$dest" apply --index "$patch"
  elif [[ "$number" == 32524 && "$pin" == 0d00de53b41238dc9a58e2269fec48ca04a2974f ]]; then
    # This pinned PR's tests were written before an upstream test-suite
    # refactor. Rebase only its test fixture with an audited, fail-closed
    # adapter; all production files still require a clean application.
    test_path="apps/server/src/orchestration-v2/ThreadSettlementService.test.ts"
    other="$(mktemp)"
    test_patch="$(mktemp)"
    git -C "$dest" diff --binary "$base" "$pin" -- . ":(exclude)$test_path" > "$other"
    git -C "$dest" apply --index "$other"
    git -C "$dest" diff --binary "$base" "$pin" -- "$test_path" > "$test_patch"
    git -C "$dest" apply --reject "$test_patch" || true
    python3 "$(dirname "$0")/adapt-settlement-tests.py" "$dest" "$pin"
    rm -f "$other" "$test_patch"
  else
    git -C "$dest" apply --3way --index "$patch"
  fi
  rm -f "$patch"
  git -C "$dest" -c user.name='t3-custom-ci' -c user.email='build@localhost' \
    commit -m "patch(t3): apply PR #$number ($pin)"
done
# An optional fail-closed policy for externally managed device tools.  Keep
# this patch in the audited build recipe, not in a downstream environment.
managed_patch="$(cd "$(dirname "$0")/.." && pwd)/patches/managed-device-tools.patch"
git -C "$dest" apply --index "$managed_patch"
git -C "$dest" -c user.name='t3-custom-ci' -c user.email='build@localhost' \
  commit -m 'patch(t3): support externally managed device tools'
git -C "$dest" diff --check
version="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["version"])' "$manifest")"
actual="$(git -C "$dest" show HEAD:apps/server/package.json | python3 -c 'import json,sys;print(json.load(sys.stdin)["version"])')"
if [[ "$actual" != "$version" ]]; then
  echo "Pinned T3 version $version differs from server $actual" >&2
  exit 1
fi
printf 'Patched source commit: %s\n' "$(git -C "$dest" rev-parse HEAD)"
