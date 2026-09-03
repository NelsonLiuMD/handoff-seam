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
HOOK = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "verify-latest.sh"
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

    def json_cli(self, *args, cwd, code):
        """Run a --json invocation and assert the contract every report obeys."""
        result = self.cli(*(list(args) + ["--json"]), cwd=cwd)
        self.assertEqual(result.returncode, code, msg=result.stderr)
        self.assertEqual(result.stderr, "", msg="--json must leave stderr empty")
        report = json.loads(result.stdout)
        self.assertEqual(report["exit_code"], code)
        self.assertIs(report["verified"], code == 0)
        self.assertRegex(
            report["checked_at"], r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z"
        )
        for reason in report["reasons"]:
            self.assertEqual(
                set(reason), {"code", "field", "sealed", "current", "message"}
            )
        return report

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


    # ------------------------------------------------------------------ json output

    def test_verify_json_reports_a_verified_seam(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        report = self.json_cli("verify", str(handoff), cwd=repo, code=0)
        self.assertEqual(report["reasons"], [])
        self.assertNotIn("content", report)
        self.assertEqual(report["seam"]["worktree_root"], os.path.realpath(repo))
        self.assertEqual(report["seam"]["schema_version"], 1)

    def test_verify_json_reports_drift_field_by_field(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        (repo / "surprise.txt").write_text("drift\n")
        report = self.json_cli("verify", str(handoff), cwd=repo, code=1)
        self.assertEqual({reason["code"] for reason in report["reasons"]}, {"drift"})
        self.assertIn("status_sha256", [reason["field"] for reason in report["reasons"]])
        # The sealed seam still rides along, so a caller can say what was expected.
        head = self.git(repo, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(report["seam"]["head_oid"], head)
        self.assertNotIn("content", report)

    def test_verify_json_reports_structural_failure_on_unsealed_file(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        report = self.json_cli("verify", str(handoff), cwd=repo, code=2)
        self.assertIsNone(report["seam"])
        self.assertEqual(len(report["reasons"]), 1)
        self.assertEqual(report["reasons"][0]["code"], "structural")
        self.assertIsNone(report["reasons"][0]["field"])
        self.assertIn("no seam block", report["reasons"][0]["message"])

    def test_read_json_carries_prose_when_verified(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        report = self.json_cli("read", str(handoff), cwd=repo, code=0)
        self.assertEqual(report["reasons"], [])
        self.assertIn("plan: alpha", report["content"])

    def test_read_json_withholds_prose_when_rejected(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        (repo / "drift.txt").write_text("drift\n")
        result = self.cli("read", str(handoff), "--json", cwd=repo)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("plan: alpha", result.stdout)
        self.assertNotIn("plan: alpha", result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["verified"])
        self.assertNotIn("content", report)

    def test_unsupported_schema_version_names_the_upgrade(self):
        repo = self.make_repo()
        handoff = self.write_handoff(repo)
        self.seal(handoff)
        lines = handoff.read_text().splitlines()
        index = lines.index(MARKER_OPEN) + 1
        seam = json.loads(lines[index])
        seam["schema_version"] = 2
        # A newer build may also carry keys this one has never seen; the version
        # skew must be diagnosed ahead of the key-set check, not as a malformed
        # manifest.
        seam["future_field"] = "written by a newer build"
        lines[index] = json.dumps(seam, separators=(",", ":"), sort_keys=True)
        handoff.write_text("\n".join(lines) + "\n")
        expected = (
            "unsupported seam schema_version 2 (this build supports 1); "
            "upgrade handoff-seam"
        )
        self.assert_verify(repo, handoff, 2, expected)
        report = self.json_cli("verify", str(handoff), cwd=repo, code=2)
        self.assertEqual(report["reasons"][0]["message"], expected)


    # ------------------------------------------------------------------ SessionStart hook

    def run_hook(self, repo):
        env = dict(self.env)
        env["CLAUDE_PLUGIN_ROOT"] = str(BIN.parent.parent)
        return subprocess.run(
            ["bash", str(HOOK)],
            input=json.dumps({"cwd": str(repo)}),
            cwd=str(repo),
            env=env,
            capture_output=True,
            text=True,
        )

    def hook_context(self, repo):
        result = self.run_hook(repo)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def seal_in_claude_dir(self, repo):
        directory = repo / ".claude"
        directory.mkdir()
        handoff = self.write_handoff(directory)
        self.seal(handoff)
        return handoff

    def test_hook_surfaces_a_verified_verdict(self):
        repo = self.make_repo()
        self.seal_in_claude_dir(repo)
        context = self.hook_context(repo)
        self.assertIn("VERIFIED", context)
        self.assertNotIn("plan: alpha", context)

    def test_hook_surfaces_drift_reasons_and_never_the_prose(self):
        repo = self.make_repo()
        self.seal_in_claude_dir(repo)
        (repo / "surprise.txt").write_text("drift\n")
        context = self.hook_context(repo)
        self.assertIn("FAILED seam verification", context)
        # Rendered from --json reasons, not a raw dump of the report.
        self.assertIn("- status_sha256: sealed=", context)
        self.assertNotIn('"reasons"', context)
        self.assertNotIn("plan: alpha", context)


if __name__ == "__main__":
    unittest.main()
