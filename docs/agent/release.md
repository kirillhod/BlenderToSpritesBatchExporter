# Release

Use this for a `vX.Y.Z` release. An intermediate build that is not committed
gets no tag. Never push, publish, create a release or move a tag unless the
user explicitly asks.

## Version locations

All four must match in the tagged commit:

- `bl_info["version"]` in `blender_to_sprites_batch_exporter/__init__.py`;
- `version` in `blender_to_sprites_batch_exporter/blender_manifest.toml`;
- the expected version in `tests/test_package_contract.py`;
- the newest section in `CHANGELOG.md`.

`tools/build_zip.ps1` reads the manifest version, so a stale manifest names the
zip incorrectly.

## Steps

1. Confirm the target version and that the user asked for a release.
2. Bump the four version locations in one change.
3. Update the release records as needed:
   - `README.md` only when user-facing behavior changed;
   - plan §13 and sequence §12 checklists when a stage closes;
   - plan §11 and sequence §11 when a milestone lands;
   - `CHANGELOG.md` with the user-visible changes.
4. Run the checks from the repository root:

   ```powershell
   python -m compileall -q blender_to_sprites_batch_exporter tests
   python -m unittest discover -s tests -p "test_*.py"
   $env:BLENDER_EXE = '<path to blender.exe>'
   & $env:BLENDER_EXE -b --factory-startup --python tests\smoke_blender.py
   ./tools/build_zip.ps1
   ```

   Unit tests must end with `OK`; smoke must print `SMOKE PASS` and exit 0.
5. Verify the zip at
   `dist/blender_to_sprites_batch_exporter-<version>.zip`: import it from its
   path in Blender and check that it registers and unregisters cleanly.
6. Commit the release changes, then tag that exact commit:

   ```powershell
   git tag vX.Y.Z
   git show vX.Y.Z:blender_to_sprites_batch_exporter/blender_manifest.toml
   git tag --list 'v*'
   ```

7. Do not push. `dist/` is gitignored; do not commit it.

## Rules

- One version per commit; do not tag a commit that lacks a version update.
- Never rewrite history, move tags or force-push without explicit permission.
- Keep `blender_version_min = "5.2.0"` unless a documented API break requires
  a newer minimum.
- Record which Blender executable was tested. A 5.3 run does not verify 5.2.
