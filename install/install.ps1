# Margin one-line install for Windows (0.10). Paste this in PowerShell (Start menu, type PowerShell):
#
#   powershell -ExecutionPolicy Bypass -c "irm https://github.com/dvaud/margin/releases/latest/download/install.ps1 | iex"
#
# Each release also has it as a file to double-click (0.14.5): Install-Margin-Windows.cmd, which is
# install/Install-Margin-Windows.cmd with this file below it (tools/release.py). Keep this file plain ASCII.
#
# It needs no git, no Python and no administrator rights:
#   1. gets uv (a small tool from Astral that installs Python programs), unless it is already here;
#   2. downloads the Margin package of this release and checks it against the release's checksums;
#   3. installs Margin with uv, which brings its own Python (3.12) and keeps it apart from any other Python;
#   4. makes the Margin icon (Start menu and Desktop) and opens Margin.
# Running the same line again installs the newest release over this one (quit Margin first): your projects stay.
#
# Options, set before running the line ($env:NAME = "value"):
#   MARGIN_LOCAL_ONLY=1   nothing may leave this computer (no cloud AI; built into the icon)
#   MARGIN_HOME=<folder>  keep projects and settings in another folder (built into the icon)
#   MARGIN_VERSION=0.10.0 install that release instead of the one this script came with
#   MARGIN_WHEEL=<file>   install this package file instead of downloading one (for testing a build)
#   MARGIN_NO_OPEN=1      do not open Margin at the end
#   MARGIN_FREE_WAIT=300  how many seconds to wait for programs that use Margin's folder to close (0.15.5)

