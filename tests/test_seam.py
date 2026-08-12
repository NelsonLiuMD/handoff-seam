"""Adversarial tests for handoff-seam.

Hermetic: every test runs against throwaway repositories with git config
isolated from the host machine. No network, no model calls.
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

BIN = pathlib.Path(__file__).resolve().parent.parent / "bin" / "handoff-seam"
MARKER_OPEN = "<!-- handoff-seam-v1 -->"


class SeamTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="handoff-seam-test."))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = dict(os.environ)
        self.env.update(
            {
                "HOME": str(self.tmp),
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_SYSTEM": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "tester",
                "GIT_AUTHOR_EMAIL": "tester@example.invalid",
                "GIT_COMMITTER_NAME": "tester",
                "GIT_COMMITTER_EMAIL": "tester@example.invalid",
            }
        )

    def git(self, repo, *args, check=True):
        return subprocess.run(
            ["git", "-C", str(repo)] + list(args),
            check=check,
            env=self.env,
            capture_output=True,
            text=True,
        )

    def cli(self, *args, cwd):
        return subprocess.run(
            [sys.executable, str(BIN)] + list(args),
            cwd=str(cwd),
            env=self.env,
            capture_output=True,
            text=True,
        )

    def make_repo(self, name="repo-a"):
        repo = self.tmp / name
        repo.mkdir()
        self.git(repo, "init", "-q", "-b", "main")
        (repo / "file.txt").write_text("tracked content\n")
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-q", "-m", "initial")
        return repo

    def write_handoff(self, repo, name="handoff-2026-01-01-demo.md"):
        path = repo / name
        path.write_text("# Handoff\n\nplan: alpha\n")
        return path

    def seal(self, path, *extra):
        result = self.cli("seal", str(path), *list(extra), cwd=path.parent)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return result

    def assert_verify(self, cwd, path, code, needle=None, *extra):
        result = self.cli("verify", str(path), *list(extra), cwd=cwd)
        self.assertEqual(result.returncode, code, msg=result.stderr)
        if needle is not None:
            self.assertIn(needle, result.stderr)
        return result

    # ------------------------------------------------------------------ happy paths

    def test_seal_then_verify_clean_tree(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        sealed = self.seal(handoff)
        self.assertIn("handoff-seam read", sealed.stdout)
        self.assert_verify(repo, handoff, 0)
        self.assertIn(MARKER_OPEN, handoff.read_text())

    def test_verify_from_subdirectory_of_correct_worktree(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        subdir = repo / "sub"
        subdir.mkdir()
        self.assert_verify(subdir, handoff, 0)

    def test_dirty_tree_roundtrip_is_stable(self):
        repo = self.make_repo()
        (repo / "file.txt").write_text("modified tracked content\n")
        (repo / "untracked.txt").write_text("untracked content\n")
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        self.assert_verify(repo, handoff, 0)

    def test_detached_head_roundtrip(self):
        repo = self.make_repo()
        self.git(repo, "checkout", "-q", "--detach")
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        self.assert_verify(repo, handoff, 0)

    def test_symlinked_path_resolves_to_physical_worktree(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        link = self.tmp / "link-to-repo"
        os.symlink(repo, link)
        self.assert_verify(link, handoff, 0)

    def test_special_untracked_file_is_fingerprinted(self):
        repo = self.make_repo()
        os.mkfifo(repo / "pipe")
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        self.assert_verify(repo, handoff, 0)

    def test_capture_prints_schema(self):
        repo = self.make_repo()
        result = self.cli("capture", cwd=repo)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        seam = json.loads(result.stdout)
        head = self.git(repo, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(seam["head_oid"], head)
        self.assertEqual(seam["schema_version"], 1)
        self.assertEqual(seam["worktree_root"], os.path.realpath(repo))

    def test_session_id_binding(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff, "--session-id", "abc123")
        self.assert_verify(repo, handoff, 0, None, "--session-id", "abc123")
        self.assert_verify(repo, handoff, 1, "session_id", "--session-id", "other9")

    def test_sibling_handoffs_do_not_invalidate_each_other(self):
        repo = self.make_repo()
        first = self.write_handoff(repo, "handoff-2026-01-01-a.md")
        self.seal(first)
        second = self.write_handoff(repo, "handoff-2026-01-02-b.md")
        self.assert_verify(repo, first, 0)
        self.seal(second)
        self.assert_verify(repo, first, 0)
        self.assert_verify(repo, second, 0)

    # ------------------------------------------------------------------ the core claim

    def test_wrong_worktree_same_commit_is_rejected(self):
        repo = self.make_repo()
        self.git(repo, "checkout", "-q", "--detach")
        linked = self.tmp / "repo-b"
        self.git(repo, "worktree", "add", "-q", "--detach", str(linked), "HEAD")
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        self.assert_verify(repo, handoff, 0)
        result = self.assert_verify(linked, handoff, 1, "worktree_root")
        # Same commit, same detached state, same cleanliness: the physical
        # worktree identity alone must carry the rejection.
        self.assertNotIn("head_oid", result.stderr)
        self.assertNotIn("branch_ref", result.stderr)
        self.assertNotIn("status_sha256", result.stderr)

    def test_repo_copy_same_branch_same_commit_is_rejected(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        copy = self.tmp / "repo-copy"
        shutil.copytree(repo, copy, symlinks=True)
        # Standing in the copy, the original handoff no longer describes here.
        self.assert_verify(copy, handoff, 1, "worktree_root")
        # The copied handoff file is a different artifact entirely.
        copied = copy / handoff.name
        self.assert_verify(copy, copied, 2, "moved or copied")

    def test_moved_handoff_file_is_rejected(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        moved = repo / "moved-note.md"
        shutil.move(handoff, moved)
        self.assert_verify(repo, moved, 2, "moved or copied")

    # ------------------------------------------------------------------ drift classes

    def test_new_commit_is_rejected(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        (repo / "file.txt").write_text("advanced\n")
        self.git(repo, "commit", "-aqm", "advance")
        self.assert_verify(repo, handoff, 1, "head_oid")

    def test_branch_switch_same_commit_is_rejected(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        self.git(repo, "checkout", "-q", "-b", "feature")
        self.assert_verify(repo, handoff, 1, "branch_ref")

    def test_detaching_after_seal_is_rejected(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        self.git(repo, "checkout", "-q", "--detach")
        self.assert_verify(repo, handoff, 1, "branch_ref")

    def test_new_untracked_file_is_rejected(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        (repo / "surprise.txt").write_text("drift\n")
        self.assert_verify(repo, handoff, 1, "status_sha256")

    def test_untracked_content_change_is_rejected(self):
        repo = self.make_repo()
        (repo / "untracked.txt").write_text("original\n")
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        (repo / "untracked.txt").write_text("mutated!\n")
        self.assert_verify(repo, handoff, 1, "status_sha256")

    def test_tracked_modification_after_seal_is_rejected(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        (repo / "file.txt").write_text("tampered tracked content\n")
        self.assert_verify(repo, handoff, 1, "status_sha256")

    # ------------------------------------------------------------------ structural failures

    def test_unsealed_file_is_rejected(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.assert_verify(repo, handoff, 2, "no seam block")

    def test_seal_refuses_already_sealed_file(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        result = self.cli("seal", str(handoff), cwd=repo)
        self.assertEqual(result.returncode, 2)
        self.assertIn("already contains", result.stderr)

    def test_duplicate_seam_blocks_are_rejected(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        text = handoff.read_text()
        lines = text.splitlines()
        start = lines.index(MARKER_OPEN)
        block = "\n".join(lines[start : start + 3])
        handoff.write_text(text + "\n" + block + "\n")
        self.assert_verify(repo, handoff, 2, "exactly one")

    def test_tampered_field_value_is_rejected_as_drift(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        lines = handoff.read_text().splitlines()
        index = lines.index(MARKER_OPEN) + 1
        seam = json.loads(lines[index])
        seam["head_oid"] = "deadbeef" * 5
        lines[index] = json.dumps(seam, separators=(",", ":"), sort_keys=True)
        handoff.write_text("\n".join(lines) + "\n")
        self.assert_verify(repo, handoff, 1, "head_oid")

    def test_malformed_field_value_is_rejected_structurally(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        lines = handoff.read_text().splitlines()
        index = lines.index(MARKER_OPEN) + 1
        seam = json.loads(lines[index])
        seam["head_oid"] = "not-a-commit"
        lines[index] = json.dumps(seam, separators=(",", ":"), sort_keys=True)
        handoff.write_text("\n".join(lines) + "\n")
        self.assert_verify(repo, handoff, 2, "head_oid")

    def test_unborn_repository_is_refused(self):
        repo = self.tmp / "unborn"
        repo.mkdir()
        self.git(repo, "init", "-q", "-b", "main")
        handoff = self.write_handoff(repo)
        result = self.cli("seal", str(handoff), cwd=repo)
        self.assertEqual(result.returncode, 2)
        self.assertIn("no commit", result.stderr)

    def test_dirty_submodule_is_refused(self):
        sub = self.make_repo("sub")
        host = self.make_repo("host")
        added = self.git(
            host,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(sub),
            "vendor",
            check=False,
        )
        if added.returncode != 0:
            self.skipTest("git submodule add unavailable: %s" % added.stderr.strip())
        self.git(host, "commit", "-qm", "add submodule")
        (host / "vendor" / "inner-drift.txt").write_text("dirty submodule\n")
        handoff = self.write_handoff(host)
        result = self.cli("seal", str(handoff), cwd=host)
        self.assertEqual(result.returncode, 2, msg=result.stderr)
        self.assertIn("submodule", result.stderr)

    # ------------------------------------------------------------------ read gate

    def test_read_prints_prose_only_on_pass(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        passing = self.cli("read", str(handoff), cwd=repo)
        self.assertEqual(passing.returncode, 0, msg=passing.stderr)
        self.assertIn("plan: alpha", passing.stdout)
        (repo / "drift.txt").write_text("drift\n")
        failing = self.cli("read", str(handoff), cwd=repo)
        self.assertEqual(failing.returncode, 1)
        self.assertEqual(failing.stdout, "")
        self.assertNotIn("plan: alpha", failing.stderr)

    # ------------------------------------------------------------------ portability

    def test_sha256_object_format_repository(self):
        repo = self.tmp / "sha256-repo"
        repo.mkdir()
        probe = self.git(
            repo, "init", "-q", "-b", "main", "--object-format=sha256", check=False
        )
        if probe.returncode != 0:
            self.skipTest("git lacks sha256 object format support")
        (repo / "file.txt").write_text("content\n")
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-qm", "initial")
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        self.assert_verify(repo, handoff, 0)
        seam = json.loads(self.cli("capture", cwd=repo).stdout)
        self.assertEqual(len(seam["head_oid"]), 64)


if __name__ == "__main__":
    unittest.main()
