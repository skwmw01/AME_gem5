#!/usr/bin/env python3
"""Install the prebuilt AME LLVM archive pinned by this repository.

Downloads are verified before extraction. --direct ignores proxy environment
variables; --archive permits an already downloaded, checksum-matching archive.
"""
import argparse
import hashlib
import shutil
import tarfile
import urllib.request
from pathlib import Path

COMMIT = "22c930a6825636cfeb0c3db676d3cf8b57375cfa"
BASE = f"https://raw.githubusercontent.com/OpenXiangShan/AME_llvm/{COMMIT}"
BLOBS = {
    "ame_toolchain.tar.gz.part000": "b9c2c8d7adebd10858c7ec7561633991315beba4",
    "ame_toolchain.tar.gz.part001": "cff2123c18fbf163479ed5e479134594c6ddaf7f",
}
CHECKSUMS = {
    "ame_toolchain.tar.gz": "b789a3addd548e3820d94704f21193f64a6ce8a0d8496bc9f075181a37cf9882",
    "ame_toolchain.tar.gz.part000": "3033b41399e8650b2a580b034a040354fb5895d77369a6b3520490db3bcc5c56",
    "ame_toolchain.tar.gz.part001": "2c1467d7fecfc5167d9c4bf12e88e5affba4e51ea4803b3f27ad5d3fb4d7a2e1",
}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--dest", type=Path, default=root / "toolchain/install")
    parser.add_argument("--cache", type=Path,
                        default=root / "example_rvv1.0/build/performance/toolchain-download")
    args = parser.parse_args()
    marker = args.dest / ".benchmark_archive_sha256"
    if marker.exists() and marker.read_text().strip() == CHECKSUMS["ame_toolchain.tar.gz"]:
        if (args.dest / "bin/clang").exists():
            print(f"[PASS] pinned AME toolchain already installed: {args.dest}")
            return
    if args.dest.exists() and any(args.dest.iterdir()):
        parser.error(f"refusing to replace nonempty toolchain directory: {args.dest}")
    args.cache.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}) if args.direct else urllib.request.ProxyHandler())
    archive = args.archive
    if archive is None:
        parts = []
        for name in list(CHECKSUMS)[1:]:
            part = args.cache / name
            if not part.exists() or digest(part) != CHECKSUMS[name]:
                temporary = part.with_suffix(part.suffix + ".download")
                print(f"Downloading {name}", flush=True)
                url = "https://api.github.com/repos/OpenXiangShan/AME_llvm/git/blobs/" + BLOBS[name]
                request = urllib.request.Request(url, headers={
                    "Accept": "application/vnd.github.raw+json",
                    "User-Agent": "AME-gem5-performance-benchmark",
                })
                with opener.open(request, timeout=120) as source:
                    with temporary.open("wb") as output:
                        shutil.copyfileobj(source, output)
                if digest(temporary) != CHECKSUMS[name]:
                    raise RuntimeError(f"SHA256 mismatch: {name}")
                temporary.replace(part)
            parts.append(part)
        archive = args.cache / "ame_toolchain.tar.gz"
        with archive.open("wb") as output:
            for part in parts:
                with part.open("rb") as source:
                    shutil.copyfileobj(source, output)
    if digest(archive) != CHECKSUMS["ame_toolchain.tar.gz"]:
        raise RuntimeError("AME toolchain archive SHA256 mismatch")
    args.dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar:
        tar.extractall(args.dest, filter="data")
    marker.write_text(CHECKSUMS["ame_toolchain.tar.gz"] + "\n")
    (args.dest / ".ame_toolchain_mode").write_text("packaged\n")
    print(f"[PASS] installed verified AME toolchain to {args.dest}")


if __name__ == "__main__":
    main()
