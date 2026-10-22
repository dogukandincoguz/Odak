"""Review a Git commit and calculate the installer's ZIP-independent source hash."""
from __future__ import annotations

import argparse
import hashlib
import io
import subprocess
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def digest_entries(entries: list[tuple[str, bytes]]) -> str:
    # Match .NET StringComparer.Ordinal, including names outside the BMP.
    entries = sorted(entries, key=lambda entry: entry[0].encode("utf-16-be"))
    manifest = "".join(name + "\0" + hashlib.sha256(data).hexdigest() + "\n"
                       for name, data in entries)
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest()


def zip_digest(path: Path) -> str:
    """For local test archives; this calculation does not establish trust."""
    with zipfile.ZipFile(path) as archive:
        return digest_entries([(entry.filename.split("/", 1)[1], archive.read(entry))
                               for entry in archive.infolist() if not entry.is_dir()])


def commit_digest(revision: str) -> str:
    git = ["git", "-c", "safe.directory=" + PROJECT.as_posix(), "-C", str(PROJECT)]
    tree = subprocess.check_output(git + ["ls-tree", "-r", "-z", "--full-tree", revision])
    objects = []
    for record in tree.split(b"\0"):
        if not record:
            continue
        metadata, name = record.split(b"\t", 1)
        mode, kind, identity = metadata.split()
        if mode not in (b"100644", b"100755") or kind != b"blob":
            raise ValueError("Only regular Git files can be published.")
        objects.append((name.decode("utf-8"), identity))
    if not objects:
        raise ValueError("The commit contains no files.")
    result = subprocess.run(git + ["cat-file", "--batch"],
                            input=b"".join(identity + b"\n" for _, identity in objects),
                            capture_output=True, check=True)
    stream = io.BytesIO(result.stdout)
    entries = []
    for name, identity in objects:
        object_id, kind, length = stream.readline().split()
        if object_id != identity or kind != b"blob":
            raise ValueError("Unexpected Git object.")
        content = stream.read(int(length))
        if len(content) != int(length) or stream.read(1) != b"\n":
            raise ValueError("Incomplete Git object.")
        entries.append((name, content))
    return digest_entries(entries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("commit", help="An already reviewed local Git commit")
    args = parser.parse_args()
    print(commit_digest(args.commit))
