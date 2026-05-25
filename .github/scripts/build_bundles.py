#!/usr/bin/env python3
"""Build reproducible per-skill release bundles from tracked content.

A bundle is a zip of one `skills/<name>/` subtree plus the repository `LICENSE`,
laid out under a top-level `<name>/` directory so a consumer unzips it straight
into their skills directory. The bytes are deterministic: same commit in, same
zip out. That is what makes the SHA256SUMS and the provenance attestation
meaningful — a verifier can rebuild from the tag and get an identical
artifact.

Determinism comes from sourcing every entry through `git archive` at a fixed
commit-ish (so file content and order are fixed), then writing the zip with
pinned per-entry metadata (mtime = the commit time, mode, and create-system)
and no compression (`ZIP_STORED`). Storing entries uncompressed is deliberate:
DEFLATE output can differ byte-for-byte across zlib/Python builds even for
identical input, which would break a verifier rebuilding from the tag; stored
entries depend only on content and the pinned metadata, not the platform's zlib.
The skill subtree is already clean of repo-development cruft (the distribution-
hygiene guard enforces that), so the archive ships only distributable content.

Stdlib-only, in the same spirit as the other release scripts; loaded from its
file path by the tests under `tests/release/`.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path

# Bumped only on a breaking change to the index.json shape; additive fields keep version 1.
INDEX_SCHEMA_VERSION = 1

# Matches `metadata.version` in a SKILL.md, mirroring tests/release/test_manifest_sync.py.
_VERSION = re.compile(r'^\s+version:\s*"([^"]+)"', flags=re.MULTILINE)

# Fixed POSIX file mode for every entry (0o644), in the high 16 bits of external_attr.
_FILE_MODE = (0o644 & 0xFFFF) << 16
# create_system 3 = Unix; pinned so the zip header does not vary by build host.
_UNIX = 3
# Zip cannot represent dates before 1980; commit times are well after, but clamp defensively.
_MIN_ZIP_YEAR = 1980


def _git(repo_root: Path, *args: str) -> bytes:
    """Run a git command in `repo_root` and return its raw stdout."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
    )
    return result.stdout


def _commit_date_time(repo_root: Path, ref: str) -> tuple[int, int, int, int, int, int]:
    """Return the committer timestamp of `ref` as a zip `date_time` tuple (UTC)."""
    epoch = int(_git(repo_root, "show", "-s", "--format=%ct", ref).decode().strip())
    utc = time.gmtime(epoch)
    year = max(utc.tm_year, _MIN_ZIP_YEAR)
    return (year, utc.tm_mon, utc.tm_mday, utc.tm_hour, utc.tm_min, utc.tm_sec)


def skill_version(repo_root: Path, ref: str, skill: str) -> str:
    """Read `metadata.version` from `skills/<skill>/SKILL.md` at `ref`."""
    text = _git(repo_root, "show", f"{ref}:skills/{skill}/SKILL.md").decode("utf-8")
    match = _VERSION.search(text)
    if not match:
        raise ValueError(f"no metadata.version in skills/{skill}/SKILL.md at {ref}")
    return match.group(1)


def _skill_entries(repo_root: Path, ref: str, skill: str) -> list[tuple[str, bytes]]:
    """Return `(<skill>/<relpath>, content)` for each tracked file in the subtree.

    Sourced via `git archive` at `ref`, so it reflects exactly what is committed
    (not the working tree) and the `skills/` prefix is rewritten to the bundle's
    top-level `<skill>/` directory.
    """
    prefix = f"skills/{skill}/"
    tar_bytes = _git(repo_root, "archive", "--format=tar", ref, prefix.rstrip("/"))
    entries: list[tuple[str, bytes]] = []
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            if not member.name.startswith(prefix):
                raise ValueError(f"unexpected archive member {member.name!r}")
            extracted = tar.extractfile(member)
            assert extracted is not None  # isfile() guarantees a payload
            entries.append((f"{skill}/{member.name[len(prefix):]}", extracted.read()))
    if not entries:
        raise ValueError(f"no tracked files under {prefix} at {ref}")
    return entries


def _write_zip(entries: list[tuple[str, bytes]], date_time, out_path: Path) -> None:
    """Write `entries` to `out_path` as a byte-deterministic zip."""
    buffer = io.BytesIO()
    # ZIP_STORED (no compression) keeps the bytes independent of the zlib build, so a
    # verifier on any toolchain can rebuild an identical artifact from the same commit.
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=date_time)
            info.external_attr = _FILE_MODE
            info.create_system = _UNIX
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, content)
    out_path.write_bytes(buffer.getvalue())


def build_skill_bundle(
    repo_root: Path, ref: str, skill: str, out_dir: Path, *, version: str | None = None
) -> Path:
    """Build `<skill>-<version>.zip` (skill subtree + LICENSE) under `out_dir`.

    `version` may be supplied by a caller that already read it, to avoid re-reading
    `SKILL.md`; when omitted it is read here. Returns the path to the written bundle.
    """
    if version is None:
        version = skill_version(repo_root, ref, skill)
    entries = _skill_entries(repo_root, ref, skill)
    entries.append((f"{skill}/LICENSE", _git(repo_root, "show", f"{ref}:LICENSE")))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{skill}-{version}.zip"
    _write_zip(entries, _commit_date_time(repo_root, ref), out_path)
    return out_path


