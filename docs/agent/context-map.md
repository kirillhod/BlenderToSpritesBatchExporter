# Context map

Use this before exploring the repository. `AGENTS.md` is loaded automatically;
do not re-read it. Read only the row you need.

## Do not read end to end

| File | Approx. tokens | Read instead |
| --- | ---: | --- |
| `IMPLEMENTATION_SEQUENCE.md` | 9.5k | `python tools/doc.py sequence O1`; one stage or task |
| `IMPROVEMENT_PLAN.md` | 6.5k | `python tools/doc.py plan 5`; one feature or rule |
| `CHANGELOG.md` | 3.6k | `python tools/doc.py changelog 2.1.3`; history only |
| `README.md` | 1.7k | `python tools/doc.py readme Collections` |
| `reports/` | 0.5-3k each | only for the reason behind a shipped rule; start at `reports/README.md` |
| `core/job.py` | 10.6k | grep the symbol; preflight is `_run_preflight`, the loop is `BatchJob` |
| `core/output.py` | 9.0k | grep the symbol; paths are `plan_output_paths` and `plan_node_output_paths` |
| `tests/smoke_blender.py` | 10.0k | grep the `run_*` function; coverage is in `docs/agent/smoke.md` |
| `tests/test_logic_unit.py` | 8.5k | grep the test class |
| `ui.py` | 5.0k | grep the panel class; the target table is in `BTS_PT_Source` |
| `tests/test_package_contract.py` | 2.5k | read it whole before changing IDs, versions or properties |

`python tools/doc.py --list` prints every heading with its line and size.
`AGENTS.md` and `docs/agent/*` are short; read them whole.

## Task map

| Task | Start here | Docs | Focused check |
| --- | --- | --- | --- |
| Panels, tooltips, density, target table | `ui.py` | plan §4; sequence U1-U5 | contract test + smoke |
| Target registry, export filter, Outliner link, status text | `core/targets.py`, `core/scene.py` | plan §4.3-§4.4; sequence U3-U4 | unit suite + smoke |
| Preflight, analysis cache, job loop, restore | `core/job.py` | plan §5, §8; sequence O3, C1 | smoke |
| Framing, padding, camera fit | `core/framing.py` | plan §5-§6 | `test_logic_unit.py` |
| Output paths, collisions, File Output nodes | `core/output.py` | plan §6.4; sequence V3-V4 | `test_logic_unit.py` |
| Bounds, isolation, hide and exclude state | `core/scene.py` | plan §3; sequence C1 | smoke |
| Presets, save and load | `core/presets.py` | plan §6.2 | `test_logic_unit.py` |
| Properties and update callbacks | `properties.py` | sequence O1, V1, A1 | contract test |
| Operators and tooltips | `operators.py` | plan §4.5; sequence U6 | contract test |
| Registration, handlers, version | `__init__.py`, `blender_manifest.toml` | release | contract test |
| IDs, property names, version pins | `tests/test_package_contract.py` | compatibility | contract test |
| Blender behavior | `tests/smoke_blender.py` | `docs/agent/smoke.md` | smoke |
| Release and tag | `docs/agent/release.md` | plan §13; sequence §14 | release checklist |
| Why an old rule exists | `reports/README.md`, `CHANGELOG.md` | - | - |

Focused checks from the repository root:

```powershell
python -m unittest discover -s tests -p "test_logic_unit.py"
python -m unittest discover -s tests -p "test_package_contract.py"
python -m unittest discover -s tests -p "test_docs.py"
```

The full unit command is in `AGENTS.md`. Blender smoke needs `BLENDER_EXE`.

## Module map

The import direction is one way: `ui` and `operators` call `logic`; `logic`
re-exports `core.*`; `core.*` never imports `ui` or `operators`.
`properties.py` is the only place where RNA properties are declared.

| Module | Owns |
| --- | --- |
| `core/targets.py` | target registry, sync, filter, Outliner link, override seeds, status, output lists |
| `core/scene.py` | bounds, source gathering, isolation and render-state restore |
| `core/framing.py` | axis math, padding and camera configuration |
| `core/job.py` | problems, analysis token, preflight, `BatchJob`, report |
| `core/output.py` | main-render paths, collisions, File Output node plans |
| `core/presets.py` | built-in and JSON presets |
| `core/common.py` | path helpers and image settings |
| `logic.py` | compatibility facade over `core.*` |
| `properties.py` | settings, target, preview and node property groups |
| `operators.py` | operators and their tooltips |
| `ui.py` | panels and UIList classes |
| `__init__.py` | registration, load and depsgraph handlers |

## Reading recipe

1. Locate the section: `python tools/doc.py --list sequence`, or grep a symbol.
2. Read one section or one code slice, about 200 lines at most.
3. Expand only the call sites that matter; do not sweep a directory.
4. For "where/how does this work" questions, send the `explore` subagent and
   keep the main context for edits.
5. Run the focused check while iterating and the full suite before claiming
   done. Add smoke only when the change touches Blender state.

## Budget signals

- The two planning documents together are about 16k tokens; one section is
  0.2-1.5k.
- `core/job.py`, `core/output.py` and `tests/smoke_blender.py` together are
  about 30k tokens; never open all three.
- `tests/test_logic_unit.py` is 8.5k; grep the test class instead.
- Screenshots, full command logs and encoded images are expensive. Print only
  the fields you need and capture a screenshot only for a visual decision.
