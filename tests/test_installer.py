"""The installer (tools/desktop.py) and the lab journal (lab/lab, lab/rollback.py), in a temp tree.

Nothing here touches the real home, /etc, the real journal or xfconf: the module's paths point
into a temp directory, LAB_STATE_DIR moves the journal, and stub `sudo`, `xfconf-query`, `mv`
and `rm` programs stand first on PATH. The stub sudo only logs and runs the command as the
current user; directories made read-only stand in for root-owned ones, and the stub opens them
for the duration of one command. That is enough to see WHEN lab asks for privilege.
"""
import contextlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import desktop  # noqa: E402

LAB = ROOT / "lab/lab"
REAL_MV = shutil.which("mv")
REAL_RM = shutil.which("rm")

STUBS = {
    "sudo": '''#!/bin/bash
echo "$*" >> "$SUDO_LOG"
[ -z "${SUDO_FAIL-}" ] || exit 1
IFS=: read -ra dirs <<< "${SUDO_UNLOCK-}"
for d in "${dirs[@]}"; do [ -d "$d" ] && chmod u+w "$d"; done
"$@"; rc=$?
for d in "${dirs[@]}"; do [ -d "$d" ] && chmod u-w "$d"; done
exit $rc
''',
    "xfconf-query": '''#!/bin/bash
echo "$*" >> "$XFCONF_LOG"
''',
    "mv": f'''#!/bin/bash
[ -z "${{FAIL_MV-}}" ] || {{ echo "mv: injected failure" >&2; exit 1; }}
exec {REAL_MV} "$@"
''',
    "rm": f'''#!/bin/bash
for a in "$@"; do [ "$a" != "${{FAIL_RM-}}" ] || {{ echo "rm: injected failure" >&2; exit 1; }}; done
exec {REAL_RM} "$@"
''',
}


@unittest.skipIf(os.geteuid() == 0, "root can write everywhere: the privilege checks need a normal user")
class TempTree(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="installer-test-")).resolve()
        self.addCleanup(self.remove_tree)
        self.home, self.root, self.src = self.tmp / "home", self.tmp / "root", self.tmp / "src"
        self.state, self.build_dir, self.stubs = self.tmp / "state", self.tmp / "build", self.tmp / "stubs"
        for path in (self.home, self.root, self.src / "xfconf", self.stubs):
            path.mkdir(parents=True)
        for name, text in STUBS.items():
            (self.stubs / name).write_text(text)
            (self.stubs / name).chmod(0o755)
        self.sudo_log, self.xfconf_log = self.tmp / "sudo.log", self.tmp / "xfconf.log"
        self.env = {"LAB_STATE_DIR": str(self.state), "PATH": f"{self.stubs}:{os.environ['PATH']}",
                    "SUDO_LOG": str(self.sudo_log), "XFCONF_LOG": str(self.xfconf_log), "SUDO_UNLOCK": ""}
        patcher = mock.patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.multiple(
            desktop, SOURCE=self.src, XFCONF=self.src / "xfconf", BUILD=self.build_dir, HOME=self.home,
            SYSTEM_ROOT=self.root, STATE=self.state, MANIFEST=self.state / "installed.manifest",
            EXPERIMENT="t1", lab=self.quiet_lab)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Whatever a test does, it must be inside the temp tree.
        assert str(self.state).startswith(tempfile.gettempdir()) and desktop.HOME == self.home

    def remove_tree(self):
        subprocess.run(["chmod", "-R", "u+rwx", str(self.tmp)])
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers
    @staticmethod
    def quiet_lab(*args, **kw):
        done = subprocess.run([str(LAB), *args], capture_output=True, **kw)
        if done.returncode:
            raise AssertionError(f"lab {args} failed: {done.stderr.decode()}")
        return done

    def lab(self, *args, input="", **env):
        with mock.patch.dict(os.environ, env):
            return subprocess.run([str(LAB), *args], input=input, capture_output=True, text=True)

    def put(self, relative, text="data\n", executable=False):
        path = self.src / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o755 if executable else 0o644)
        return path

    def apply(self, experiment="t1"):
        with mock.patch.object(desktop, "EXPERIMENT", experiment), open(os.devnull, "w") as null, \
                contextlib.redirect_stdout(null), mock.patch.object(desktop, "xfconf_live", return_value={}):
            desktop.apply()

    def locked(self, *relatives):
        """Make directories under the fake root read-only (root-owned stand-ins) and unlock them for sudo."""
        for relative in relatives:
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        for relative in relatives:
            (self.root / relative).chmod(0o555)
        os.environ["SUDO_UNLOCK"] = ":".join(str(self.root / relative) for relative in relatives)

    def journal(self):
        path = self.state / "journal.tsv"
        return [line.split("\t") for line in path.read_text().splitlines()] if path.exists() else []

    def sudo_calls(self):
        return self.sudo_log.read_text().splitlines() if self.sudo_log.exists() else []

    def mode(self, path):
        return stat.S_IMODE(Path(path).stat().st_mode)


