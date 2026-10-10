#!/usr/bin/env python3
"""Create a clean, commit-pinned CarPaly source ZIP for a release."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import PurePosixPath
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_MARKDOWN = {"CarPaly/README.md"}
BLOCKED_SUFFIXES = {
    ".aab",
    ".apk",
    ".cer",
    ".crt",
    ".der",
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".p7b",
    ".pem",
    ".pfx",
    ".pk8",
}
BLOCKED_PARTS = {".private", ".gradle", ".kotlin", "build", "captures"}


def archive_timestamp(epoch: int) -> tuple[int, int, int, int, int, int]:
    # ZIP timestamps start at 1980 and have two-second precision.
    value = datetime.fromtimestamp(max(epoch, 315532800), timezone.utc)
    return (value.year, value.month, value.day, value.hour, value.minute, value.second // 2 * 2)


def safe_member_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError(f"Unsafe source archive path: {name}")
    return path


def build_archive(ref: str, output: Path) -> tuple[int, int]:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing archive: {output}")
    commit = subprocess.run(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryFile() as tar_file:
        subprocess.run(
            ["git", "archive", "--format=tar", "--prefix=CarPaly/", commit],
            cwd=ROOT,
            check=True,
            stdout=tar_file,
        )
        tar_file.seek(0)
        with tarfile.open(fileobj=tar_file, mode="r:") as source:
            temporary_path: Path | None = None
            included: set[str] = set()
            try:
                with tempfile.NamedTemporaryFile(
                    prefix=f".{output.name}.", suffix=".tmp", dir=output.parent, delete=False
                ) as temporary:
                    temporary_path = Path(temporary.name)
                with ZipFile(temporary_path, mode="w", compression=ZIP_DEFLATED, compresslevel=9) as zipped:
                    for member in sorted(source.getmembers(), key=lambda item: item.name):
                        if member.isdir():
                            continue
                        path = safe_member_name(member.name)
                        if BLOCKED_PARTS.intersection(path.parts):
                            raise ValueError(f"Private/build path found in source commit: {member.name}")
                        if path.suffix.lower() in BLOCKED_SUFFIXES:
                            raise ValueError(f"Credential or installable artifact found in source commit: {member.name}")
                        if path.suffix.lower() == ".md" and member.name not in ALLOWED_MARKDOWN:
                            continue
                        # A ZIP symlink can escape the extraction root even when its
                        # member name is safe. Public source archives do not need
                        # symlinks, so reject them rather than normalizing targets.
                        if member.issym():
                            raise ValueError(f"Symbolic links are forbidden in source archives: {member.name}")
                        if not member.isfile():
                            raise ValueError(f"Unsupported source archive entry: {member.name}")
                        if member.name in included:
                            raise ValueError(f"Duplicate source archive path: {member.name}")

                        info = ZipInfo(member.name, archive_timestamp(member.mtime))
                        info.create_system = 3
                        info.external_attr = (stat.S_IFREG | (member.mode & 0o777)) << 16
                        stream = source.extractfile(member)
                        if stream is None:
                            raise ValueError(f"Could not read source archive entry: {member.name}")
                        with stream:
                            payload = stream.read()
                        zipped.writestr(info, payload)
                        included.add(member.name)

                required = {"CarPaly/README.md", "CarPaly/LICENSE"}
                if not required.issubset(included):
                    raise ValueError("Source archive must retain the public README and project license")
                with ZipFile(temporary_path, mode="r") as zipped:
                    if zipped.testzip() is not None:
                        raise ValueError("Source ZIP integrity check failed")
                os.replace(temporary_path, output)
                temporary_path = None
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)

    return len(included), output.stat().st_size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", required=True, help="Release tag or commit to package")
    parser.add_argument("--output", required=True, type=Path, help="New output ZIP path")
    args = parser.parse_args()
    count, size = build_archive(args.ref, args.output)
    print(f"Created source archive from {args.ref}: {count} files, {size} bytes")


if __name__ == "__main__":
    main()
