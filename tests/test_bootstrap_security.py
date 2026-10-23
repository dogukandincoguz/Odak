import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.source_digest import zip_digest

PROJECT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "Windows PowerShell bootstrap")
class BootstrapSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.archive = self.root / "source.zip"
        self.wrapper = self.root / "verify.ps1"
        self.wrapper.write_text('''param([string]$Bootstrap,[string]$Mode,[string]$Archive,[string]$Expected,[string]$Destination)
$ErrorActionPreference = 'Stop'
foreach ($module in @('Microsoft.PowerShell.Utility', 'Microsoft.PowerShell.Archive')) {
    Import-Module -Name (Join-Path $PSHOME ('Modules\\' + $module + '\\' + $module + '.psd1')) -ErrorAction Stop
}
$workPath = Split-Path -Parent $Archive
$parseTokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($Bootstrap, [ref]$parseTokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'Invalid PowerShell syntax.' }
$definitions = $ast.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -in @('Get-OdakSourceHash', 'Assert-OdakFileHash', 'Install-OdakUv', 'Get-OdakUv') }, $true)
foreach ($definition in $definitions) { Invoke-Expression $definition.Extent.Text }
switch ($Mode) {
    'source' { Get-OdakSourceHash $Archive }
    'uv' { Install-OdakUv $Archive $Expected $Expected $Destination }
    { $_ -in @('cache', 'old') } {
        if ($Mode -eq 'old') {
            $fakeUv = Join-Path $workPath 'old-uv.cmd'
            [IO.File]::WriteAllText($fakeUv, "@echo off`r`necho uv 0.12.5`r`n")
            function Get-Command { return [pscustomobject]@{ Source=$fakeUv } }
        } else {
            function Get-Command { return $null }
        }
        function Invoke-WebRequest { throw 'Unexpected download.' }
        $env:PROCESSOR_ARCHITECTURE = 'AMD64'
        $env:PROCESSOR_ARCHITEW6432 = ''
        $env:LOCALAPPDATA = $workPath
        $cached = Join-Path $workPath 'Programs\\Odak-Tools\\uv\\0.13.5\\x86_64\\uv.exe'
        New-Item -ItemType Directory -Path (Split-Path -Parent $cached) -Force | Out-Null
        [IO.File]::WriteAllText($cached, 'tampered cached executable')
        Get-OdakUv
    }
}
''', encoding="utf-8")
        system = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.shells = [str(system)]
        if shell := shutil.which("pwsh.exe") or shutil.which("pwsh"):
            self.shells.append(shell)

    def tearDown(self):
        self.temporary.cleanup()

    def archive_entries(self, entries, compression=zipfile.ZIP_DEFLATED):
        with zipfile.ZipFile(self.archive, "w", compression) as archive:
            for name, data in entries:
                archive.writestr(name, data)

    def verify(self, shell, mode="source", expected="0" * 64):
        return subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.wrapper),
                               "-Bootstrap", str(PROJECT / "bootstrap.ps1"), "-Mode", mode,
                               "-Archive", str(self.archive), "-Expected", expected,
                               "-Destination", str(self.root / "uv-target/uv.exe")],
                              capture_output=True)

    def test_contents_and_names_are_hashed_independently_of_zip_representation(self):
        entries = [("Odak-root/app.py", b"reviewed source"), ("Odak-root/odak/model.py", b"other file")]
        self.archive_entries(entries)
        expected = zip_digest(self.archive)
        for compression, ordered in ((zipfile.ZIP_DEFLATED, entries), (zipfile.ZIP_STORED, list(reversed(entries)))):
            self.archive_entries(ordered, compression)
            for shell in self.shells:
                with self.subTest(shell=shell, compression=compression):
                    result = self.verify(shell)
                    self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                    self.assertEqual(result.stdout.decode().strip(), expected)

    def test_modified_missing_or_added_file_changes_the_digest(self):
        original = [("Odak-root/app.py", b"reviewed source"), ("Odak-root/odak/model.py", b"other file")]
        self.archive_entries(original)
        expected = zip_digest(self.archive)
        variants = [original[:1], original + [("Odak-root/extra.py", b"injected")],
                    [("Odak-root/app.py", b"changed"), original[1]],
                    [("Odak-root/renamed.py", original[0][1]), original[1]]]
        for entries in variants:
            self.archive_entries(entries)
            for shell in self.shells:
                with self.subTest(shell=shell, entries=entries):
                    result = self.verify(shell)
                    self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                    self.assertNotEqual(result.stdout.decode().strip(), expected)

    def test_unsafe_and_ambiguous_archive_paths_are_rejected(self):
        variants = [[("Odak-root/../escape.py", b"bad")], [("/absolute.py", b"bad")],
                    [("Odak-root/name:stream", b"bad")],
                    [("Odak-root/app.py", b"one"), ("Other-root/file.py", b"two")],
                    [("Odak-root/app.py", b"one"), ("Odak-root/APP.py", b"two")],
                    [("Odak-root/app.py.", b"bad")]]
        for entries in variants:
            self.archive_entries(entries)
            for shell in self.shells:
                with self.subTest(shell=shell, entries=entries):
                    self.assertNotEqual(self.verify(shell).returncode, 0)
        link = zipfile.ZipInfo("Odak-root/link")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr(link, b"../../elsewhere")
        for shell in self.shells:
            self.assertNotEqual(self.verify(shell).returncode, 0)

    def test_wrong_uv_hash_is_rejected_before_unpacking_or_installing(self):
        self.archive_entries([("uv.exe", b"not the official binary")])
        for shell in self.shells:
            result = self.verify(shell, mode="uv")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"SHA-256", result.stderr)
            self.assertFalse((self.root / "uv-extracted").exists())
            self.assertFalse((self.root / "uv-target").exists())

    def test_wrong_uv_binary_hash_is_rejected_before_installing(self):
        self.archive_entries([("uv.exe", b"not the official binary")])
        expected = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        for index, shell in enumerate(self.shells):
            with self.subTest(shell=shell):
                if index:
                    unpacked = (self.root / "uv-extracted").resolve()
                    self.assertTrue(unpacked.is_relative_to(self.root.resolve()))
                    self.assertNotEqual(unpacked, self.root.resolve())
                    shutil.rmtree(unpacked)
                result = self.verify(shell, mode="uv", expected=expected)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"SHA-256", result.stderr)
                self.assertFalse((self.root / "uv-target").exists())

    def test_tampered_cached_uv_is_rejected_without_a_download(self):
        for shell in self.shells:
            for mode in ("cache", "old"):
                with self.subTest(shell=shell, mode=mode):
                    result = self.verify(shell, mode=mode)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(b"SHA-256", result.stderr)
                    self.assertNotIn(b"Unexpected download", result.stderr)

    def test_missing_or_wrong_source_hash_never_touches_install_or_data(self):
        self.archive_entries([("Odak-root/app.py", b"untrusted")])
        for shell in self.shells:
            for extra in ([], ["-SourceSha256", "0" * 64]):
                result = subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                         str(PROJECT / "bootstrap.ps1"), "-SourceArchive", str(self.archive),
                                         "-InstallDir", str(self.root / "application"),
                                         "-DataDir", str(self.root / "data"), "-NoLaunch", "-NoShortcuts", *extra],
                                        capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"sha", result.stderr.lower())
                self.assertFalse((self.root / "application").exists())
                self.assertFalse((self.root / "data").exists())