class InstallTests(TempTree):
    def test_first_install_modes_directories_and_rollback(self):
        self.locked("etc", "etc/ro.d", "usr")
        self.put("bin/tool", "#!/bin/sh\n")
        self.put("share/app/data.txt")
        self.put("config/app/sub/conf")
        self.put("system/etc/app.d/x.conf")
        self.put("system/etc/ro.d/y.conf")
        self.put("system/usr/local/bin/hook", "#!/bin/sh\n")
        self.apply()
        self.assertEqual((self.home / ".config/app/sub/conf").read_text(), "data\n")
        self.assertEqual(self.mode(self.home / ".local/bin/tool"), 0o755)
        self.assertEqual(self.mode(self.home / ".local/share/app/data.txt"), 0o644)
        self.assertEqual(self.mode(self.root / "usr/local/bin/hook"), 0o755)
        self.assertEqual(desktop.differences(), [])
        self.assertEqual(desktop.mode_differences(), [])
        # sudo only where the directory was not ours - never for a path under the home
        calls = self.sudo_calls()
        self.assertTrue(calls and not any(str(self.home) in call for call in calls), calls)
        self.assertTrue(any(f"mkdir -- {self.root}/etc/app.d" in call for call in calls), calls)
        self.assertTrue(any(f"mkdir -- {self.root}/usr/local" in call for call in calls), calls)
        self.assertFalse(any(f"mkdir -- {self.root}/usr/local/bin" in call for call in calls), calls)
        actions = {row[2] for row in self.journal()}
        self.assertEqual(actions, {"file", "dir"})        # first install: nothing to back up, no mode records
        self.sudo_log.unlink()
        done = self.lab("rollback", "t1")
        self.assertEqual(done.returncode, 0, done.stderr)
        for path in (".local/bin/tool", ".local/share/app", ".config/app", ".local"):
            self.assertFalse((self.home / path).exists(), path)
        for path in ("etc/app.d", "etc/ro.d/y.conf", "usr/local"):
            self.assertFalse((self.root / path).exists(), path)
        self.assertTrue((self.root / "etc/ro.d").is_dir())          # not ours: stays
        self.assertEqual(self.journal(), [])
        calls = self.sudo_calls()
        self.assertTrue(calls and not any(str(self.home) in call for call in calls), calls)
        self.assertTrue(any(f"rmdir -- {self.root}/etc/app.d" in call for call in calls), calls)
        self.assertTrue(any(f"rmdir -- {self.root}/usr/local" in call for call in calls), calls)

    def test_changed_file_is_backed_up_and_rolled_back(self):
        self.put("bin/tool", "#!/bin/sh\necho 1\n")
        self.apply()
        self.put("bin/tool", "#!/bin/sh\necho 2\n")
        self.apply("t2")
        self.assertEqual([row[2] for row in self.journal() if row[1] == "t2"], ["backup"])
        self.assertEqual(self.lab("rollback", "t1").returncode, 1)         # t2 touched it later
        self.assertEqual(self.lab("rollback", "t2").returncode, 0)
        self.assertEqual((self.home / ".local/bin/tool").read_text(), "#!/bin/sh\necho 1\n")
        self.assertEqual(self.mode(self.home / ".local/bin/tool"), 0o755)
        self.assertEqual(self.lab("rollback", "t1").returncode, 0)
        self.assertFalse((self.home / ".local/bin/tool").exists())

    def test_empty_source_is_installed(self):
        self.put("config/empty", "")
        self.assertEqual(len(desktop.differences()), 1)
        self.apply()
        self.assertTrue((self.home / ".config/empty").is_file())
        self.assertEqual(desktop.differences(), [])


