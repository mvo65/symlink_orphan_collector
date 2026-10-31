# symlink_orphan_collector

Finds and optionally removes symlinks whose targets no longer exist, walking a directory tree without following symlinked directories.

```python
from symlink_orphan_collector import collect_orphaned_symlinks, is_orphaned_symlink

for orphan in collect_orphaned_symlinks("/var/data/migrated"):
    print(orphan)

# To unlink each orphan as it is found:
removed = list(collect_orphaned_symlinks("/var/data/migrated", remove=True))

# Check a single path:
is_orphaned_symlink("/var/data/migrated/old_link")
```

## Why this exists

After a migration or cleanup pass, symlinks that pointed at now-deleted files linger indefinitely. This library walks a tree, identifies links whose targets are unreachable, and can remove them in one pass.

The trade-off: "orphan" is defined as the link resolving to nothing right now. We do not track whether a target existed in the past. If a link points through another link to a missing file, it is orphaned; if its immediate target exists, it is not. One rule, no ambiguity.

## Edge case to know about

The scan does not descend into symlinked directories (`followlinks=False`). This prevents infinite loops on cyclic link graphs and bounds the scan to the real directory tree. A symlink to a missing directory is reported as an orphan like any other broken link.

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

## Limitations

Values are coerced to floats, so very large integers lose precision. If you need
exact integer aggregates over a window, this is the wrong tool.

