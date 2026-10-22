[CmdletBinding()]
param(
    [switch]$Launch,
    [string]$DataDir = '',
    [switch]$NoShortcuts,
    [string[]]$ShortcutDirectories = @()
)
$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
if (-not $projectPath) { throw 'Yerel kurulum icin dosyayi calistir; irm | iex icin bootstrap.ps1 kullan.' }
$pythonPath = Join-Path $projectPath '.venv\Scripts\pythonw.exe'
$appPath = Join-Path $projectPath 'app.py'
$iconPath = Join-Path $projectPath 'assets\odak.ico'
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw 'Proje ortami bulunamadi. Once proje klasorunde uv sync --locked calistir.'
}
if (-not $DataDir) { $DataDir = Join-Path $projectPath 'data' }
$DataDir = [IO.Path]::GetFullPath($DataDir)
if ($DataDir -ne [IO.Path]::GetPathRoot($DataDir)) { $DataDir = $DataDir.TrimEnd('\') }
New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
# Paths cannot contain quotes. A trailing root slash needs Windows argv escaping.
$quotedData = $DataDir
if ($quotedData.EndsWith('\')) { $quotedData += '\' }
$appArguments = '"' + $appPath + '" --data-dir "' + $quotedData + '"'
if (-not $NoShortcuts) {
    $shellObject = New-Object -ComObject WScript.Shell
    if ($ShortcutDirectories.Count -eq 0) {
        $ShortcutDirectories = @([Environment]::GetFolderPath('Startup'), [Environment]::GetFolderPath('Desktop'))
    }
    foreach ($folderPath in $ShortcutDirectories) {
        if (-not $folderPath) { throw 'Kisayol klasoru bulunamadi.' }
        New-Item -ItemType Directory -Path $folderPath -Force | Out-Null
        $shortcutPath = Join-Path $folderPath 'Odak.lnk'
        $shortcut = $shellObject.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $pythonPath
        $shortcut.Arguments = $appArguments
        $shortcut.WorkingDirectory = $projectPath
        $shortcut.Description = 'Odak - masaustu gorev takipcisi'
        $shortcut.IconLocation = $iconPath
        $shortcut.Save()
        Write-Output ('Kisayol hazir: ' + $shortcutPath)
    }
}
if ($Launch) {
    # The application is the visible interactive window requested by the user.
    Start-Process -FilePath $pythonPath -ArgumentList $appArguments -WorkingDirectory $projectPath
    Write-Output 'Odak baslatildi.'
}
