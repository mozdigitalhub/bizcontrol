from pathlib import Path
import re

from django.test import SimpleTestCase


class PtPtVocabularyGuardTests(SimpleTestCase):
    FORBIDDEN_PATTERNS = [
        r"\bcadastro\b",
        r"\bcadastrar\b",
        r"\busu[áa]rio\b",
        r"\busu[áa]rios\b",
        r"\busuario\b",
        r"\busuarios\b",
        r"\bsenha\b",
        r"\bfaturamento\b",
        r"\barquivo\b",
        r"\barquivos\b",
        r"\bdeletar\b",
        r"\bcontato\b",
        r"\bcontatos\b",
        r"\bendereco\b",
        r"\benderecos\b",
        r"\bregistrar\b",
    ]

    def _project_root(self):
        return Path(__file__).resolve().parents[1]

    def _iter_files(self):
        root = self._project_root()
        for path in (root / "templates").rglob("*.html"):
            yield path
        for path in root.rglob("*.py"):
            rel = path.relative_to(root).as_posix()
            if "/migrations/" in rel:
                continue
            if "/tests" in rel or rel.endswith(".py") and "/tests_" in rel:
                continue
            if rel.endswith("tests_vocabulary_ptpt.py"):
                continue
            yield path

    def test_no_forbidden_br_terms_in_ui_and_messages(self):
        combined = re.compile("|".join(self.FORBIDDEN_PATTERNS), re.IGNORECASE)
        hits = []
        for path in self._iter_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for line_no, line in enumerate(text.splitlines(), start=1):
                match = combined.search(line)
                if match:
                    hits.append(
                        f"{path.relative_to(self._project_root())}:{line_no} -> {match.group(0)}"
                    )
        self.assertFalse(
            hits,
            "Foram encontrados termos BR proibidos:\n" + "\n".join(hits[:80]),
        )