def write_sha256sums(
    bundles: list[Path], out_path: Path, *, digests: dict[Path, str] | None = None
) -> Path:
    """Write a coreutils-format `SHA256SUMS` over `bundles` (sorted by name).

    `digests` may supply precomputed `{path: hexdigest}` so a caller that already
    hashed the files isn't forced to re-read them; any missing entry is hashed here.
    """
    digests = digests or {}
    lines = []
    for bundle in sorted(bundles, key=lambda p: p.name):
        digest = digests.get(bundle) or hashlib.sha256(bundle.read_bytes()).hexdigest()
        # "<digest>  <name>": two spaces are sha256sum's text-mode separator (binary mode
        # uses " *"); `sha256sum -c` reads this form.
        lines.append(f"{digest}  {bundle.name}\n")
    out_path.write_text("".join(lines), encoding="utf-8")
    return out_path


def skill_tag(skill: str, version: str) -> str:
    """The per-skill release tag release-please cuts: `<skill>-v<version>`."""
    return f"{skill}-v{version}"


def bundle_entry(
    repo_root: Path,
    ref: str,
    skill: str,
    bundle: Path,
    repo: str | None,
    *,
    version: str | None = None,
    sha256: str | None = None,
) -> dict:
    """Build one `index.json` skill entry pointing at a built bundle.

    `repo` is `owner/name`; when given, a GitHub release download URL is added.
    The download target is the per-skill release tag, so the catalog (attached to
    the CalVer release) can point across to each skill's own release assets.
    `version` and `sha256` may be supplied by a caller that already computed them,
    to avoid re-reading `SKILL.md` and re-hashing the bundle; both default to None.
    """
    if version is None:
        version = skill_version(repo_root, ref, skill)
    tag = skill_tag(skill, version)
    entry = {
        "name": skill,
        "version": version,
        "tag": tag,
        "bundle": bundle.name,
        "sha256": sha256 or hashlib.sha256(bundle.read_bytes()).hexdigest(),
    }
    if repo:
        entry["url"] = f"https://github.com/{repo}/releases/download/{tag}/{bundle.name}"
    return entry


def build_index(
    entries: list[dict],
    *,
    repo: str | None = None,
    catalog: str | None = None,
    generated_at: str | None = None,
) -> dict:
    """Assemble the catalog manifest the marketplace will consume.

    Minimal and additive by design: a `schemaVersion` lets the shape grow without
    breaking consumers, so it carries only what is needed to locate and verify each
    bundle. `catalog` is the CalVer train coordinate; `generated_at` is optional so
    the manifest stays reproducible unless a timestamp is supplied.
    """
    index: dict = {"schemaVersion": INDEX_SCHEMA_VERSION}
    if repo:
        index["repository"] = repo
    if catalog:
        index["catalog"] = catalog
    if generated_at:
        index["generatedAt"] = generated_at
    index["skills"] = sorted(entries, key=lambda entry: entry["name"])
    return index


def write_index(index: dict, out_path: Path) -> Path:
    """Write `index` as pretty-printed JSON with a trailing newline."""
    out_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return out_path


def _resolve_skills(repo_root: Path, ref: str, requested: list[str]) -> list[str]:
    """Return the requested skills, or every tracked skill directory at `ref` when none given."""
    if requested:
        return sorted(requested)
    # -d lists only tree (directory) entries, so a stray file under skills/ is never
    # mistaken for a skill name.
    listing = _git(repo_root, "ls-tree", "-d", "--name-only", f"{ref}:skills").decode().splitlines()
    return sorted(name for name in listing if name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build reproducible skill release bundles.")
    parser.add_argument("--ref", default="HEAD", help="commit-ish to archive (default: HEAD)")
    parser.add_argument("--out", type=Path, default=Path("dist"), help="output directory")
    parser.add_argument(
        "--skill",
        action="append",
        default=[],
        dest="skills",
        help="skill to bundle; repeatable. Omit to bundle every skill at the ref.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root (default: inferred from this script's location)",
    )
    parser.add_argument("--index", action="store_true", help="also write a catalog index.json")
    parser.add_argument("--repo", help="`owner/name`, used for index.json download URLs")
    parser.add_argument("--catalog", help="CalVer train coordinate for index.json (e.g. v2026.05.0)")
    parser.add_argument("--generated-at", help="ISO-8601 timestamp to stamp into index.json")
    args = parser.parse_args(argv)

    skills = _resolve_skills(args.repo_root, args.ref, args.skills)
    # Read each skill's version and hash each bundle exactly once, then reuse those
    # values for the SHA256SUMS and (optionally) the index, instead of recomputing.
    records = []  # (skill, bundle, version, sha256)
    for skill in skills:
        version = skill_version(args.repo_root, args.ref, skill)
        bundle = build_skill_bundle(args.repo_root, args.ref, skill, args.out, version=version)
        digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
        records.append((skill, bundle, version, digest))

    sums = write_sha256sums(
        [bundle for _, bundle, _, _ in records],
        args.out / "SHA256SUMS",
        digests={bundle: digest for _, bundle, _, digest in records},
    )
    for _, bundle, _, _ in records:
        print(bundle)
    print(sums)
    if args.index:
        entries = [
            bundle_entry(
                args.repo_root, args.ref, skill, bundle, args.repo, version=version, sha256=digest
            )
            for skill, bundle, version, digest in records
        ]
        index = build_index(
            entries, repo=args.repo, catalog=args.catalog, generated_at=args.generated_at
        )
        print(write_index(index, args.out / "index.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