class DeletedSourceTests(TempTree):
    def test_deleted_source_is_reported_and_removed_with_a_journal_record(self):
        self.put("bin/a", "#!/bin/sh\n")
        self.put("config/dir/old.conf", "old\n")
        self.put("config/dir/keep.conf", "keep\n")
        self.apply()
        self.assertEqual(desktop.removed(), [])
        self.assertEqual(sorted((self.state / "installed.manifest").read_text().split()),
                         ["bin/a", "config/dir/keep.conf", "config/dir/old.conf"])
        (self.src / "config/dir/old.conf").unlink()
        stale = desktop.removed()
        self.assertEqual([str(dest) for _, dest in stale], [str(self.home / ".config/dir/old.conf")])
        desktop.build()
        self.assertFalse((self.build_dir / "config/dir/old.conf").exists())     # the build output is pruned too
        self.assertTrue((self.build_dir / "config/dir/keep.conf").exists())
        self.apply("t2")
        self.assertFalse((self.home / ".config/dir/old.conf").exists())
        self.assertTrue((self.home / ".config/dir/keep.conf").exists())
        self.assertEqual([row[2:4] for row in self.journal() if row[1] == "t2"],
                         [["backup", str(self.home / ".config/dir/old.conf")]])
        self.assertEqual((self.state / "installed.manifest").read_text().split(), ["bin/a", "config/dir/keep.conf"])
        self.assertEqual(desktop.removed(), [])
        self.assertEqual(self.lab("rollback", "t2").returncode, 0)             # the removal is undoable
        self.assertEqual((self.home / ".config/dir/old.conf").read_text(), "old\n")

    def test_directories_the_removal_empties_go_too_and_come_back_on_rollback(self):
        self.put("config/solo/deep/x.conf")
        self.put("config/other/y.conf")
        self.apply()
        (self.src / "config/solo").mkdir(exist_ok=True)
        shutil.rmtree(self.src / "config/solo")
        self.apply("t2")
        self.assertFalse((self.home / ".config/solo").exists())
        self.assertTrue((self.home / ".config").is_dir())                   # the kind's root stays
        self.assertIn("rmdir", [row[2] for row in self.journal() if row[1] == "t2"])
        self.assertEqual(self.lab("rollback", "t2").returncode, 0)
        self.assertEqual((self.home / ".config/solo/deep/x.conf").read_text(), "data\n")

    def test_a_directory_with_foreign_files_stays(self):
        self.put("config/solo/x.conf")
        self.apply()
        (self.home / ".config/solo/user-file").write_text("mine")
        shutil.rmtree(self.src / "config/solo")
        self.apply("t2")
        self.assertFalse((self.home / ".config/solo/x.conf").exists())
        self.assertEqual((self.home / ".config/solo/user-file").read_text(), "mine")

    def test_dangling_symlink_of_a_deleted_source_is_removed(self):
        self.put("config/link.conf")
        self.apply()
        (self.home / ".config/link.conf").unlink()
        (self.home / ".config/link.conf").symlink_to(self.tmp / "nowhere")
        (self.src / "config/link.conf").unlink()
        self.assertEqual(len(desktop.removed()), 1)
        self.apply("t2")
        self.assertFalse((self.home / ".config/link.conf").is_symlink())
        self.assertEqual(desktop.removed(), [])
        self.assertEqual(self.lab("rollback", "t2").returncode, 0)
        self.assertTrue((self.home / ".config/link.conf").is_symlink())

    def test_file_that_another_source_still_installs_is_not_stale(self):
        self.put("config/moved.conf")
        self.apply()
        (self.src / "config/moved.conf").unlink()
        self.put("home/.config/moved.conf")           # same target from another kind
        self.assertEqual(desktop.removed(), [])

    def test_missing_manifest_is_seeded_from_the_build_output(self):
        (self.build_dir / "config").mkdir(parents=True)
        (self.build_dir / "config/ghost.conf").write_text("x")
        (self.build_dir / "config/gone.conf").write_text("x")
        (self.home / ".config").mkdir()
        (self.home / ".config/ghost.conf").write_text("x")            # still installed; gone.conf is not
        self.assertEqual([str(dest) for _, dest in desktop.removed()], [str(self.home / ".config/ghost.conf")])
        self.assertFalse(desktop.MANIFEST.exists())                   # status never writes
        desktop.build()
        self.assertTrue(desktop.MANIFEST.exists())                    # build keeps what it is about to prune
        self.assertFalse((self.build_dir / "config/ghost.conf").exists())
        self.assertEqual([str(dest) for _, dest in desktop.removed()], [str(self.home / ".config/ghost.conf")])

    def test_a_manifest_line_cannot_point_outside_the_kinds(self):
        victim = self.tmp / "victim"
        victim.write_text("x")
        desktop.manifest_write({"../../victim", "config/../../victim", "/etc/passwd", "bogus/x"})
        self.assertEqual(desktop.removed(), [])
        self.assertTrue(victim.exists())


