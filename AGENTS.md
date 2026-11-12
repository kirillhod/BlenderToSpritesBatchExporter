# Project instructions

## Project

Blender To Sprites Batch Exporter is a GPL-3.0-or-later Blender add-on written
in Python. It renders Blender collections as separate sprites with an
auto-fitted orthographic camera.

Project sources of truth:

- `README.md` - user-facing behavior and installation.
- `IMPROVEMENT_PLAN.md` - v3 scope, roadmap and definition of done.
- `IMPLEMENTATION_SEQUENCE.md` - stage order, dependencies and release checks.
- `CHANGELOG.md` - released changes and version history.

Keep those documents in sync when a release, command or workflow changes. Do not
copy their full contents into this file.

## Environment

- Work on the `feature/improvements-v3` branch. `main` is the base branch.
- Use the system `python` for unit tests and tooling.
- Unit tests are Blender-free and use `tests/stub_bpy.py`.
- Smoke tests run inside Blender and load the working tree.
- Do not assume Blender is on `PATH` or at a fixed location. Never hardcode a
  machine-specific Blender path in the repository.
- Before a smoke test, use `$env:BLENDER_EXE` when it is set. If it is not set,
  ask the user for the Blender executable path.
- Do not claim a Blender version was tested unless that executable actually ran.
- `tests/run_tests.ps1` respects the `BLENDER_EXE` environment variable.

## Commands

Run from the repository root.

```powershell
python -m compileall -q blender_to_sprites_batch_exporter tests
python -m unittest discover -s tests -p "test_*.py"
$env:BLENDER_EXE = '<path to blender.exe>'
& $env:BLENDER_EXE -b --factory-startup --python tests\smoke_blender.py
./tools/build_zip.ps1
```

Success criteria:

- Unit tests end with `OK`.
- Smoke prints `SMOKE PASS` and exits with code 0.
- The zip is written to
  `dist/blender_to_sprites_batch_exporter-<version>.zip`.

Verify the built zip by importing it from its path in Blender and checking that
it registers and unregisters cleanly. `dist/` is gitignored; do not commit it.

## Architecture

- `blender_to_sprites_batch_exporter/` - the installable add-on.
- `ui.py` - panels and UIList classes.
- `operators.py` - operators and their tooltips.
- `properties.py` - RNA properties and property update callbacks.
- `logic.py` - compatibility facade that re-exports `core.*`.
- `core/` - Blender logic. It must not import `ui` or `operators`.
- `tests/` - unit tests, `stub_bpy.py`, and the Blender smoke suite.
- `tools/` - build and helper scripts.
- `reports/` - historical stage reports. Do not rewrite old reports.
- `legacy/` - the old single-file add-on. Not part of the current build.

## Compatibility rules

- Preserve every existing operator `bl_idname`.
- Do not add new operator IDs in v3.
- Preserve existing `scene.bts_settings` property names and enum identifiers.
  New properties are allowed when required, but update the package contract.
- Preserve panel IDs. `BTS_PT_report` keeps its ID even though its visible label
  is now `Log`.
- Register new `PropertyGroup` and `UIList` classes in `__init__.py`. Pin
  `UIList` IDs in `tests/test_package_contract.py` and add new
  `BTS_Settings` properties to its expected set.
- Keep features opt-in when they can change output. With new toggles off,
  existing scenes must keep their current output.
- Keep `blender_version_min = "5.2.0"` unless a documented API break requires a
  newer minimum.

## Target-list model

`export_source` is a filter over the persistent `target_items` registry. It
must filter both the visible target list and `gather_target_collections`; it
must not delete registry entries or reset their enabled flags. `Active
Collection` therefore shows only the active Outliner collection.

The active Outliner collection and `active_target_index` follow each other.
Set the active index through the suppression helper during sync so the property
callback does not write back to the Outliner and create a feedback loop.

`All` and `None` apply only to targets visible in the current export mode.

## UI conventions

- Keep interface text English, short and state-oriented.
- Static help belongs in tooltips. Do not add persistent hint labels.
- Wrap target, Path Preview and File Output `template_list` calls in a layout
  with `use_property_split = False`; otherwise rows inherit property-split
  layout and appear centred.
- Target rows use the fixed `Collection` / `Canvas / status` table.
- Path Preview and File Output node information use compact `template_list`
  views, not boxes that grow with the data.
- A skipped target shows the short `skipped` marker; keep the row compact.
- Do not draw the full export report in the UI. `Log` exposes `Copy Log` and
  `Open Log` only.

## Testing and verification

- Unit tests must remain Blender-free.
- Add or update smoke coverage when changing target filtering, Outliner
  linkage, output lists, preflight or rendering.
- PNG file hashes are unstable across runs. Compare decoded pixels, not file
  hashes.
- Do not claim a fix or release is complete without running the relevant
  commands and reporting their actual results.
- For visual UI changes, verify the result in Blender when possible; do not
  infer alignment from source alone.

## Release workflow

For a version release:

1. Update the version in `bl_info`, `blender_manifest.toml`,
   `tests/test_package_contract.py` and `CHANGELOG.md`.
2. Run unit tests and smoke.
3. Build the zip with `./tools/build_zip.ps1`.
4. Verify the zip imports, registers and unregisters in Blender.
5. Commit the release changes and create a tag `vX.Y.Z`.
6. Do not push unless explicitly asked.

Intermediate builds that are not committed do not get a tag. Document the
relationship in `CHANGELOG.md` and the planning documents.

## Git and scope

- Do not push unless explicitly asked.
- Do not rewrite history, move tags or force-push without explicit permission.
- Keep changes within the requested task. Do not add atlas packing, a CLI,
  metadata manifests, pivots, localization or a module split; these are
  explicit non-goals.
- English only in code, comments, documentation, tests and commit messages.
