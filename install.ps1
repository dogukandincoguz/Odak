param([switch]$Launch)
$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$pythonPath = Join-Path $projectPath '.venv\Scripts\pythonw.exe'
$appPath = Join-Path $projectPath 'app.py'
$iconPath = Join-Path $projectPath 'assets\odak.ico'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Proje ortamı bulunamadı. Önce proje klasöründe uv sync çalıştır.'
}
$shellObject = New-Object -ComObject WScript.Shell
$startupPath = [Environment]::GetFolderPath('Startup')
$desktopPath = [Environment]::GetFolderPath('Desktop')
foreach ($folderPath in @($startupPath, $desktopPath)) {
    $shortcutPath = Join-Path $folderPath 'Odak.lnk'
    $shortcut = $shellObject.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $pythonPath
    $shortcut.Arguments = '"' + $appPath + '"'
    $shortcut.WorkingDirectory = $projectPath
    $shortcut.Description = 'Odak - masaüstü görev takipçisi'
    $shortcut.IconLocation = $iconPath
    $shortcut.Save()
    Write-Output ('Kısayol hazır: ' + $shortcutPath)
}
if ($Launch) {
    # Bu görünür pencere, kullanıcının istediği etkileşimli uygulamadır.
    Start-Process -FilePath $pythonPath -ArgumentList ('"' + $appPath + '"') -WorkingDirectory $projectPath
    Write-Output 'Odak başlatıldı.'
}
