import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT_DOCS = sorted((ROOT / "docs" / "agent").glob("*.md"))
LINKED_DOCS = [ROOT / "AGENTS.md", ROOT / "reports" / "README.md", *AGENT_DOCS]

REQUIRED_DOCS = (
    "AGENTS.md",
    "docs/agent/context-map.md",
    "docs/agent/smoke.md",
    "docs/agent/release.md",
    "docs/agent/ui.md",
    "docs/agent/ui-proposals.md",
    "reports/README.md",
)


def load_doc_tool():
    path = ROOT / "tools" / "doc.py"
    spec = importlib.util.spec_from_file_location("bts_doc_tool", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DocToolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load_doc_tool()

    def test_known_sections(self):
        cases = (
            ("plan", "5", "per-collection overrides"),
            ("sequence", "O1", "O1. Properties"),
            ("changelog", "2.1.3", "[2.1.3]"),
            ("readme", "Collections", "## Collections"),
            ("context", "Task map", "## Task map"),
        )
        for doc, query, expected in cases:
            with self.subTest(doc=doc, query=query):
                self.assertIn(expected, self.tool.find_section(doc, query))

    def test_unknown_section_fails(self):
        with self.assertRaises(LookupError):
            self.tool.find_section("plan", "99.99")

    def test_section_list_covers_stage_ids(self):
        headings = self.tool.parse_headings(self.tool.read_lines("sequence"))
        keys = {heading.key for heading in headings}
        for key in ("5", "o1", "o2", "c1", "a8"):
            self.assertIn(key, keys)


class AgentDocsTest(unittest.TestCase):
    def test_required_docs_exist(self):
        for relative in REQUIRED_DOCS:
            path = ROOT / relative
            with self.subTest(path=relative):
                self.assertTrue(path.is_file(), relative)
                self.assertTrue(
                    path.read_text(encoding="utf-8").startswith("# "),
                    "%s needs a top-level heading" % relative,
                )

    def test_relative_links_resolve(self):
        failures = []
        for path in LINKED_DOCS:
            text = path.read_text(encoding="utf-8")
            for target in re.findall(r"\]\(([^)\s]+)\)", text):
                if re.match(r"^(?:https?:|mailto:|#)", target):
                    continue
                without_anchor = target.split("#", 1)[0]
                if not without_anchor:
                    continue
                resolved = (path.parent / without_anchor).resolve()
                if not resolved.exists():
                    failures.append(
                        "%s -> %s" % (path.relative_to(ROOT), target)
                    )
        self.assertEqual(
            failures,
            [],
            "broken relative links:\n" + "\n".join(failures),
        )

    def test_no_machine_specific_blender_path(self):
        for path in [ROOT / "AGENTS.md", *AGENT_DOCS]:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotIn("SteamLibrary", text)
                self.assertIsNone(
                    re.search(r"[A-Za-z]:\\", text),
                    "%s contains a drive-letter path" % path.name,
                )
        self.assertIn(
            "BLENDER_EXE",
            (ROOT / "AGENTS.md").read_text(encoding="utf-8"),
        )

    def test_context_docs_stay_small(self):
        limits = (
            ("AGENTS.md", 9000),
            ("docs/agent/context-map.md", 9000),
            ("docs/agent/ui.md", 15000),
            ("docs/agent/ui-proposals.md", 15000),
        )
        for relative, limit in limits:
            size = len((ROOT / relative).read_text(encoding="utf-8"))
            with self.subTest(path=relative):
                self.assertLessEqual(
                    size,
                    limit,
                    "%s is %d characters; keep it under %d" % (relative, size, limit),
                )


if __name__ == "__main__":
    unittest.main()
