from __future__ import annotations

import unittest

from app.educational.textbook_builder import TextbookBuilder


class TextbookBuilderTests(unittest.TestCase):
    def test_builds_structured_table_and_formula_blocks(self) -> None:
        rows = [
            {
                "chunk_id": "table_1",
                "text": "Quantity    Cost\n1 notebook    20\n2 notebooks    40\n4 notebooks    80",
                "metadata": {"content_type": "table", "grade": 8, "subject": "maths", "chapter": "proportion", "topic": "direct proportion"},
            },
            {
                "chunk_id": "formula_1",
                "text": "Formula: y = kx. This means y changes in the same ratio as x.",
                "metadata": {
                    "content_type": "formula_explanation",
                    "grade": 8,
                    "subject": "maths",
                    "chapter": "proportion",
                    "topic": "direct proportion",
                    "formula_intelligence": [
                        {
                            "formula": "y = kx",
                            "formula_type": "equation",
                            "meaning": "y changes in the same ratio as x.",
                            "variables": {"x": "input quantity", "y": "output quantity", "k": "constant"},
                            "units": {},
                        }
                    ],
                },
            },
        ]

        textbook, report = TextbookBuilder().build(
            rows,
            pack_id="grade8_maths_proportion",
            metadata={"grade": 8, "subject": "maths", "chapter": "proportion", "language": "english"},
            concepts=[],
        )

        blocks = [block for section in textbook["sections"] for block in section["blocks"]]
        table_blocks = [block for block in blocks if block["type"] == "table"]
        formula_blocks = [block for block in blocks if block["type"] == "formula"]

        self.assertEqual(report["table_blocks"], 1)
        self.assertEqual(report["formula_blocks"], 1)
        self.assertEqual(table_blocks[0]["rows"][0], ["Quantity", "Cost"])
        self.assertEqual(formula_blocks[0]["formula"], "y = kx")
        self.assertEqual(formula_blocks[0]["variables"][0]["symbol"], "k")


if __name__ == "__main__":
    unittest.main()
