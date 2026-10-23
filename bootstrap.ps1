# Windows PowerShell 5.1 / PowerShell 7. Run as a file or with irm ... | iex.
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\Odak'),
    [string]$DataDir = '',
    [string]$Ref = '13598e705eb974765e218f9b159c721e53645f24',
    [ValidatePattern('^$|^[a-fA-F0-9]{64}$')]
    [string]$SourceSha256 = '',
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

    function Assert-OdakFileHash {
        param([string]$Path, [string]$Expected)
        if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $Expected) {
            throw 'SHA-256 dogrulamasi basarisiz. Indirilen dosya calistirilmadi.'
        }
    }

    function Get-OdakSourceHash {
        param([string]$Path)
        # Hash file names and contents, independent of ZIP timestamps/compression.
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $archive = [IO.Compression.ZipFile]::OpenRead($Path)
        $digests = New-Object 'Collections.Generic.SortedDictionary[string,string]' ([StringComparer]::Ordinal)
        $seen = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        $root = $null
        $sha = [Security.Cryptography.SHA256]::Create()
        try {
            foreach ($entry in $archive.Entries) {
                $name = $entry.FullName
                if ($name -match '[\\:\x00-\x1f<>"|?*]' -or $name.StartsWith('/')) { throw 'Arsivda gecersiz bir yol var.' }
                $parts = $name.TrimEnd('/').Split('/')
                if (@($parts | Where-Object { -not $_ -or $_ -eq '.' -or $_ -eq '..' -or $_.EndsWith('.') -or $_.EndsWith(' ') }).Count) {
                    throw 'Arsivda gecersiz bir yol var.'
                }
                if ($null -eq $root) { $root = $parts[0] }
                if ($parts[0] -cne $root) { throw 'Arsiv tek bir kok klasor icermeli.' }
                if ((($entry.ExternalAttributes -shr 16) -band 61440) -eq 40960) { throw 'Arsiv sembolik bag iceriyor.' }
                if ($name.EndsWith('/')) { continue }
                if ($parts.Count -lt 2) { throw 'Arsiv dosyalari kok klasorun altinda olmali.' }
                $relative = $name.Substring($root.Length + 1)
                if (-not $seen.Add($relative)) { throw 'Arsivda yinelenen dosya yolu var.' }
                $stream = $entry.Open()
                try { $digest = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
                finally { $stream.Dispose() }
                $digests.Add($relative, $digest)
            }
            if (-not $digests.Count) { throw 'Arsiv bos.' }
            $manifest = New-Object Text.StringBuilder
            foreach ($item in $digests.GetEnumerator()) {
                [void]$manifest.Append($item.Key).Append([char]0).Append($item.Value).Append([char]10)
            }
            $bytes = [Text.Encoding]::UTF8.GetBytes($manifest.ToString())
            return [BitConverter]::ToString($sha.ComputeHash($bytes)).Replace('-', '').ToLowerInvariant()
        } finally { $sha.Dispose(); $archive.Dispose() }
    }

    function Install-OdakUv {
        param([string]$Archive, [string]$ArchiveHash, [string]$BinaryHash, [string]$Destination)
        Assert-OdakFileHash $Archive $ArchiveHash
        $unpacked = Join-Path $workPath 'uv-extracted'
        Expand-Archive -LiteralPath $Archive -DestinationPath $unpacked
        $binary = Join-Path $unpacked 'uv.exe'
        Assert-OdakFileHash $binary $BinaryHash
        New-Item -ItemType Directory -Path (Split-Path -Parent $Destination) -Force | Out-Null
        Copy-Item -LiteralPath $binary -Destination $Destination
        Assert-OdakFileHash $Destination $BinaryHash
    }

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
        if ($command) {
            $installedVersion = & $command.Source --version
            if ($LASTEXITCODE -eq 0 -and $installedVersion -match '^uv (\d+\.\d+\.\d+)(?:\s|$)') {
                if ([version]$Matches[1] -ge [version]'0.13.5') { return $command.Source }
            }
        }
        $version = '0.13.5'
        $architecture = $env:PROCESSOR_ARCHITECTURE
        if ($env:PROCESSOR_ARCHITEW6432) { $architecture = $env:PROCESSOR_ARCHITEW6432 }
        switch ($architecture) {
            'AMD64' { $target = 'x86_64'; $zipHash = 'a38b8d1902b7cfbc76b423ba1bb456f623f42064cdc72628b6075b89afd1019a'; $exeHash = 'f45d1cb9d9140ca6d3f4005fdfc0ebeccf849fd04d1dc85804155cb923f1597b' }
            'ARM64' { $target = 'aarch64'; $zipHash = '09f47edf90726084a70f9426f6e3ca4f46e9bf7cbf23b1716ec64d60b055fae3'; $exeHash = '9690c472d1f5c9c57b5919512c64024dfff872d3e35be8f1892fe895a502b913' }
            'x86' { $target = 'i686'; $zipHash = '96228420d0a89a64757afba59932c1e58c4977e4122f2cc9f8615a51ba2d3084'; $exeHash = '9171486cedba050e942fbdacf26156a418245c934e7d1723a37000de62f65a21' }
            default { throw 'Bu islemci mimarisi icin uv paketi tanimli degil.' }
        }
        $privateUv = Join-Path $env:LOCALAPPDATA ("Programs\Odak-Tools\uv\$version\$target\uv.exe")
        if (Test-Path -LiteralPath $privateUv -PathType Leaf) {
            Assert-OdakFileHash $privateUv $exeHash
            return $privateUv
        }
        Write-Host ('uv ' + $version + ' resmi surum paketinden kuruluyor...')
        $zipPath = Join-Path $workPath 'uv.zip'
        Invoke-WebRequest -UseBasicParsing -Uri ("https://github.com/astral-sh/uv/releases/download/$version/uv-$target-pc-windows-msvc.zip") -OutFile $zipPath
        Install-OdakUv $zipPath $zipHash $exeHash $privateUv
        return $privateUv
    }

    function Find-OdakPython {
        param([string]$UvPath)
        # --system avoids choosing the environment that is being updated.
        $startInfo = New-Object Diagnostics.ProcessStartInfo
        $startInfo.FileName = $UvPath
        $startInfo.Arguments = 'python find --system 3.15.1'
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
                Write-Host 'Python 3.15.1 uv ile kuruluyor...'
                Invoke-OdakCommand $UvPath @('python', 'install', '3.15.1') | Out-Host
            }
        }
        throw 'Python 3.15.1 bulunamadi.'
    }

    try {
        if (-not $SourceSha256) {
            if ($SourceArchive -or $Ref -ne '13598e705eb974765e218f9b159c721e53645f24') {
                throw 'Farkli kaynak icin guvenilir bir -SourceSha256 degeri gerekli.'
            }
            $SourceSha256 = '74f010226390c0de4fec866408232b9f5c02f7e262912112f32335b2bed7bee1'
        }
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
                $revision = $Ref
                if ($revision -notmatch '^[0-9a-f]{40}$') {
                    $commit = Invoke-RestMethod -Uri ($repository + '/commits/' + [Uri]::EscapeDataString($Ref)) -Headers $headers
                    $revision = $commit.sha
                }
                if ($revision -notmatch '^[0-9a-f]{40}$') { throw 'Gecersiz GitHub yaniti.' }
                Invoke-WebRequest -UseBasicParsing -Uri ($repository + '/zipball/' + $revision) -Headers $headers -OutFile $zipPath
            } catch {
                # Never include authenticated redirect URLs or headers in errors.
                throw 'GitHub indirmesi tamamlanamadi. Internet baglantisini, surumu ve repo erisimini kontrol et.'
            }
        }
        if ((Get-OdakSourceHash $zipPath) -ne $SourceSha256) {
            throw 'Kaynak SHA-256 dogrulamasi basarisiz. Kurulum ve gorev verileri degistirilmedi.'
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
