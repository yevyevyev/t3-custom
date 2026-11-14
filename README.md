# t3-custom

Independent **source-build and release pipeline** for [T3 Code](https://github.com/pingdotgg/t3code), with selected unmerged device fixes. This is not an official T3 release and not a fork of the full source tree. The build fetches a reviewed upstream commit and applies an exact, pinned patch stack.

## Patch set

The checked-in `manifest.json` pins T3 v0.1.9 upstream and these PR revisions:

| PR | Fix |
| --- | --- |
| [#31304](https://github.com/pingdotgg/t3code/pull/31304) | Prevent device interaction across thread ownership boundaries |
| [#32524](https://github.com/pingdotgg/t3code/pull/32524) | Release claimed devices when a thread settles |
| [#32862](https://github.com/pingdotgg/t3code/pull/32862) | Show the device owner and allow explicit takeover in the web UI |

The patches are applied from pinned **commit objects**, not floating PR branches. A conflict fails the build; rebase decisions need review.

## CI and releases

The workflow `.github/workflows/build-release.yml` runs on pushes and pull requests:

1. Validate the manifest and apply exact PR diffs to the pinned upstream source.
2. Set up upstream's Node/Vite+ toolchain, install dependencies and run device regression tests.
3. Build the Linux x64 server/web UI and the official-format self-contained CLI archive.
4. Run T3's archive smoke test, and record SHA-256 checksums and source/patch provenance.
5. Upload an Actions artifact for inspection.

**This workflow never deploys to downstream systems.** For a public release, manually dispatch the workflow from `main` with `publish: true`. The release job refuses to publish while this repository is private, because private Release assets cannot be fetched anonymously by NixOS. It creates a content-addressed GitHub Release tag and never overwrites a release.

**Repository visibility:** this repository was initially created **private**. To publish archives usable by `nixpkgs.fetchurl` without credentials, change visibility to **Public** in GitHub **Settings → General → Danger Zone → Change repository visibility**, after reviewing the files. Alternatively, retain privacy and introduce a separate public artifact host. Never bake a token into the Nix store or an artifact URL.

## Downstream consumption

This repository publishes T3 Linux x64 CLI archives that downstream
systems can fetch by an immutable release URL and a verified SHA-256 hash.
Packaging, deployment, and any release promotion into production remain
the responsibility of each consumer. No downstream machine is deployed
or configured by this pipeline.

Use the published `SHA256SUMS` and `build-manifest.json` to verify the
artifact before pinning it. The native mobile application changes in
upstream PR #32862 are not included in the Linux CLI archive.

## Local checks

```bash
python3 -m unittest discover -s tests -v
bash -n scripts/assemble.sh
python3 scripts/validate-manifest.py manifest.json
```

Avoid running development builds against production T3 state. Each new upstream version or patch revision should be pinned, reviewed and verified before publishing a release.
