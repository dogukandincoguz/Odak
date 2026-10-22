# Windows PowerShell 5.1 / PowerShell 7. Run as a file or with irm ... | iex.
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\Odak'),
    [string]$DataDir = '',
    [string]$Ref = 'dev',
    [string]$GitHubToken = $env:ODAK_GITHUB_TOKEN,
    [string]$LegacyDataDir = '',
    [string]$SourceArchive = '',
    [switch]$NoLaunch,
    [switch]$NoShortcuts
)

# Keep functions, preferences and TLS settings out of the caller's session.
& {
    $ErrorActionPreference = 'Stop'
    Set-StrictMode -Version 2.0
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'Odak kurulumu Windows gerektirir.'
    }
    # Use this PowerShell edition's modules even when launched from another edition.
    foreach ($module in @('Microsoft.PowerShell.Utility', 'Microsoft.PowerShell.Archive')) {
        Import-Module -Name (Join-Path $PSHOME ('Modules\' + $module + '\' + $module + '.psd1')) -ErrorAction Stop
    }
    $previousTls = [Net.ServicePointManager]::SecurityProtocol
    [Net.ServicePointManager]::SecurityProtocol = $previousTls -bor [Net.SecurityProtocolType]::Tls12
    $temporaryParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
    $workName = 'odak-install-' + [guid]::NewGuid().ToString('N')
    $workPath = Join-Path $temporaryParent $workName

    function Invoke-OdakCommand {
        param([string]$Executable, [string[]]$Arguments)
        $previousModules = [Environment]::GetEnvironmentVariable('PSModulePath', 'Process')
        try {
            # Nested Windows PowerShell must not autoload PowerShell 7 modules.
            $env:PSModulePath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\Modules'
            & $Executable @Arguments
        } finally {
            [Environment]::SetEnvironmentVariable('PSModulePath', $previousModules, 'Process')
        }
        if ($LASTEXITCODE -ne 0) { throw ('Komut tamamlanamadi: ' + [IO.Path]::GetFileName($Executable)) }
    }

    function Get-OdakUv {
        $command = Get-Command uv.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command) { return $command.Source }
        $privateUv = Join-Path $env:LOCALAPPDATA 'Programs\Odak-Tools\uv\uv.exe'
        if (Test-Path -LiteralPath $privateUv -PathType Leaf) { return $privateUv }
        Write-Host 'uv resmi kaynagindan kuruluyor...'
        $installer = Join-Path $workPath 'install-uv.ps1'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://astral.sh/uv/install.ps1' -OutFile $installer
        $previousUnmanaged = [Environment]::GetEnvironmentVariable('UV_UNMANAGED_INSTALL', 'Process')
        try {
            $env:UV_UNMANAGED_INSTALL = Split-Path -Parent $privateUv
            $powershellPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
            Invoke-OdakCommand $powershellPath @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $installer) | Out-Host
        } finally {
            [Environment]::SetEnvironmentVariable('UV_UNMANAGED_INSTALL', $previousUnmanaged, 'Process')
        }
        if (-not (Test-Path -LiteralPath $privateUv -PathType Leaf)) { throw 'uv kurulumu tamamlanamadi.' }
        return $privateUv
    }

    function Find-OdakPython {
        param([string]$UvPath)
        # --system avoids choosing the environment that is being updated.
        $startInfo = New-Object Diagnostics.ProcessStartInfo
        $startInfo.FileName = $UvPath
        $startInfo.Arguments = 'python find --system 3.13'
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $startInfo.StandardOutputEncoding = New-Object Text.UTF8Encoding($false)
        $startInfo.StandardErrorEncoding = New-Object Text.UTF8Encoding($false)
        foreach ($attempt in @(0, 1)) {
            $process = [Diagnostics.Process]::Start($startInfo)
            try {
                $found = $process.StandardOutput.ReadToEnd().Trim()
                $null = $process.StandardError.ReadToEnd()
                $process.WaitForExit()
                if ($process.ExitCode -eq 0 -and (Test-Path -LiteralPath $found -PathType Leaf)) { return $found }
            } finally { $process.Dispose() }
            if ($attempt -eq 0) {
                Write-Host 'Python 3.13 uv ile kuruluyor...'
                Invoke-OdakCommand $UvPath @('python', 'install', '3.13') | Out-Host
            }
        }
        throw 'Python 3.13 bulunamadi.'
    }

    try {
        $InstallDir = [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($InstallDir))
        $marker = Join-Path $InstallDir '.odak-install.json'
        if (Test-Path -LiteralPath $marker -PathType Leaf) {
            $previous = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($previous.format -ne 'odak-install-v1') { throw 'Kurulum kaydi gecersiz.' }
            if (-not $DataDir) { $DataDir = $previous.data_dir }
        } elseif ((Test-Path -LiteralPath $InstallDir) -and @(Get-ChildItem -LiteralPath $InstallDir -Force).Count) {
            throw 'Kurulum klasoru bos degil ve Odak kurulum kaydi yok. Bos bir klasor sec.'
        }
        if (-not $DataDir) { $DataDir = Join-Path $env:LOCALAPPDATA 'Odak\data' }
        $DataDir = [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($DataDir))
        New-Item -ItemType Directory -Path $workPath | Out-Null
        $zipPath = Join-Path $workPath 'odak.zip'
        if ($SourceArchive) {
            Copy-Item -LiteralPath $SourceArchive -Destination $zipPath
            $revision = 'local-' + (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
        } else {
            $headers = @{ 'User-Agent' = 'Odak-Installer'; 'Accept' = 'application/vnd.github+json'; 'X-GitHub-Api-Version' = '2022-11-28' }
            if ($GitHubToken) { $headers['Authorization'] = 'Bearer ' + $GitHubToken }
            $repository = 'https://api.github.com/repos/dogukandincoguz/Odak'
            Write-Host ('Odak indiriliyor: ' + $Ref)
            try {
                $commit = Invoke-RestMethod -Uri ($repository + '/commits/' + [Uri]::EscapeDataString($Ref)) -Headers $headers
                $revision = $commit.sha
                if ($revision -notmatch '^[0-9a-f]{40}$') { throw 'Gecersiz GitHub yaniti.' }
                Invoke-WebRequest -UseBasicParsing -Uri ($repository + '/zipball/' + $revision) -Headers $headers -OutFile $zipPath
            } catch {
                # Never include authenticated redirect URLs or headers in errors.
                throw 'GitHub indirmesi tamamlanamadi. Interneti, branch adini ve repo erisimini kontrol et. Gizli repo icin -GitHubToken kullan; public repo token gerektirmez.'
            }
        }
        $extractPath = Join-Path $workPath 'source'
        New-Item -ItemType Directory -Path $extractPath | Out-Null
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $archive = [IO.Compression.ZipFile]::OpenRead($zipPath)
        try {
            foreach ($entry in $archive.Entries) {
                $destination = [IO.Path]::GetFullPath((Join-Path $extractPath $entry.FullName))
                if (-not $destination.StartsWith($extractPath + '\', [StringComparison]::OrdinalIgnoreCase)) {
                    throw 'Arsivda kurulum klasoru disina cikan bir yol var.'
                }
                if ((($entry.ExternalAttributes -shr 16) -band 61440) -eq 40960) { throw 'Arsiv sembolik bag iceriyor.' }
            }
        } finally { $archive.Dispose() }
        Expand-Archive -LiteralPath $zipPath -DestinationPath $extractPath
        $roots = @(Get-ChildItem -LiteralPath $extractPath -Directory)
        if ($roots.Count -ne 1) { throw 'Odak arsiv yapisi gecersiz.' }
        $sourcePath = $roots[0].FullName
        foreach ($required in @('app.py', 'pyproject.toml', 'uv.lock', 'install.ps1', 'tools\install_state.py')) {
            if (-not (Test-Path -LiteralPath (Join-Path $sourcePath $required) -PathType Leaf)) { throw ('Arsiv eksik: ' + $required) }
        }
        if (-not $LegacyDataDir -and -not $NoShortcuts -and -not (Test-Path -LiteralPath (Join-Path $DataDir 'odak.sqlite3'))) {
            $desktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Odak.lnk'
            if (Test-Path -LiteralPath $desktopShortcut -PathType Leaf) {
                $shellObject = New-Object -ComObject WScript.Shell
                $shortcut = $shellObject.CreateShortcut($desktopShortcut)
                if ($shortcut.WorkingDirectory -and (Test-Path -LiteralPath (Join-Path $shortcut.WorkingDirectory 'app.py'))) {
                    if ($shortcut.Arguments -match '--data-dir\s+"([^"]+)"') { $LegacyDataDir = $matches[1] }
                    else { $LegacyDataDir = Join-Path $shortcut.WorkingDirectory 'data' }
                }
            }
        }
        $uvPath = Get-OdakUv
        $pythonPath = Find-OdakPython $uvPath
        $arguments = @((Join-Path $sourcePath 'tools\install_state.py'), '--source', $sourcePath,
            '--target', $InstallDir, '--data-dir', $DataDir, '--uv', $uvPath, '--revision', $revision, '--ref', $Ref)
        if ($LegacyDataDir) { $arguments += @('--legacy-data-dir', $LegacyDataDir) }
        if ($NoLaunch) { $arguments += '--no-launch' }
        if ($NoShortcuts) { $arguments += '--no-shortcuts' }
        Invoke-OdakCommand $pythonPath $arguments
    } finally {
        [Net.ServicePointManager]::SecurityProtocol = $previousTls
        # Only remove this run's verified temporary directory.
        $resolvedWork = [IO.Path]::GetFullPath($workPath)
        if ((Split-Path -Leaf $resolvedWork) -eq $workName -and
            $resolvedWork.StartsWith($temporaryParent + '\', [StringComparison]::OrdinalIgnoreCase) -and
            (Test-Path -LiteralPath $resolvedWork)) {
            Remove-Item -LiteralPath $resolvedWork -Recurse -Force
        }
    }
}
