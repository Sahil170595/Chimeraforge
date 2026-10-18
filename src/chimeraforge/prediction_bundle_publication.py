"""Exclusive destination ownership and manifest-last readiness, without directory replacement."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
import stat

from chimeraforge.plan_bundle import _plain_path, _read
from chimeraforge.prediction_bundle_inputs import fail

logger = logging.getLogger(__name__)
PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600


def _identity(path: Path, *, directory: bool) -> tuple[int, int]:
    info = path.lstat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)) or getattr(
        info, "st_file_attributes", 0
    ) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
        fail(retained=True)
    return info.st_dev, info.st_ino


@dataclass
class _Owner:
    root: Path
    created: bool = False
    identity: tuple[int, int] | None = None
    directories: dict[str, tuple[int, int]] = field(default_factory=dict)
    files: dict[str, tuple[tuple[int, int], bytes] | None] = field(default_factory=dict)

    def check(self) -> None:
        if self.identity is None or _identity(self.root, directory=True) != self.identity:
            fail(retained=True)
        for logical, identity in self.directories.items():
            if _identity(self.root / logical, directory=True) != identity:
                fail(retained=True)


def _write_member(owner: _Owner, logical: str, raw: bytes) -> None:
    owner.check()
    path = owner.root / logical
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        PRIVATE_FILE_MODE,
    )
    owner.files[logical] = None
    with os.fdopen(descriptor, "wb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            fail(retained=True)
        if stream.write(raw) != len(raw):
            fail(retained=True)
        stream.flush()
        after = os.fstat(stream.fileno())
    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino) or after.st_size != len(raw):
        fail(retained=True)
    owner.files[logical] = ((after.st_dev, after.st_ino), raw)
    owner.check()


def _verify_owned(owner: _Owner) -> None:
    owner.check()
    expected = {*owner.directories, *(path for path in owner.files if "/" not in path)}
    if {entry.name for entry in owner.root.iterdir()} != expected:
        fail(retained=True)
    for logical in owner.directories:
        if {entry.name for entry in (owner.root / logical).iterdir()} != {
            path.split("/")[1] for path in owner.files if path.startswith(logical + "/")
        }:
            fail(retained=True)
    for logical, record in owner.files.items():
        path = owner.root / logical
        if (
            record is None
            or _identity(path, directory=False) != record[0]
            or _read(path, len(record[1])) != record[1]
        ):
            fail(retained=True)


def _cleanup(owner: _Owner) -> bool:
    from chimeraforge.api import PlanError

    if owner.identity is None:
        return not owner.created
    try:
        _verify_owned(owner)
        for logical in reversed(tuple(owner.files)):
            owner.check()
            record = owner.files[logical]
            path = owner.root / logical
            if (
                record is None
                or _identity(path, directory=False) != record[0]
                or _read(path, len(record[1])) != record[1]
            ):
                return False
            path.unlink()
        for logical in reversed(owner.directories):
            if _identity(owner.root / logical, directory=True) != owner.directories[logical]:
                return False
            (owner.root / logical).rmdir()
        if _identity(owner.root, directory=True) != owner.identity:
            return False
        owner.root.rmdir()
        return True
    except (OSError, PlanError):
        logger.warning("prediction bundle owned cleanup could not verify unchanged destination")
        return False


def publish(root: Path, members: tuple[tuple[str, bytes], ...], manifest_raw: bytes) -> None:
    _plain_path(root)
    if not root.parent.is_dir():
        fail()
    owner = _Owner(root)
    try:
        root.mkdir(mode=PRIVATE_DIRECTORY_MODE)
        owner.created = True
        owner.identity = _identity(root, directory=True)
        for name in ("plan", "receipts"):
            owner.check()
            (root / name).mkdir(mode=PRIVATE_DIRECTORY_MODE)
            owner.directories[name] = _identity(root / name, directory=True)
        for logical, raw in members:
            _write_member(owner, logical, raw)
        _verify_owned(owner)
        _write_member(owner, "manifest.json", manifest_raw)
        _verify_owned(owner)
    except BaseException as exc:
        cleaned = _cleanup(owner)
        if not cleaned:
            logger.warning("prediction bundle incomplete destination retained")
            if isinstance(exc, Exception):
                fail(retained=True)
        raise
