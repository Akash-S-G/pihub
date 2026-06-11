from __future__ import annotations

import re


class FormulaPreserver:
    """Detect and preserve formulas/equations as atomic blocks."""

    FORMULA_LINE = re.compile(
        r"(=|\+|\-|\*|/|\^|\bE\s*=\s*mc\^?2\b|\b[a-zA-Z]\s*=\s*[a-zA-Z0-9\+\-\*/\^\(\)]+)"
    )

    def is_formula_block(self, paragraph: str) -> bool:
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        if not lines:
            return False
        matches = sum(1 for line in lines if self.FORMULA_LINE.search(line))
        return matches >= max(1, len(lines) // 2)
