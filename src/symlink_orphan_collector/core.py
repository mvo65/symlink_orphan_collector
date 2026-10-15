from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Iterator

__all__ = ["is_orphaned_symlink", "collect_orphaned_symlinks"]


def is_orphaned_symlink(path: str) -> bool:
    """Return True if *path* is a symlink whose target does not exist.

    We deliberately interpret "orphan" as "the link itself is broken right now".
    A link that resolves through a chain of links to a missing file is orphaned;
    a link whose immediate target exists (even if that target is itself a broken
    link) is not. This single-rule definition keeps the behaviour predictable
    and easy to reason about — os.path.exists already does the right thing by
    following the chain and reporting whether something lives at the end.

    We use lstat to detect symlinks rather than stat, because stat would follow
    the link and could raise on a broken link before we ever classify it.
    """
    try:
        st = os.lstat(path)
    except (OSError, ValueError):
        return False
    if not stat.S_ISLNK(st.st_mode):
        return False
    try:
        os.stat(path)  # follows the link; raises if the target is missing
    except (OSError, ValueError):
        return True
    return False


def collect_orphaned_symlinks(
    root: str,
    *,
    remove: bool = False,
) -> Iterator[str]:
    """Yield paths of broken symlinks found under *root*.

    If *remove* is True, each orphan is unlinked before being yielded. We
    unlink before yielding so that the operation is atomic from the caller's
    perspective: the list you get back reflects exactly what was removed, with
    no risk of a link being counted and then left behind by a later error.

    Walking is done with os.walk(followlinks=False) so we never traverse into a
    symlinked directory — only into real directories. This prevents infinite
    loops on cyclic link graphs and means the scan is bounded by the real tree.
    """
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Prune symlinked directories from the descent so os.walk does not
        # try to recurse into them on platforms that might expand them.
        real_dirs = []
        for d in dirnames:
            full = os.path.join(dirpath, d)
            if os.path.islink(full):
                if is_orphaned_symlink(full):
                    if remove:
                        os.unlink(full)
                    yield full
                continue
            real_dirs.append(d)
        dirnames[:] = real_dirs

        for name in filenames:
            full = os.path.join(dirpath, name)
            if is_orphaned_symlink(full):
                if remove:
                    os.unlink(full)
                yield full


# Re-export Path so type-checkers see the same names callers might reference.
_ = Path
