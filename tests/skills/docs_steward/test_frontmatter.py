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

    def test_dot_dot_dot_opener_is_not_frontmatter(self) -> None:
        # YAML 1.2: `---` opens a document, `...` ends one. A file that
        # begins with `...` is NOT frontmatter — auditing it as YAML
        # would lint ordinary prose under yamllint and silently skip any
        # fenced YAML before the next boundary.
        text = "...\nname: foo\n---\nactual body\n"
        self.assertEqual(extract_blocks(text), [])

    def test_dot_dot_dot_opener_does_not_swallow_later_fenced_yaml(self) -> None:
        # The misclassified `...`-opened block must not consume the rest of
        # the file: a well-formed fenced yaml block after it must still
        # be returned.
        text = (
            "...\n"
            "looks_like: yaml but isn't\n"
            "...\n"
            "intervening prose\n"
            "```yaml\n"
            "real: block\n"
            "```\n"
        )
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].kind, "fenced")
        self.assertIn("real: block", blocks[0].yaml_text)

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

    def test_fence_open_accepts_info_string_after_language_tag(self) -> None:
        # CommonMark allows info-string content after the language tag (e.g.
        # title= / linenums= attributes used by various renderers). The
        # parser must still recognize the block as yaml and audit it.
        text = '```yaml linenums="1" title="example"\nkey: value\n```\n'
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].kind, "fenced")
        self.assertIn("key: value", blocks[0].yaml_text)

    def test_fence_open_accepts_yml_alias_with_info_string(self) -> None:
        text = "```yml {.docs collapsed}\nkey: value\n```\n"
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].kind, "fenced")

    def test_closing_fence_may_be_longer_than_opener(self) -> None:
        # CommonMark allows the closing fence to use more backticks (or
        # tildes) than the opener — e.g. a yaml block opened with ``` and
        # closed with ````. Treating that as unterminated silently drops
        # the block from the audit.
        text = "```yaml\nkey: value\n````\nbody\n"
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].kind, "fenced")
        self.assertEqual(blocks[0].yaml_text, "key: value")

    def test_closing_fence_must_match_opener_character(self) -> None:
        # A block opened with backticks may NOT be closed with tildes.
        # This stays unterminated and is silently skipped.
        text = "```yaml\nkey: value\n~~~\nstill inside fence\n"
        self.assertEqual(extract_blocks(text), [])

    def test_fence_open_with_one_space_indent(self) -> None:
        # CommonMark allows 0-3 spaces of indentation before a fence.
        text = " ```yaml\nkey: value\n ```\nbody\n"
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].kind, "fenced")
        self.assertIn("key: value", blocks[0].yaml_text)

    def test_fence_open_with_three_space_indent(self) -> None:
        text = "   ```yaml\nkey: value\n```\n"
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].kind, "fenced")

    def test_fence_open_with_four_space_indent_is_not_a_fence(self) -> None:
        # 4-space indent makes this a CommonMark indented code block,
        # NOT a fenced code block. Must NOT be parsed as a yaml fence.
        text = "    ```yaml\nkey: value\n```\n"
        self.assertEqual(extract_blocks(text), [])

    def test_closing_fence_may_have_different_indent_than_opener(self) -> None:
        # Closing fence indent (0-3 spaces) is independent of opener indent.
        text = " ```yaml\nkey: value\n   ```\nbody\n"
        blocks = extract_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertIn("key: value", blocks[0].yaml_text)

    def test_unterminated_fence_does_not_drop_later_well_formed_fences(self) -> None:
        # Regression: when an earlier yaml opener never closed before EOF
        # the scanner used to `break` and silently drop every well-formed
        # yaml fence after it. Now we advance past the unmatched opener
        # and keep scanning so the second fence still lands in the audit.
        text = (
            "```yaml\n"
            "key: never closed\n"
            "more body text\n"
            "even more body\n"
            "```yaml\n"
            "actual: block\n"
            "```\n"
        )
        blocks = extract_blocks(text)
        # The first opener has no closer before the SECOND opener, so the
        # parser treats it as malformed and skips it; the well-formed
        # second block must still be reported.
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].kind, "fenced")
        self.assertIn("actual: block", blocks[0].yaml_text)

    def test_closing_fence_too_short_is_unterminated(self) -> None:
        # An opener with `````` cannot be closed by ```` (CommonMark requires
        # the closer to be at least as long as the opener).
        text = "````yaml\nkey: value\n```\nstill inside\n"
        self.assertEqual(extract_blocks(text), [])


if __name__ == "__main__":
    unittest.main()
