import os
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch

from odak.platforms import default_data_directory
from odak.startup import Startup, startup_directory, desktop_entry
from tools.install_desktop import create_launcher


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project = self.root / 'Türkçe proje & space'
        self.project.mkdir()
        (self.project / 'assets').mkdir()
        (self.project / 'assets/odak.icns').write_bytes(b'icon')
        self.data = self.root / 'Görev verileri'

    def tearDown(self):
        self.temporary.cleanup()

    def test_desktop_icons_include_native_sizes_and_transparent_corners(self):
        from PySide6.QtGui import QImageReader
        assets = Path(__file__).resolve().parents[1] / "assets"
        # Without a 256px ICO frame Windows can pad a small icon in its jumbo image list.
        for filename, required in (
            ("odak.ico", {16, 24, 32, 48, 256}),
            ("odak.icns", {16, 32, 64, 128, 256, 512, 1024}),
            ("odak.png", {256}),
        ):
            with self.subTest(filename=filename):
                sizes = set()
                reader = QImageReader(str(assets / filename))
                for index in range(reader.imageCount()):
                    reader = QImageReader(str(assets / filename))
                    if index:
                        self.assertTrue(reader.jumpToImage(index))
                    image = reader.read()
                    self.assertFalse(image.isNull(), reader.errorString())
                    self.assertEqual(image.width(), image.height())
                    self.assertTrue(image.hasAlphaChannel())
                    self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
                    self.assertEqual(image.pixelColor(image.width() // 2, image.height() // 2).alpha(), 255)
                    sizes.add(image.width())
                self.assertTrue(required <= sizes, (required, sizes))

    def test_linux_autostart_uses_xdg_and_preserves_other_launchers(self):
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root)}):
            self.assertEqual(startup_directory('linux'), self.root / 'autostart')
        directory = self.root / 'startup'
        directory.mkdir()
        other = directory / 'other.desktop'
        other.write_text('keep')
        startup = Startup(self.project, self.data, directory, platform='linux')
        self.assertFalse(startup.enabled())
        startup.set_enabled(True)
        text = startup.shortcut.read_text(encoding='utf-8')
        self.assertIn('[Desktop Entry]', text)
        self.assertIn('--data-dir', text)
        self.assertIn(self.data.name, text)
        self.assertTrue(startup.enabled())
        startup.set_enabled(False)
        self.assertFalse(startup.enabled())
        self.assertEqual(other.read_text(), 'keep')
        self.assertEqual(list(directory.iterdir()), [other])

    def test_macos_launch_agent_preserves_arguments_and_does_not_restart_after_exit(self):
        startup = Startup(self.project, self.data, self.root, platform='darwin')
        startup.set_enabled(True)
        config = plistlib.loads(startup.shortcut.read_bytes())
        self.assertEqual(config['ProgramArguments'], [sys.executable, str(self.project/'app.py'), '--data-dir', str(self.data)])
        self.assertTrue(config['RunAtLoad'])
        self.assertNotIn('KeepAlive', config)
        self.assertEqual(config['LimitLoadToSessionType'], 'Aqua')
        startup.set_enabled(False)
        self.assertFalse(startup.enabled())

    def test_existing_source_data_remains_in_use_on_unix(self):
        for platform in ('linux', 'darwin'):
            with self.subTest(platform=platform), patch('odak.platforms.sys.platform', platform):
                with patch.dict(os.environ, {'XDG_DATA_HOME': str(self.root/'xdg')}):
                    expected = self.root/'xdg/Odak' if platform == 'linux' else Path.home()/'Library/Application Support/Odak'
                    self.assertEqual(default_data_directory(self.project), expected)
                (self.project/'data').mkdir(exist_ok=True)
                legacy = self.project/'data/odak.sqlite3'
                legacy.touch()
                self.assertEqual(default_data_directory(self.project), self.project/'data')
                legacy.unlink()

    def test_desktop_entry_treats_paths_as_arguments_and_rejects_newlines(self):
        text = desktop_entry(['/a space/python', '/a $dollar/"quote"/100%/app.py', '--data-dir', str(self.data)], self.project)
        self.assertIn('"/a space/python"', text)
        self.assertIn('100%%', text)
        self.assertIn('\\\\$', text)
        self.assertNotIn('/bin/sh', text)
        with self.assertRaises(ValueError):
            desktop_entry(['python', 'unsafe\nExec=other'], self.project)

    def test_linux_launcher_is_separate_from_autostart(self):
        with patch('tools.install_desktop.sys.platform', 'linux'):
            target = create_launcher(self.project, self.data, self.root/'applications')
        self.assertEqual(target.name, 'odak.desktop')
        self.assertIn(self.data.name, target.read_text(encoding='utf-8'))
        self.assertFalse((self.root/'autostart').exists())

    def test_macos_bundle_launcher_quotes_shell_paths(self):
        with patch('tools.install_desktop.sys.platform', 'darwin'):
            target = create_launcher(self.project, self.data, self.root/'applications')
        config = plistlib.loads((target/'Contents/Info.plist').read_bytes())
        self.assertEqual(config['CFBundleExecutable'], 'odak')
        self.assertTrue(config['LSUIElement'])
        self.assertIn("'" + str(self.data) + "'", (target/'Contents/MacOS/odak').read_text(encoding='utf-8'))
        self.assertEqual((target/'Contents/Resources/odak.icns').read_bytes(), b'icon')
