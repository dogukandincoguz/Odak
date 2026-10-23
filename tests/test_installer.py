import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from odak.model import Store
from tools.install_state import FORMAT, database_copy, install, managed_path, prepare_data


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.source = self.root/"source"
        self.target = self.root/"application"
        self.data = self.root/"user-data"
        self.source.mkdir()
        for name in ("app.py","bootstrap.ps1","install.ps1","install.sh",".python-version","pyproject.toml","uv.lock","README.md",
                     "odak/ui.py","odak/model.py","assets/fonts/Inter.ttf","assets/fonts/OFL.txt","assets/odak.ico",
                     "assets/odak.png","assets/odak.icns","tools/install_state.py","tools/install_desktop.py"):
            file = self.source/name
            file.parent.mkdir(parents=True,exist_ok=True)
            file.write_text("new source",encoding="utf-8")

    def tearDown(self):
        self.directory.cleanup()

    def database(self, directory, title="Existing task"):
        store = Store(directory/"odak.sqlite3")
        identity = store.save(title,steps=["Preserved step"])
        store.set_step(store.all()[0].steps[0].id,True)
        store.set_setting("focus_preferences",{"work":30,"rest":5})
        store.close()
        return identity

    def test_install_preserves_existing_data_and_records_managed_files(self):
        identity = self.database(self.data)
        with patch("tools.install_state.subprocess.run") as run:
            install(self.source,self.target,self.data,"uv.exe","revision","dev",no_launch=True,no_shortcuts=True)
        self.assertEqual(run.call_count,3)
        self.assertIn("--locked",run.call_args_list[0].args[0])
        self.assertIn("-NoShortcuts" if os.name == "nt" else "--no-shortcuts",run.call_args_list[-1].args[0])
        self.assertNotIn("-Launch" if os.name == "nt" else "--launch",run.call_args_list[-1].args[0])
        marker=json.loads((self.target/".odak-install.json").read_text(encoding="utf-8"))
        self.assertEqual((marker["format"],marker["data_dir"]),(FORMAT,str(self.data.resolve())))
        self.assertIn("assets/fonts/OFL.txt",marker["files"])
        store=Store(self.data/"odak.sqlite3")
        try:
            self.assertEqual(store.all()[0].id,identity)
            self.assertTrue(store.all()[0].steps[0].done)
            self.assertEqual(store.setting("focus_preferences")["work"],30)
        finally:store.close()

    def test_failed_update_restores_sources_and_never_touches_database(self):
        self.database(self.data)
        with patch("tools.install_state.subprocess.run"):
            install(self.source,self.target,self.data,"uv.exe","v1","dev",no_launch=True,no_shortcuts=True)
        before=(self.data/"odak.sqlite3").read_bytes()
        old_marker=(self.target/".odak-install.json").read_bytes()
        (self.source/"app.py").write_text("broken update",encoding="utf-8")
        (self.source/"odak/added.py").write_text("new",encoding="utf-8")
        with patch("tools.install_state.subprocess.run",side_effect=subprocess.CalledProcessError(1,["uv"])):
            with self.assertRaises(subprocess.CalledProcessError):
                install(self.source,self.target,self.data,"uv.exe","v2","dev",no_launch=True,no_shortcuts=True)
        self.assertEqual((self.target/"app.py").read_text(),"new source")
        self.assertFalse((self.target/"odak/added.py").exists())
        self.assertEqual((self.data/"odak.sqlite3").read_bytes(),before)
        self.assertEqual((self.target/".odak-install.json").read_bytes(),old_marker)

    def test_updates_remove_obsolete_managed_files_but_keep_user_files(self):
        (self.source/"odak/retired.py").write_text("old",encoding="utf-8")
        with patch("tools.install_state.subprocess.run"):
            install(self.source,self.target,self.data,"uv.exe","v1","dev",no_launch=True,no_shortcuts=True)
            (self.target/"personal.txt").write_text("keep",encoding="utf-8")
            (self.source/"odak/retired.py").unlink()
            install(self.source,self.target,self.data,"uv.exe","v2","dev",no_launch=True,no_shortcuts=True)
        self.assertFalse((self.target/"odak/retired.py").exists())
        self.assertEqual((self.target/"personal.txt").read_text(),"keep")

    def test_unmanaged_directory_and_tampered_manifest_cannot_overwrite_files(self):
        self.target.mkdir()
        (self.target/"personal.txt").write_text("keep",encoding="utf-8")
        with self.assertRaises(ValueError):
            install(self.source,self.target,self.data,"uv.exe","v1","dev")
        marker={"format":FORMAT,"files":["../personal.txt"],"data_dir":str(self.data)}
        (self.target/".odak-install.json").write_text(json.dumps(marker),encoding="utf-8")
        with self.assertRaises(ValueError):
            install(self.source,self.target,self.data,"uv.exe","v1","dev")
        self.assertEqual((self.target/"personal.txt").read_text(),"keep")

    def test_managed_paths_reject_data_git_and_traversal(self):
        for relative in ("../outside.py","odak/../../outside.py","data/odak.sqlite3",".git/config",".venv/file","C:/outside.py"):
            with self.assertRaises(ValueError):managed_path(self.target,relative)

    @unittest.skipIf(os.name == "nt", "Unix symlink fixture")
    def test_arbitrary_symlink_parent_cannot_redirect_an_install(self):
        outside = self.root / "outside"
        outside.mkdir()
        link = self.root / "redirect"
        link.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            install(self.source, link / "application", self.data, "uv", "v1", "dev")
        self.assertEqual(list(outside.iterdir()), [])

    def test_migration_copies_sqlite_wal_and_existing_destination_wins(self):
        legacy=self.root/"legacy"
        store=Store(legacy/"odak.sqlite3")
        identity=store.save("In WAL",steps=["Keep"])
        try:
            prepare_data(self.data,legacy)
            incoming=Store(self.data/"odak.sqlite3")
            self.assertEqual(incoming.all()[0].id,identity)
            incoming.save("Only new location")
            incoming.close()
            prepare_data(self.data,legacy)
            con=sqlite3.connect(self.data/"odak.sqlite3")
            self.assertEqual(con.execute("SELECT count(*) FROM tasks").fetchone()[0],2)
            con.close()
            self.assertEqual(len(store.all()),1)
        finally:store.close()

    def test_invalid_database_does_not_replace_data(self):
        invalid=self.root/"not-a-database.sqlite3"
        invalid.write_text("bad",encoding="utf-8")
        destination=self.root/"preserved.sqlite3"
        destination.write_bytes(b"original")
        with self.assertRaises(sqlite3.DatabaseError):database_copy(invalid,destination)
        self.assertEqual(destination.read_bytes(),b"original")

    def test_repeated_updates_keep_only_three_owned_backups(self):
        self.database(self.data)
        directory=self.data/"backups"
        directory.mkdir()
        (directory/"personal.sqlite3").write_text("keep",encoding="utf-8")
        for _ in range(5):prepare_data(self.data)
        self.assertEqual(len(list(directory.glob("odak-*.sqlite3"))),3)
        self.assertTrue((directory/"personal.sqlite3").exists())

    def test_source_and_data_directories_cannot_overlap(self):
        for data in (self.target,self.target/"odak",self.root):
            with self.assertRaises(ValueError):
                install(self.source,self.target,data,"uv.exe","v1","dev")
