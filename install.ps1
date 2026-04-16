Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageDir = Join-Path $scriptDir "agent-harness"
$skillSource = Join-Path $packageDir "cli_anything\jobnimbus\skills\SKILL.md"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python is required but was not found on PATH."
}

python -m pip --version | Out-Null

$userBase = python -c "import site; print(site.getuserbase())"
$userBase = $userBase.Trim()
$userBin = Join-Path $userBase "Scripts"

Write-Host "Installing cli-anything-jobnimbus as a user-level Python package..."
try {
    python -m pip install --user --upgrade $packageDir
}
catch {
    Write-Host "Retrying with --break-system-packages for externally-managed Python..."
    python -m pip install --user --upgrade --break-system-packages $packageDir
}

function Install-Skill {
    param(
        [string]$AgentName,
        [string]$HomeDir
    )

    if (Test-Path -LiteralPath $HomeDir -PathType Container) {
        $skillDir = Join-Path $HomeDir "skills\jobnimbus-read-cli"
        New-Item -ItemType Directory -Force -Path $skillDir | Out-Null
        Copy-Item -LiteralPath $skillSource -Destination (Join-Path $skillDir "SKILL.md") -Force
        Write-Host "Installed $AgentName skill to $skillDir"
    }
    else {
        Write-Host "Skipped $AgentName skill install because $HomeDir does not exist."
    }
}

Install-Skill -AgentName "Claude" -HomeDir (Join-Path $HOME ".claude")

$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
Install-Skill -AgentName "Codex" -HomeDir $codexHome

Write-Host ""
Write-Host "Install complete."
Write-Host "CLI script location: $userBin\jn.exe"

$pathEntries = @($env:PATH -split ';') | ForEach-Object { $_.TrimEnd('\') }
if ($pathEntries -notcontains $userBin.TrimEnd('\')) {
    Write-Host ""
    Write-Host "Add this to your user PATH if 'jn' is not found in a new PowerShell window:"
    Write-Host "  $userBin"
}

Write-Host ""
Write-Host "Next step:"
Write-Host "  [System.Environment]::SetEnvironmentVariable(""JOBNIMBUS_API_KEY"", ""your-api-key"", ""User"")"
Write-Host "  jn --help"
