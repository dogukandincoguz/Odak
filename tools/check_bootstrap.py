"""PowerShell 5.1 ile geçici, ayrı klasörlere gerçek kurulum ve güncelleme.

--clean-runtime ayrıca uv ve Python'un bulunmadığı durumu dener.
Gerçek kısayollara ve görevlere dokunmaz. İnternet gerektirir.
"""
import argparse
import json
import os
import subprocess
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from odak.model import Store
from tools.source_digest import zip_digest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--clean-runtime",action="store_true")
    parser.add_argument("--powershell-seven",action="store_true")
    args=parser.parse_args()
    powershell=Path(os.environ["SystemRoot"])/"System32/WindowsPowerShell/v1.0/powershell.exe"
    if args.powershell_seven:
        powershell=Path(shutil.which("pwsh.exe") or shutil.which("pwsh") or "")
        if not powershell.is_file():raise RuntimeError("PowerShell 7 bulunamadı.")
    output=PROJECT/"artifacts"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bootstrap-check-",dir=output) as directory:
        temporary=Path(directory)
        archive=temporary/"source.zip"
        files=subprocess.check_output(["git","-c","safe.directory="+PROJECT.as_posix(),"ls-files"],cwd=PROJECT,text=True).splitlines()
        files.extend(["bootstrap.ps1","tools/install_state.py"])
        with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as zip_file:
            for relative in sorted(set(files)):
                if (PROJECT/relative).is_file():zip_file.write(PROJECT/relative,"Odak-check/"+relative)
        target=temporary/"kurulum alanı"
        data=temporary/"kullanıcı verileri"
        environment={**os.environ,"UV_CACHE_DIR":str(PROJECT/".uv-cache"),"PYTHONIOENCODING":"utf-8"}
        if args.clean_runtime:
            environment.update(LOCALAPPDATA=str(temporary/"isolated-localappdata"),
                PATH=str(Path(os.environ["SystemRoot"])/"System32")+os.pathsep+str(powershell.parent),
                UV_PYTHON_INSTALL_DIR=str(temporary/"managed-python"),
                UV_PYTHON_BIN_DIR=str(temporary/"python-bin"), UV_PYTHON_PREFERENCE="only-managed")
        command=[str(powershell),"-NoProfile","-ExecutionPolicy","Bypass","-File",str(PROJECT/"bootstrap.ps1"),
            "-SourceArchive",str(archive),"-SourceSha256",zip_digest(archive),
            "-InstallDir",str(target),"-DataDir",str(data),"-NoLaunch","-NoShortcuts"]
        subprocess.run(command,cwd=PROJECT,env=environment,check=True)
        marker=json.loads((target/".odak-install.json").read_text(encoding="utf-8"))
        assert marker["format"]=="odak-install-v1"
        assert Path(marker["data_dir"])==data.resolve()
        store=Store(data/"odak.sqlite3")
        identity=store.save("Türkçe görev: ı İ ş ğ ü ö ç",steps=["Kaybolmayan adım"])
        store.set_step(store.all()[0].steps[0].id,True)
        store.set_setting("window_size",[510,800])
        store.close()
        (target/"personal-file.txt").write_text("keep",encoding="utf-8")
        subprocess.run(command,cwd=PROJECT,env=environment,check=True)
        store=Store(data/"odak.sqlite3")
        assert store.all()[0].id==identity and store.all()[0].steps[0].done
        assert store.setting("window_size")==[510,800]
        assert len(list((data/"backups").glob("odak-*.sqlite3")))==1
        store.close()
        assert (target/"personal-file.txt").read_text()=="keep"
        desktop,startup=temporary/"fake desktop",temporary/"fake startup"
        wrapper=temporary/"check-shortcuts.ps1"
        wrapper.write_text('''param([string]$Application,[string]$Data,[string]$DesktopTarget,[string]$StartupTarget)
$ErrorActionPreference = 'Stop'
& (Join-Path $Application 'install.ps1') -DataDir $Data -ShortcutDirectories @($DesktopTarget,$StartupTarget)
$shellObject = New-Object -ComObject WScript.Shell
foreach ($folder in @($DesktopTarget,$StartupTarget)) {
    $shortcut = $shellObject.CreateShortcut((Join-Path $folder 'Odak.lnk'))
    if ($shortcut.TargetPath -ne (Join-Path $Application '.venv\\Scripts\\pythonw.exe')) { throw 'Wrong executable.' }
    if ($shortcut.Arguments -ne ('"' + (Join-Path $Application 'app.py') + '" --data-dir "' + $Data + '"')) { throw 'Wrong arguments.' }
    if ($shortcut.WorkingDirectory -ne $Application) { throw 'Wrong working directory.' }
}
Write-Output 'Desktop and Startup shortcut arguments verified.'
''',encoding="utf-8")
        subprocess.run([str(powershell),"-NoProfile","-ExecutionPolicy","Bypass","-File",str(wrapper),
            "-Application",str(target),"-Data",str(data),"-DesktopTarget",str(desktop),"-StartupTarget",str(startup)],check=True)
        # The same bytes must work through Invoke-Expression, without PSScriptRoot.
        pipeline_wrapper=temporary/"check-iex.ps1"
        pipeline_wrapper.write_text('''param([string]$Bootstrap,[string]$Archive,[string]$SourceHash,[string]$Application,[string]$Data)
$ErrorActionPreference = 'Stop'
$arguments = @{ SourceArchive=$Archive; SourceSha256=$SourceHash; InstallDir=$Application; DataDir=$Data; NoLaunch=$true; NoShortcuts=$true }
$script = Get-Content -LiteralPath $Bootstrap -Raw -Encoding UTF8
Invoke-Expression ('& {' + [Environment]::NewLine + $script + [Environment]::NewLine + '} @arguments')
if (-not (Test-Path -LiteralPath (Join-Path $Application '.odak-install.json'))) { throw 'Missing install marker.' }
''',encoding="utf-8")
        subprocess.run([str(powershell),"-NoProfile","-ExecutionPolicy","Bypass","-File",str(pipeline_wrapper),
            "-Bootstrap",str(PROJECT/"bootstrap.ps1"),"-Archive",str(archive),"-SourceHash",zip_digest(archive),"-Application",str(target),"-Data",str(data)],
            cwd=temporary,env=environment,check=True)
    print("PowerShell bootstrap check: install, update, Invoke-Expression, Unicode paths, data preservation and isolated shortcuts OK.")


if __name__=="__main__":main()
