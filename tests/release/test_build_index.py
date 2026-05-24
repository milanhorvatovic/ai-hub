"""Unit tests for the catalog index.json generator in `build_bundles.py`.

Loaded from its file path like the bundle-builder tests; exercises the manifest
the future marketplace consumes against the real repository at `HEAD`.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / ".github" / "scripts" / "build_bundles.py"
_REPO = "milanhorvatovic/ai-hub"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_bundles", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = _load_module()
_SKILL = "git-toolkit"


def _entry(tmp_path: Path, repo: str | None = _REPO) -> dict:
    bundle = builder.build_skill_bundle(_REPO_ROOT, "HEAD", _SKILL, tmp_path)
    return builder.bundle_entry(_REPO_ROOT, "HEAD", _SKILL, bundle, repo)


def test_entry_carries_locate_and_verify_fields(tmp_path: Path) -> None:
    bundle = builder.build_skill_bundle(_REPO_ROOT, "HEAD", _SKILL, tmp_path)
    version = builder.skill_version(_REPO_ROOT, "HEAD", _SKILL)
    entry = builder.bundle_entry(_REPO_ROOT, "HEAD", _SKILL, bundle, _REPO)
    assert entry["name"] == _SKILL
    assert entry["version"] == version
    assert entry["tag"] == f"{_SKILL}-v{version}"
    assert entry["bundle"] == bundle.name
    assert entry["sha256"] == hashlib.sha256(bundle.read_bytes()).hexdigest()


def test_entry_url_targets_the_per_skill_release(tmp_path: Path) -> None:
    entry = _entry(tmp_path)
    assert entry["url"] == (
        f"https://github.com/{_REPO}/releases/download/{entry['tag']}/{entry['bundle']}"
    )


def test_entry_url_omitted_without_repo(tmp_path: Path) -> None:
    entry = _entry(tmp_path, repo=None)
    assert "url" not in entry


def test_index_has_schema_version_and_repository(tmp_path: Path) -> None:
    index = builder.build_index([_entry(tmp_path)], repo=_REPO)
    assert index["schemaVersion"] == builder.INDEX_SCHEMA_VERSION
    assert index["repository"] == _REPO


def test_index_catalog_and_timestamp_are_optional(tmp_path: Path) -> None:
    bare = builder.build_index([_entry(tmp_path)], repo=_REPO)
    assert "catalog" not in bare
    assert "generatedAt" not in bare
    stamped = builder.build_index(
        [_entry(tmp_path)], repo=_REPO, catalog="v2026.05.0", generated_at="2026-05-24T00:00:00Z"
    )
    assert stamped["catalog"] == "v2026.05.0"
    assert stamped["generatedAt"] == "2026-05-24T00:00:00Z"


def test_index_sorts_skills_by_name(tmp_path: Path) -> None:
    skills = builder._resolve_skills(_REPO_ROOT, "HEAD", [])
    entries = []
    for skill in reversed(skills):  # feed them out of order
        bundle = builder.build_skill_bundle(_REPO_ROOT, "HEAD", skill, tmp_path)
        entries.append(builder.bundle_entry(_REPO_ROOT, "HEAD", skill, bundle, _REPO))
    index = builder.build_index(entries, repo=_REPO)
    names = [entry["name"] for entry in index["skills"]]
    assert names == sorted(names)


def test_index_is_omitted_when_timestamp_absent_so_it_stays_reproducible(tmp_path: Path) -> None:
    a = builder.build_index([_entry(tmp_path / "a")], repo=_REPO)
    b = builder.build_index([_entry(tmp_path / "b")], repo=_REPO)
    assert json.dumps(a) == json.dumps(b)


def test_write_index_round_trips_with_trailing_newline(tmp_path: Path) -> None:
    index = builder.build_index([_entry(tmp_path)], repo=_REPO, catalog="v2026.05.0")
    out = builder.write_index(index, tmp_path / "index.json")
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text) == index


def test_main_writes_index_when_requested(tmp_path: Path) -> None:
    rc = builder.main(
        [
            "--ref",
            "HEAD",
            "--out",
            str(tmp_path),
            "--skill",
            _SKILL,
            "--index",
            "--repo",
            _REPO,
            "--catalog",
            "v2026.05.0",
        ]
    )
    assert rc == 0
    index = json.loads((tmp_path / "index.json").read_text())
    assert index["catalog"] == "v2026.05.0"
    assert [entry["name"] for entry in index["skills"]] == [_SKILL]
    assert (tmp_path / "SHA256SUMS").is_file()


def test_main_skips_index_by_default(tmp_path: Path) -> None:
    rc = builder.main(["--ref", "HEAD", "--out", str(tmp_path), "--skill", _SKILL])
    assert rc == 0
    assert not (tmp_path / "index.json").exists()
