#!/usr/bin/env python3
"""Build the zero-install release bundle for ublcheck.

Standard library only. No pip, no `build` module, no network access.
Produces, all relative to the repo root:

    ublcheck.pyz                        single-file zipapp (stdlib-only)
    dist/ublcheck-1.0.0-standalone.zip  pyz + README + LICENSE + RUNBOOK + INSTALL
    dist/SHA256SUMS                     sha256 of the standalone zip and the pyz

A fixed timestamp is pinned on every archive member so the build is
reproducible (the zip container uses the newest member mtime, so pinning every
member keeps the containers stable too).

Usage:  python3 scripts/build_release.py
"""
import hashlib
import os
import shutil
import sys
import zipapp
import zipfile

# --- fixed, reproducible member timestamp (2010-01-01T00:00:00Z) ----------
FIXED_DATE = (2010, 1, 1, 0, 0, 0)

VERSION = "1.0.0"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(REPO_ROOT, "dist")
BUILD_STAGE = os.path.join(REPO_ROOT, "build_zipapp")

# Files that ship inside the standalone zip, in order.
BUNDLE_FILES = ["README.md", "LICENSE", "RUNBOOK.md", "INSTALL.md"]


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_pyz():
    """Build ublcheck.pyz via `python -m zipapp` from a staging dir."""
    os.makedirs(BUILD_STAGE, exist_ok=True)
    stage_main = os.path.join(BUILD_STAGE, "__main__.py")
    with open(os.path.join(REPO_ROOT, "ublcheck.py"), "r", encoding="utf-8") as fh:
        source = fh.read()
    with open(stage_main, "w", encoding="utf-8") as fh:
        fh.write(source)

    out = os.path.join(REPO_ROOT, "ublcheck.pyz")
    if os.path.exists(out):
        os.remove(out)
    # -p sets the shebang AND the executable bit; compressed keeps it small.
    zipapp.create_archive(
        BUILD_STAGE,
        target=out,
        interpreter="/usr/bin/env python3",
        compressed=True,
    )

    # zipapp prepends the shebang OUTSIDE the zip container. Re-reading and
    # rewriting the archive with pinned timestamps would drop that prefix, so
    # capture it, pin the members, then restore the shebang prefix.
    with open(out, "rb") as fh:
        head = fh.read(2)
    if head != b"#!":
        raise SystemExit("ERROR: zipapp did not emit a shebang")
    with open(out, "rb") as fh:
        data = fh.read()
    nl = data.index(b"\n")
    shebang = data[:nl + 1]
    payload = data[nl + 1:]

    with zipfile.ZipFile(out, "r") as src:
        blobs = [(i, src.read(i.filename)) for i in src.infolist()]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info, blob in blobs:
            new = zipfile.ZipInfo(info.filename, date_time=FIXED_DATE)
            new.compress_type = zipfile.ZIP_DEFLATED
            new.external_attr = info.external_attr
            dst.writestr(new, blob)
    with open(out, "rb") as fh:
        payload = fh.read()
    with open(out, "wb") as fh:
        fh.write(shebang)
        fh.write(payload)
    os.chmod(out, 0o755)

    # Sanity: shebang must be the first line, and the executable bit must be set.
    with open(out, "rb") as fh:
        if fh.read(2) != b"#!":
            raise SystemExit("ERROR: ublcheck.pyz does not start with a shebang")
    if not os.access(out, os.X_OK):
        raise SystemExit("ERROR: ublcheck.pyz is not executable")
    return out


def build_standalone(pyz_path):
    """Assemble dist/ublcheck-1.0.0-standalone.zip with all bundle members."""
    os.makedirs(DIST, exist_ok=True)
    target = os.path.join(DIST, "ublcheck-%s-standalone.zip" % VERSION)
    if os.path.exists(target):
        os.remove(target)

    # (archive_name, source_path, external_attr) triples.
    members = [("ublcheck.pyz", pyz_path, 0o755 << 16)]
    for name in BUNDLE_FILES:
        src = os.path.join(REPO_ROOT, name)
        if not os.path.isfile(src):
            raise SystemExit("ERROR: required bundle file missing: %s" % name)
        members.append((name, src, 0o644 << 16))

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, src, mode in members:
            with open(src, "rb") as fh:
                data = fh.read()
            info = zipfile.ZipInfo(arcname, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = mode
            zf.writestr(info, data)
    return target


def stage_pyz_into_dist(pyz_path):
    """Copy the freshly built pyz next to SHA256SUMS so `sha256sum -c` works."""
    os.makedirs(DIST, exist_ok=True)
    dest = os.path.join(DIST, "ublcheck.pyz")
    shutil.copyfile(pyz_path, dest)
    os.chmod(dest, 0o755)
    return dest


def write_sha256sums(pyz_path, standalone_path):
    lines = [
        "%s  %s" % (sha256_of(pyz_path), os.path.basename(pyz_path)),
        "%s  %s" % (sha256_of(standalone_path), os.path.basename(standalone_path)),
    ]
    target = os.path.join(DIST, "SHA256SUMS")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return target


def main():
    print("repo root: %s" % REPO_ROOT)
    pyz = build_pyz()
    print("built %s (%d bytes)" % (os.path.relpath(pyz, REPO_ROOT), os.path.getsize(pyz)))
    standalone = build_standalone(pyz)
    print("built %s (%d bytes)" % (os.path.relpath(standalone, REPO_ROOT), os.path.getsize(standalone)))
    dist_pyz = stage_pyz_into_dist(pyz)
    print("staged %s" % os.path.relpath(dist_pyz, REPO_ROOT))
    sums = write_sha256sums(dist_pyz, standalone)
    print("wrote %s" % os.path.relpath(sums, REPO_ROOT))
    print("--- SHA256SUMS ---")
    sys.stdout.write(open(sums, "r", encoding="utf-8").read())
    return 0


if __name__ == "__main__":
    sys.exit(main())