class ModeTests(TempTree):
    def test_lost_executable_bit_is_drift_and_apply_journals_the_fix(self):
        self.put("bin/tool", "#!/bin/sh\n")
        self.put("config/plain.conf")
        self.apply()
        (self.home / ".local/bin/tool").chmod(0o644)
        (self.home / ".config/plain.conf").chmod(0o600)               # not a script: the mode is left alone
        drift = desktop.mode_differences(desktop.differences())
        self.assertEqual([(str(dest), wanted, actual) for _, dest, wanted, actual in drift],
                         [(str(self.home / ".local/bin/tool"), 0o755, 0o644)])
        self.apply("t2")
        self.assertEqual(self.mode(self.home / ".local/bin/tool"), 0o755)
        self.assertEqual(self.mode(self.home / ".config/plain.conf"), 0o600)
        self.assertEqual([row[2:] for row in self.journal() if row[1] == "t2"],
                         [["mode", str(self.home / ".local/bin/tool"), "644"]])
        self.assertEqual(desktop.mode_differences(), [])
        self.assertEqual(self.lab("rollback", "t2").returncode, 0)
        self.assertEqual(self.mode(self.home / ".local/bin/tool"), 0o644)

    def test_system_hook_mode_follows_the_source(self):
        hook = self.put("system/usr/lib/hooks/zz-hook", "#!/bin/sh\n", executable=True)
        conf = self.put("system/etc/thing.conf")
        script = self.put("system/usr/local/bin/session", "#!/bin/sh\n")
        self.assertEqual(desktop.wanted_mode(hook, self.root / "usr/lib/hooks/zz-hook"), 0o755)
        self.assertIsNone(desktop.wanted_mode(conf, self.root / "etc/thing.conf"))
        self.assertEqual(desktop.wanted_mode(script, self.root / "usr/local/bin/session"), 0o755)

    def test_mode_of_a_root_file_is_fixed_through_sudo_only_when_not_ours(self):
        self.locked("usr")
        self.put("system/usr/hook", "#!/bin/sh\n", executable=True)
        self.apply()
        self.sudo_log.unlink()
        (self.root / "usr/hook").chmod(0o644)
        self.apply("t2")
        self.assertEqual(self.mode(self.root / "usr/hook"), 0o755)
        # the file is ours here (the stub sudo runs as the user), so chmod needs no privilege
        self.assertEqual(self.sudo_calls(), [])


