#!/usr/bin/env python3
"""Reject the eMudhra incident's root certificates in PEM trust stores.

This checks certificate contents, including OpenSSL's lazily loaded CA directory.
It does not model native OS certificate revocation or arbitrary custom clients.
Incident fingerprints: https://emudhra.we-have-a-problem.com/roots.json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import os
from pathlib import Path
import re
import ssl
import sys


BLOCKED_ROOTS = {
    "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b": "emSign ECC Root CA - G3",
    "d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4": "AAA Certificate Services",
    "7dd78d5f4f13459a83dff9abbba62edbaf6f2d102bf257fd712f4d9f2746ed8d": "emSign Root TLS CA - G3",
    "f2edaaff3d9b701fb4d14c9f285f8c0bad90fc3bcc1fa07d47f4718edaba34a5": "emSign Root CS CA - G3",
}


def check_bundle(path: Path) -> None:
    """Raise on an unreadable, empty, malformed, or affected CA bundle."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=str(path))
    certificates = context.get_ca_certs(binary_form=True)
    if not certificates:
        raise ValueError("no CA certificates")
    blocked = {
        BLOCKED_ROOTS[fingerprint]
        for certificate in certificates
        if (fingerprint := hashlib.sha256(certificate).hexdigest()) in BLOCKED_ROOTS
    }
    if blocked:
        raise ValueError("affected roots: " + ", ".join(sorted(blocked)))


def system_paths() -> list[Path]:
    """Inspect both the effective OpenSSL CA file and hashed directory entries."""
    defaults = ssl.get_default_verify_paths()
    paths = [Path(defaults.cafile)] if defaults.cafile else []
    # get_default_verify_paths() can report None for a colon-separated
    # SSL_CERT_DIR even though OpenSSL consumes each directory in that list.
    capath = os.environ.get(defaults.openssl_capath_env, defaults.capath)
    if capath:
        for directory in filter(None, capath.split(os.pathsep)):
            paths.extend(
                path
                for path in Path(directory).iterdir()
                if re.fullmatch(r"[0-9a-fA-F]{8}\.[0-9]+", path.name) and path.is_file()
            )
    if not paths:
        raise ValueError("no effective OpenSSL PEM CA store found")
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundles", nargs="*", type=Path)
    parser.add_argument("--system", action="store_true", help="check effective OpenSSL PEM stores")
    parser.add_argument("--python", action="store_true", help="check certifi and pip's separate vendored bundle")
    args = parser.parse_args(argv)
    if not (args.bundles or args.system or args.python):
        parser.error("select --system, --python, or explicit PEM bundle paths")
    try:
        paths = list(args.bundles)
        if args.system:
            paths.extend(system_paths())
        if args.python:
            for name in ("certifi", "pip._vendor.certifi"):
                paths.append(Path(importlib.import_module(name).where()))
        paths = list(dict.fromkeys(path.resolve() for path in paths))
        errors = []
        for path in paths:
            try:
                check_bundle(path)
            except (OSError, ValueError, ssl.SSLError) as exc:
                errors.append(f"{path}: {exc}")
        if errors:
            raise ValueError("\n".join(errors))
    except (ImportError, OSError, ValueError, ssl.SSLError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Validated {len(paths)} CA bundle file(s): no eMudhra incident roots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
