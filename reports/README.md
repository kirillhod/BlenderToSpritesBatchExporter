# Stage reports

Historical record for the 1.x and 2.0.x work. Read a report only when you need
the reason behind a shipped rule, a regression or a design decision. Do not
update old reports and do not treat them as a plan; current scope lives in
`IMPROVEMENT_PLAN.md` and `IMPLEMENTATION_SEQUENCE.md`.

| Report | Scope | Version |
| --- | --- | --- |
| `STAGE_00_REPORT.md` | preparation and baseline | 1.2.0 |
| `STAGE_01_REPORT.md` | P0 hotfix in the monolith | 1.2.1 |
| `STAGE_02_REPORT.md` | split into five files | 1.3.0 |
| `STAGE_03_REPORT.md` | predictable paths, node checks, state, isolation | 1.3.1 |
| `STAGE_04_REPORT.md` | preflight, `BatchJob`, cancellation | 1.4.0 |
| `STAGE_05_REPORT.md` | rebuilt interface | 2.0.0 |
| `HOTFIX_2_0_1_REPORT.md` | first 2.0.x fixes | 2.0.1 |
| `HOTFIX_2_0_2_REPORT.md` | second 2.0.x fixes | 2.0.2 |
| `HOTFIX_2_0_3_REPORT.md` | third 2.0.x fixes | 2.0.3 |
| `HOTFIX_2_0_4_REPORT.md` | fourth 2.0.x fixes | 2.0.4 |
| `UX_REVIEW_COLLECTION_GOES_TO.md` | File Output and `Collection Goes To` review | 2.0.x |

For released user-visible changes read `CHANGELOG.md`. For current v3 stages
read `IMPLEMENTATION_SEQUENCE.md`; use `python tools/doc.py sequence O1` for a
single task.
