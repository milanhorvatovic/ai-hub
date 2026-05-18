"""frontmatter.extract_blocks — grammar coverage for both block kinds."""

from __future__ import annotations

import unittest

from docs_steward.frontmatter import extract_blocks


class FrontmatterExtractionTests(unittest.TestCase):
    def test_empty_file_yields_no_blocks(self) -> None:
        self.assertEqual(extract_blocks(""), [])

    def test_no_yaml_anywhere_yields_no_blocks(self) -> None:
        self.assertEqual(extract_blocks("# Heading\n\nProse only.\n"), [])

    def test_top_of_file_frontmatter(self) -> None:
        text = "---\nname: foo\nversion: 1.0.0\n---\n\n# Heading\n"
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].kind, "frontmatter")
        self.assertEqual(blocks[0].yaml_text, "name: foo\nversion: 1.0.0")
        self.assertEqual(blocks[0].anchor, "frontmatter")

    def test_frontmatter_with_dot_dot_dot_terminator(self) -> None:
        text = "---\nname: foo\n...\n\nbody\n"
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].kind, "frontmatter")

    def test_unterminated_frontmatter_is_skipped(self) -> None:
        text = "---\nname: foo\n# no closer\n"
        self.assertEqual(extract_blocks(text), [])

    def test_frontmatter_must_be_at_top(self) -> None:
        # A `---` block in the middle of a file is NOT frontmatter.
        text = "# Heading\n\n---\nname: foo\n---\n"
        self.assertEqual(extract_blocks(text), [])

    def test_fenced_yaml_block_with_backticks(self) -> None:
        text = (
            "# Heading\n\n"
            "```yaml\n"
            "key: value\n"
            "list:\n"
            "  - one\n"
            "  - two\n"
            "```\n"
        )
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].kind, "fenced")
        self.assertIn("key: value", blocks[0].yaml_text)
        self.assertTrue(blocks[0].anchor.startswith("yaml fence:"))

    def test_fenced_yml_alias_is_recognized(self) -> None:
        text = "```yml\nkey: value\n```\n"
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].kind, "fenced")

    def test_fenced_yaml_with_tildes(self) -> None:
        text = "~~~yaml\nkey: value\n~~~\n"
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].kind, "fenced")

    def test_fenced_yaml_case_insensitive(self) -> None:
        text = "```YAML\nkey: value\n```\n"
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 1)

    def test_non_yaml_fence_is_ignored(self) -> None:
        text = "```python\nprint('hi')\n```\n```json\n{}\n```\n"
        self.assertEqual(extract_blocks(text), [])

    def test_unterminated_fence_is_skipped(self) -> None:
        text = "```yaml\nkey: value\n# no closer\n"
        self.assertEqual(extract_blocks(text), [])

    def test_multiple_fences_returned_in_order(self) -> None:
        text = (
            "```yaml\nfirst: 1\n```\n"
            "intervening prose\n"
            "```yaml\nsecond: 2\n```\n"
        )
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 2)
        self.assertIn("first", blocks[0].yaml_text)
        self.assertIn("second", blocks[1].yaml_text)

    def test_frontmatter_plus_fence_returns_both(self) -> None:
        text = (
            "---\nname: foo\n---\n\n"
            "# Heading\n\n"
            "```yaml\nkey: value\n```\n"
        )
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].kind, "frontmatter")
        self.assertEqual(blocks[1].kind, "fenced")

    def test_fence_anchor_truncated_for_long_first_line(self) -> None:
        long_line = "key_that_is_quite_long: value_with_lots_of_extra_text_here"
        text = f"```yaml\n{long_line}\n```\n"
        block = extract_blocks(text)[0]
        # Anchor should include "yaml fence:" prefix + truncated/ellipsized excerpt.
        self.assertTrue(block.anchor.startswith("yaml fence:"))
        self.assertIn("…", block.anchor)


if __name__ == "__main__":
    unittest.main()
