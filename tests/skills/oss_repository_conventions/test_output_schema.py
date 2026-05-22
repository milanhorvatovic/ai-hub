"""Validate the audit-output NDJSON contract.

`references/output-format.schema.json` is the machine-checkable contract for the
audit NDJSON finding stream; `references/output-format.example.ndjson` is the
worked fixture. These tests read the constraints *from the schema* (required
keys, enums, patterns, additionalProperties) and enforce them on the example, so
the schema and fixture can't silently diverge — without needing the third-party
`jsonschema` package (the skill's tests run on the Python stdlib only).
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def _schema(references_dir: Path) -> dict:
    return json.loads(
        (references_dir / "output-format.schema.json").read_text(encoding="utf-8")
    )


def _example_lines(references_dir: Path) -> list[str]:
    text = (references_dir / "output-format.example.ndjson").read_text(
        encoding="utf-8"
    )
    return [ln for ln in text.splitlines() if ln.strip()]


def test_schema_is_valid_json_with_expected_shape(references_dir: Path) -> None:
    schema = _schema(references_dir)
    assert schema.get("type") == "object"
    assert schema.get("additionalProperties") is False
    for key in ("domain", "check", "severity", "status", "message"):
        assert key in schema["required"], f"schema missing required key {key}"
    assert set(schema["properties"]["severity"]["enum"]) == {
        "must",
        "should",
        "could",
    }
    assert set(schema["properties"]["status"]["enum"]) == {
        "pass",
        "fail",
        "warn",
        "skip",
    }


def test_example_lines_are_valid_json(references_dir: Path) -> None:
    lines = _example_lines(references_dir)
    assert lines, "example NDJSON is empty"
    for i, line in enumerate(lines, start=1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:  # pragma: no cover - failure path
            raise AssertionError(f"line {i} is not valid JSON: {exc}") from exc
        assert isinstance(obj, dict), f"line {i} is not a JSON object"


def test_example_conforms_to_schema(references_dir: Path) -> None:
    schema = _schema(references_dir)
    props: dict = schema["properties"]
    required: set[str] = set(schema["required"])
    allowed: set[str] = set(props)

    def _type_ok(value: object, spec: dict) -> bool:
        t = spec.get("type")
        types = t if isinstance(t, list) else [t]
        ok = False
        for one in types:
            if one == "string" and isinstance(value, str):
                ok = True
            elif one == "null" and value is None:
                ok = True
            elif one == "integer" and isinstance(value, int) and not isinstance(
                value, bool
            ):
                ok = True
        return ok

    for i, line in enumerate(_example_lines(references_dir), start=1):
        obj = json.loads(line)
        keys = set(obj)
        missing = required - keys
        assert not missing, f"line {i} missing required keys: {missing}"
        extra = keys - allowed  # additionalProperties: false
        assert not extra, f"line {i} has keys outside the schema: {extra}"
        for key, value in obj.items():
            spec = props[key]
            assert _type_ok(value, spec), (
                f"line {i} field {key!r}={value!r} violates type {spec.get('type')}"
            )
            if "enum" in spec:
                assert value in spec["enum"], (
                    f"line {i} field {key!r}={value!r} not in enum {spec['enum']}"
                )
            if "pattern" in spec and isinstance(value, str):
                assert re.fullmatch(spec["pattern"], value), (
                    f"line {i} field {key!r}={value!r} fails pattern {spec['pattern']}"
                )