class JournalTests(TempTree):
    def test_failed_replacement_leaves_no_record_stage_or_backup(self):
        target = self.home / "f"
        target.write_text("old\n")
        done = self.lab("write", "t1", str(target), FAIL_MV="1")
        # (the content comes from stdin: an empty stdin is a different file than "old\n")
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(self.journal(), [])
        self.assertEqual(target.read_text(), "old\n")
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ["f"])
        self.assertEqual(list((self.state / "backups").iterdir()), [])

    def test_failed_first_write_leaves_nothing(self):
        done = self.lab("write", "t1", str(self.home / "new"), FAIL_MV="1")
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(self.journal(), [])
        self.assertEqual(list(self.home.iterdir()), [])

    def test_denied_privilege_leaves_nothing(self):
        self.locked("etc")
        done = self.lab("write", "t1", str(self.root / "etc/new"), SUDO_FAIL="1")
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(self.journal(), [])
        self.assertEqual(list((self.root / "etc").iterdir()), [])

    def test_failed_remove_keeps_file_and_writes_nothing(self):
        target = self.home / "f"
        target.write_text("keep\n")
        done = self.lab("remove", "t1", str(target), FAIL_RM=str(target))
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(self.journal(), [])
        self.assertEqual(target.read_text(), "keep\n")
        self.assertEqual(list((self.state / "backups").iterdir()), [])

    def test_record_appears_only_after_success(self):
        target = self.home / "f"
        target.write_text("old\n")
        done = self.lab("write", "t1", str(target), input="new\n")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([row[2:4] for row in self.journal()], [["backup", str(target)]])
        self.assertEqual(target.read_text(), "new\n")

    def test_read_only_installed_file_is_replaced_and_its_mode_kept(self):
        target = self.home / "ro"
        target.write_text("old\n")
        target.chmod(0o444)
        done = self.lab("write", "t1", str(target), input="new\n")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual((target.read_text(), self.mode(target)), ("new\n", 0o444))
        self.assertEqual(self.sudo_calls(), [])                  # ours: no privilege

    def test_legacy_rmdir_record_gets_privilege_per_target(self):
        (self.root / "etc/legacy.d").mkdir(parents=True)
        (self.home / "mine").mkdir()
        (self.root / "etc/kept.d").mkdir()
        (self.root / "etc/kept.d/foreign").write_text("x")
        self.locked("etc")
        rows = [f"2026-01-01T00:00:00+00:00\told\tcmd\trmdir -- {path}\t" for path in
                (self.root / "etc/kept.d", self.home / "mine", self.root / "etc/legacy.d")]
        (self.state).mkdir(exist_ok=True)
        (self.state / "journal.tsv").write_text("\n".join(rows) + "\n")
        done = self.lab("rollback", "old")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse((self.root / "etc/legacy.d").exists())
        self.assertFalse((self.home / "mine").exists())
        self.assertTrue((self.root / "etc/kept.d/foreign").exists())     # not empty: kept, record dropped
        self.assertEqual(self.journal(), [])
        calls = self.sudo_calls()
        self.assertTrue(any("legacy.d" in call for call in calls) and not any("mine" in call for call in calls), calls)

    def test_path_records_conflict_with_later_modes(self):
        target = self.home / "f"
        target.write_text("a")
        self.assertEqual(self.lab("chmod", "t2", "600", str(target)).returncode, 0)
        rows = [["2026-01-01T00:00:00+00:00", "t1", "file", str(target)]] + self.journal()
        (self.state / "journal.tsv").write_text("".join("\t".join(r) + "\n" for r in rows))
        done = self.lab("rollback", "t1")
        self.assertEqual(done.returncode, 1)
        self.assertIn("conflicts with a later experiment", done.stderr)
        self.assertTrue(target.exists())