# 0.15.5: the programs running from Margin's own folder (the one uv keeps it in, ...\uv\tools\margin). uv
# replaces that whole folder, and Windows does not let a running program's files go: while one ran (most often the
# Margin connector of an open Claude Code window, which runs Margin's own python.exe), uv removed part of the folder
# and stopped with "Access is denied", and every margin command then said "uv trampoline failed to canonicalize script
# path". So the install waits until none runs. Each comes back as Id, Name, Path and Line (its command line; empty
# where only Get-Process can be asked, as on Linux).
function Get-ProgramsIn([string[]]$Folders) {
    $sep = [IO.Path]::DirectorySeparatorChar
    $prefixes = @()
    foreach ($f in $Folders) {
        if (-not $f) { continue }
        try { $f = [IO.Path]::GetFullPath($f) } catch { }
        $prefixes += $f.TrimEnd('\', '/') + $sep
    }
    $procs = $null
    try {
        $procs = @(Get-CimInstance Win32_Process -ErrorAction Stop | ForEach-Object {
            [pscustomobject]@{ Id = [int]$_.ProcessId; Name = $_.Name; Path = $_.ExecutablePath; Line = $_.CommandLine } })
    } catch { }
    if ($null -eq $procs) {
        $procs = @(Get-Process -ErrorAction SilentlyContinue | ForEach-Object {
            $path = $null
            try { $path = $_.Path } catch { }   # a program of another user or of Windows itself does not say
            [pscustomobject]@{ Id = $_.Id; Name = $_.ProcessName; Path = $path; Line = '' } })
    }
    $found = @()
    foreach ($p in $procs) {
        if (-not $p.Path -or $p.Id -eq $PID) { continue }
        foreach ($prefix in $prefixes) {
            if (([string]$p.Path).StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { $found += $p; break }
        }
    }
    return $found
}
function Get-ProgramLabel($Program) {
    $what = "$($Program.Name), process $($Program.Id)"
    if ($Program.Line -match 'margin\.mcp_server') { return "Claude Code's Margin connector ($what)" }
    if ($Program.Line -match 'margin\.gui|margin-gui') { return "the Margin app ($what)" }
    return $what
}
function Wait-FolderFree([string[]]$Folders, [int]$Seconds) {
    $busy = @(Get-ProgramsIn $Folders)
    if ($busy.Count -eq 0) { return }
    Write-Host ''
    Write-Host '     Margin cannot be replaced while these programs run from its folder:' -ForegroundColor Yellow
    foreach ($p in $busy) { Write-Host "       - $(Get-ProgramLabel $p)" }
    Write-Host '     Quit Margin (Quit Margin in the app) and close Claude Code: the Claude app, and every terminal or'
    Write-Host '     editor where Claude Code runs. The install goes on by itself once they have closed. Nothing has'
    Write-Host "     been changed yet. If one does not close, end it in another PowerShell: Stop-Process -Id $(@($busy | ForEach-Object { $_.Id }) -join ',')"
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        $busy = @(Get-ProgramsIn $Folders)
        if ($busy.Count -eq 0) {
            Write-Host '     They have closed.'
            return
        }
    }
    $names = @($busy | ForEach-Object { Get-ProgramLabel $_ }) -join '; '
    $ids = @($busy | ForEach-Object { $_.Id }) -join ','
    throw "these programs still run from Margin's folder: $names. Nothing was changed. Quit Margin and close Claude Code (or end them: Stop-Process -Id $ids), then run the line again."
}

function Install-Margin {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is very slow with its progress bar
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072 } catch { }

    $repo = if ($env:MARGIN_REPO) { $env:MARGIN_REPO } else { 'dvaud/margin' }
    $version = if ($env:MARGIN_VERSION) { $env:MARGIN_VERSION } else { '@MARGIN_VERSION@' }
    $extras = 'connector,fast,pdfminer,ocr'
    if ($version.StartsWith('@') -and -not $env:MARGIN_WHEEL) {
        throw "this copy of install.ps1 does not name a version. Use the one from a GitHub Release: https://github.com/$repo/releases"
    }
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('margin-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        # 1. uv -------------------------------------------------------------------------------
        function Find-Uv {
            $c = Get-Command uv -ErrorAction SilentlyContinue
            if ($c) { return $c.Source }
            foreach ($p in @("$env:USERPROFILE\.local\bin\uv.exe", "$env:USERPROFILE\.cargo\bin\uv.exe")) {
                if (Test-Path $p) { return $p }
            }
            return $null
        }
        # 0.15.2: where uv put margin.exe. uv writes the folder in UTF-8, but PowerShell reads what a program writes
        # in the console's code page (437, 850, 852...), so a user folder with an accent came back garbled (the a with
        # an acute accent of C:\Users\David became two box-drawing characters) and the install stopped at "margin.exe
        # is missing" although it was there. So uv's answer is read as UTF-8 bytes, and the folders uv itself would
        # choose, in its order, are looked at too, should the answer still be unreadable.
        function Get-Utf8Output([string]$Exe, [string]$Arguments) {
            try {
                $psi = New-Object System.Diagnostics.ProcessStartInfo $Exe, $Arguments
                $psi.UseShellExecute = $false
                $psi.CreateNoWindow = $true
                $psi.RedirectStandardOutput = $true
                $psi.StandardOutputEncoding = New-Object System.Text.UTF8Encoding $false
                $p = [System.Diagnostics.Process]::Start($psi)
                $text = $p.StandardOutput.ReadToEnd()
                $p.WaitForExit()
                if ($p.ExitCode -eq 0) { return $text.Trim() }
            } catch { }
            return ''
        }
        function Get-MarginBinFolders([string]$Uv) {
            $folders = @((Get-Utf8Output $Uv 'tool dir --bin'), $env:UV_TOOL_BIN_DIR, $env:XDG_BIN_HOME)
            try { if ($env:XDG_DATA_HOME) { $folders += Join-Path (Split-Path $env:XDG_DATA_HOME -Parent) 'bin' } } catch { }
            if ($env:USERPROFILE) { $folders += Join-Path (Join-Path $env:USERPROFILE '.local') 'bin' }
            return @($folders | Where-Object { $_ } | Select-Object -Unique)
        }
        function Find-MarginExe([string]$Uv) {
            foreach ($folder in (Get-MarginBinFolders $Uv)) {
                try {
                    $exe = Join-Path $folder 'margin.exe'
                    if (Test-Path -LiteralPath $exe) { return $exe }
                } catch { }
            }
            return $null
        }
        # 0.15.5: the folder uv keeps Margin in (uv's answer read as UTF-8, then the folders uv itself would choose)
        function Get-MarginEnvFolders([string]$Uv) {
            $tools = @((Get-Utf8Output $Uv 'tool dir'), $env:UV_TOOL_DIR)
            if ($env:APPDATA) { $tools += Join-Path (Join-Path $env:APPDATA 'uv') 'tools' }
            return @($tools | Where-Object { $_ } | ForEach-Object { Join-Path $_ 'margin' } | Select-Object -Unique)
        }
        $uv = Find-Uv
        if (-not $uv) {
            Write-Host '1/4  Getting uv, which installs Margin and its own Python...'
            powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex" | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'uv could not be installed. Are you online?' }
            $uv = Find-Uv
            if (-not $uv) { throw 'uv was installed, but cannot be found. Open a new PowerShell window and run the line again.' }
        } else {
            Write-Host "1/4  uv is here already ($uv)."
        }

        # 2. the package ----------------------------------------------------------------------
        if ($env:MARGIN_WHEEL) {
            if (-not (Test-Path $env:MARGIN_WHEEL)) { throw "no such file: $env:MARGIN_WHEEL" }
            $wheelName = Split-Path $env:MARGIN_WHEEL -Leaf
            $wheel = Join-Path $tmp $wheelName
            Copy-Item $env:MARGIN_WHEEL $wheel
            Write-Host "2/4  Using the package $wheelName."
        } else {
            $wheelName = "margin-$version-py3-none-any.whl"
            $base = "https://github.com/$repo/releases/download/v$version"
            $wheel = Join-Path $tmp $wheelName
            Write-Host "2/4  Downloading Margin $version..."
            try {
                Invoke-WebRequest -UseBasicParsing -Uri "$base/$wheelName" -OutFile $wheel
                Invoke-WebRequest -UseBasicParsing -Uri "$base/SHA256SUMS" -OutFile (Join-Path $tmp 'SHA256SUMS')
            } catch { throw "the download from $base did not work. Are you online? ($($_.Exception.Message))" }
            $want = ''
            foreach ($line in Get-Content (Join-Path $tmp 'SHA256SUMS')) {
                $parts = $line -split '\s+'
                if ($parts.Count -ge 2 -and $parts[1].TrimStart('*') -eq $wheelName) { $want = $parts[0].ToLower() }
            }
            $got = (Get-FileHash -Algorithm SHA256 $wheel).Hash.ToLower()
            if (-not $want -or $want -ne $got) {
                throw "the downloaded package does not match the release's checksum (nothing was installed). Try again later."
            }
        }

        # 3. install --------------------------------------------------------------------------
        # 0.15.5: nothing may run from Margin's folder while uv replaces it (see Get-ProgramsIn)
        $wait = 300
        if ($env:MARGIN_FREE_WAIT) { $wait = [int]$env:MARGIN_FREE_WAIT }
        Wait-FolderFree (Get-MarginEnvFolders $uv) $wait
        Write-Host '3/4  Installing Margin (the first time this also fetches Python 3.12; a minute or two)...'
        $uri = ([System.Uri](Resolve-Path $wheel).Path).AbsoluteUri
        $env:UV_PYTHON_PREFERENCE = 'only-managed'
        & $uv tool install --force --quiet --python 3.12 "margin[$extras] @ $uri"
        if ($LASTEXITCODE -ne 0) {
            throw 'uv could not install Margin (see the lines above). If it says access is denied, a program still used Margin: quit Margin, close Claude Code and run the line again. That also repairs a Margin that no longer starts.'
        }
        $margin = Find-MarginExe $uv
        if (-not $margin) {
            throw "Margin was installed, but margin.exe is in none of these folders: $((Get-MarginBinFolders $uv) -join '; ')"
        }

        # 4. the icon, the Claude Code plugin, and open -------------------------------------------
        Write-Host '4/4  Making the Margin icon...'
        $postArgs = @('post-install', '--by', 'script')
        if ($env:MARGIN_HOME) { $postArgs += @('--home', $env:MARGIN_HOME) }
        if (-not $env:MARGIN_NO_OPEN) { $postArgs += '--open' }
        & $margin @postArgs
        if ($LASTEXITCODE -ne 0) { throw 'the last step did not work (see above).' }
        Write-Host ''
        Write-Host 'Done. Next time, open Margin from its icon (Start menu or Desktop). It tells you when there is a new version.'
    } finally {
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    }
}

try {
    Install-Margin
} catch {
    Write-Host ''
    Write-Host "Margin could not be installed: $($_.Exception.Message)" -ForegroundColor Red
    # `irm ... | iex` runs this in the person's own window: never `exit`, which would close it
}
