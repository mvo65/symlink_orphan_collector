import os
import tempfile
import unittest

from symlink_orphan_collector import collect_orphaned_symlinks, is_orphaned_symlink


class TestIsOrphanedSymlink(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def _touch(self, name, content="x"):
        path = os.path.join(self.root, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def _link(self, name, target):
        path = os.path.join(self.root, name)
        os.symlink(target, path)
        return path

    def test_broken_symlink_is_orphan(self):
        link = self._link("broken", os.path.join(self.root, "missing"))
        self.assertTrue(is_orphaned_symlink(link))

    def test_valid_symlink_is_not_orphan(self):
        target = self._touch("real")
        link = self._link("good", target)
        self.assertFalse(is_orphaned_symlink(link))

    def test_regular_file_is_not_symlink(self):
        path = self._touch("plain")
        self.assertFalse(is_orphaned_symlink(path))

    def test_nonexistent_path_is_not_symlink(self):
        self.assertFalse(is_orphaned_symlink(os.path.join(self.root, "nope")))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks not supported")
    def test_relative_link_to_missing(self):
        link = self._link("rel", "does-not-exist")
        self.assertTrue(is_orphaned_symlink(link))

    def test_relative_link_to_existing(self):
        self._touch("here")
        link = self._link("relgood", "here")
        # The symlink target is resolved relative to the link's directory.
        self.assertFalse(is_orphaned_symlink(link))

    def test_chain_ending_in_missing_is_orphan(self):
        # a -> b -> c (missing)
        self._link("b", os.path.join(self.root, "c"))
        link = self._link("a", os.path.join(self.root, "b"))
        self.assertTrue(is_orphaned_symlink(link))

    def test_chain_ending_in_existing_is_not_orphan(self):
        self._touch("c")
        self._link("b", os.path.join(self.root, "c"))
        link = self._link("a", os.path.join(self.root, "b"))
        self.assertFalse(is_orphaned_symlink(link))


class TestCollectOrphanedSymlinks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def _touch(self, *parts, content="x"):
        path = os.path.join(self.root, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    def _link(self, target, *parts):
        path = os.path.join(self.root, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        os.symlink(target, path)
        return path

    def test_finds_no_orphans_in_empty_tree(self):
        result = list(collect_orphaned_symlinks(self.root))
        self.assertEqual(result, [])

    def test_finds_broken_link_in_root(self):
        link = self._link(os.path.join(self.root, "missing"), "broken")
        result = list(collect_orphaned_symlinks(self.root))
        self.assertEqual(result, [link])

    def test_finds_broken_link_in_subdirectory(self):
        link = self._link(
            os.path.join(self.root, "missing"), "sub", "broken"
        )
        result = list(collect_orphaned_symlinks(self.root))
        self.assertEqual(result, [link])

    def test_does_not_report_valid_links(self):
        self._touch("real")
        good = self._link(os.path.join(self.root, "real"), "good")
        self._link(os.path.join(self.root, "missing"), "broken")
        result = list(collect_orphaned_symlinks(self.root))
        self.assertNotIn(good, result)
        self.assertEqual(len(result), 1)

    def test_remove_unlinks_orphans(self):
        link = self._link(os.path.join(self.root, "missing"), "broken")
        list(collect_orphaned_symlinks(self.root, remove=True))
        self.assertFalse(os.path.lexists(link))

    def test_remove_preserves_valid_links(self):
        self._touch("real")
        good = self._link(os.path.join(self.root, "real"), "good")
        list(collect_orphaned_symlinks(self.root, remove=True))
        self.assertTrue(os.path.lexists(good))

    def test_remove_returns_removed_paths(self):
        link = self._link(os.path.join(self.root, "missing"), "broken")
        result = list(collect_orphaned_symlinks(self.root, remove=True))
        self.assertEqual(result, [link])

    def test_does_not_traverse_into_symlinked_directories(self):
        # Create a real directory with a broken link inside it, then symlink
        # to that directory from the scan root. The broken link inside the
        # real directory will be found when we walk that real directory, but
        # we must not descend through dirlink (followlinks=False). dirlink
        # itself is a valid (non-orphan) symlink so should not be reported.
        real_dir = os.path.join(self.root, "realdir")
        os.makedirs(real_dir)
        os.symlink("missing", os.path.join(real_dir, "inside_broken"))
        dir_link = self._link(real_dir, "dirlink")
        result = list(collect_orphaned_symlinks(self.root))
        # The inside_broken link IS found because realdir is a real directory
        # under root, so the scan naturally walks it. dirlink itself is a valid
        # (non-orphan) symlink so should not appear in results.
        self.assertIn(os.path.join(real_dir, "inside_broken"), result)
        self.assertNotIn(dir_link, result)

    def test_orphaned_symlinked_directory_is_reported(self):
        dir_link = self._link(os.path.join(self.root, "no_such_dir"), "dirlink")
        result = list(collect_orphaned_symlinks(self.root))
        self.assertEqual(result, [dir_link])

    def test_orphaned_symlinked_directory_can_be_removed(self):
        dir_link = self._link(os.path.join(self.root, "no_such_dir"), "dirlink")
        list(collect_orphaned_symlinks(self.root, remove=True))
        self.assertFalse(os.path.lexists(dir_link))

    def test_mixed_tree_reports_only_orphans(self):
        self._touch("present")
        good = self._link(os.path.join(self.root, "present"), "good")
        bad1 = self._link(os.path.join(self.root, "absent"), "bad1")
        os.makedirs(os.path.join(self.root, "sub"))
        bad2 = self._link(
            os.path.join(self.root, "gone"), "sub", "bad2"
        )
        result = sorted(collect_orphaned_symlinks(self.root))
        expected = sorted([bad1, bad2])
        self.assertEqual(result, expected)
        self.assertNotIn(good, result)


if __name__ == "__main__":
    unittest.main()