class XfconfTests(TempTree):
    def xfconf_calls(self):
        return self.xfconf_log.read_text().splitlines() if self.xfconf_log.exists() else []

    def test_apply_records_structured_undo_from_the_live_values(self):
        (self.src / "xfconf/ch.xml").write_text(
            '<channel name="ch" version="1.0"><property name="a" type="int" value="8"/>'
            '<property name="b" type="string" value="x"/>'
            '<property name="c" type="array"><value type="int" value="1"/><value type="int" value="2"/></property></channel>')
        live = {"/a": ("int", "7"), "/c": ("array", [("int", "5"), ("int", "6")])}     # /b is not set live yet
        with mock.patch.object(desktop, "xfconf_live", return_value=live):
            desktop.xfconf_apply()
        self.assertEqual([row[2:] for row in self.journal()], [
            ["xfconf", "ch:/a", '["-n", "-t", "int", "-s", "7"]'],
            ["xfconf", "ch:/b", '["-r"]'],
            ["xfconf", "ch:/c", '["-n", "-a", "-t", "int", "-s", "5", "-t", "int", "-s", "6"]']])
        self.assertEqual(self.xfconf_calls(), [
            "-c ch -p /a -n -t int -s 8", "-c ch -p /b -n -t string -s x",
            "-c ch -p /c -n -a -t int -s 1 -t int -s 2"])
        self.xfconf_log.unlink()
        self.assertEqual(self.lab("rollback", "t1").returncode, 0)
        self.assertEqual(self.xfconf_calls(), [          # newest first
            "-c ch -p /c -n -a -t int -s 5 -t int -s 6", "-c ch -p /b -r", "-c ch -p /a -n -t int -s 7"])

    def test_live_values_are_what_the_daemon_holds_not_the_xml_file(self):
        (self.src / "xfconf/ch.xml").write_text('<channel name="ch"><property name="a" type="int" value="8"/></channel>')
        stale_file = self.home / ".config/xfce4/xfconf/xfce-perchannel-xml/ch.xml"
        stale_file.parent.mkdir(parents=True)
        stale_file.write_text('<channel name="ch"><property name="a" type="int" value="8"/></channel>')
        with mock.patch.object(desktop, "xfconf_live", return_value={"/a": ("int", "3")}):
            self.assertEqual([(c, p, w, l) for c, p, w, l in desktop.xfconf_differences()],
                             [("ch", "/a", ("int", "8"), ("int", "3"))])

    def test_daemon_values_are_converted_with_their_types(self):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")            # PyGObject's own deprecation chatter
                from gi.repository import GLib
        except ImportError:
            self.skipTest("PyGObject is not installed")
        value = desktop.xfconf_value
        self.assertEqual(value(GLib.Variant("b", True)), ("bool", "true"))
        self.assertEqual(value(GLib.Variant("i", -3)), ("int", "-3"))
        self.assertEqual(value(GLib.Variant("u", 3)), ("uint", "3"))
        self.assertEqual(value(GLib.Variant("s", "x y")), ("string", "x y"))
        self.assertTrue(desktop.xfconf_same(("double", "100.000000"), value(GLib.Variant("d", 100.0))))
        array = GLib.Variant("av", [GLib.Variant("i", 1), GLib.Variant("i", 50)])
        self.assertEqual(value(array), ("array", [("int", "1"), ("int", "50")]))

    def set_property(self, experiment, prop="/p", value="1", channel="ch"):
        done = self.lab("xfconf", experiment, channel, prop, '["-n", "-t", "int", "-s", "0"]', "--", "-n", "-t", "int", "-s", value)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_older_experiment_cannot_undo_a_newer_one_on_the_same_property(self):
        self.set_property("A", value="1")
        self.set_property("B", value="2")
        self.set_property("C", prop="/other")
        done = self.lab("rollback", "A")
        self.assertEqual(done.returncode, 1)
        self.assertIn("conflicts with a later experiment", done.stderr)
        self.assertEqual(len(self.journal()), 3)
        self.assertEqual(len(self.xfconf_calls()), 3)                  # nothing was undone
        self.assertEqual(self.lab("rollback", "C").returncode, 0)       # an unrelated property is free
        self.assertEqual(self.lab("rollback", "B").returncode, 0)
        self.assertEqual(self.lab("rollback", "A").returncode, 0)       # in order, it works
        self.assertEqual(self.xfconf_calls()[3:], ["-c ch -p /other -n -t int -s 0", "-c ch -p /p -n -t int -s 0",
                                                    "-c ch -p /p -n -t int -s 0"])
        self.assertEqual(self.journal(), [])

    def test_same_property_in_another_channel_is_no_conflict(self):
        self.set_property("A", channel="one")
        self.set_property("B", channel="two")
        self.assertEqual(self.lab("rollback", "A").returncode, 0)

    def test_old_cmd_records_take_part_in_the_conflict_check(self):
        rows = ["2026-01-01T00:00:00+00:00\tA\tcmd\txfconf-query -c ch -p /p -t int -s 5\t"]
        self.state.mkdir(exist_ok=True)
        (self.state / "journal.tsv").write_text("\n".join(rows) + "\n")
        self.set_property("B", value="2")
        done = self.lab("rollback", "A")
        self.assertEqual(done.returncode, 1)
        self.assertIn("conflicts", done.stderr)
        self.assertEqual(self.lab("rollback", "B").returncode, 0)
        self.assertEqual(self.lab("rollback", "A").returncode, 0)       # the old record still runs as a shell command
        self.assertEqual(self.xfconf_calls()[-1], "-c ch -p /p -t int -s 5")

    def test_failed_set_writes_no_undo_record(self):
        (self.stubs / "xfconf-query").write_text("#!/bin/bash\nexit 1\n")
        done = self.lab("xfconf", "A", "ch", "/p", '["-r"]', "--", "-n", "-t", "int", "-s", "1")
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(self.journal(), [])


if __name__ == "__main__":
    unittest.main()
