# ==============================================================================
# RoboCopy Manager - Launcher de Terminal com Elevação Automática de Administrador
# Compatível com Windows PowerShell 5.1 e PowerShell 7+ no Windows 10 e 11
# ==============================================================================

[CmdletBinding()]
param(
    [string]$Source = "",
    [string]$Destination = "",
    [string]$Mode = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# 1. Verifica se já está executando com privilégios de Administrador
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "`n[AVISO] Privilegios de Administrador necessarios para acesso total." -ForegroundColor Yellow
    Write-Host "Solicitando elevacao (UAC)..." -ForegroundColor Cyan
    
    $argsList = @("-NoProfile", "-ExecutionPolicy", "Bypass")
    if ($PSCommandPath) {
        $argsList += @("-File", "`"$PSCommandPath`"")
        if ($Source) { $argsList += @("-Source", "`"$Source`"") }
        if ($Destination) { $argsList += @("-Destination", "`"$Destination`"") }
        if ($Mode) { $argsList += @("-Mode", "`"$Mode`"") }
        if ($DryRun) { $argsList += "-DryRun" }
    } else {
        # Execução direta via Web (irm ... | iex)
        $remoteScriptUrl = "https://raw.githubusercontent.com/pedro-paiva/RoboCopy/main/run-cli.ps1"
        $argsList += @("-Command", "irm $remoteScriptUrl | iex")
    }

    try {
        Start-Process powershell.exe -Verb RunAs -ArgumentList $argsList
    } catch {
        Write-Host "[ERRO] Elevacao cancelada pelo usuario." -ForegroundColor Red
    }
    exit
}

# 2. Localiza o executável ou o script Python
$scriptDir = Split-Path -Parent $PSCommandPath
if (-not $scriptDir) {
    $scriptDir = (Get-Location).Path
}

$exePath = Join-Path $scriptDir "dist\RoboCopyCLI.exe"
if (-not (Test-Path $exePath)) {
    $exePath = Join-Path $scriptDir "RoboCopyCLI.exe"
}

$pyScript = Join-Path $scriptDir "robocopy_cli.py"

# Parâmetros de encaminhamento caso tenham sido passados
$cliArgs = @()
if ($Source) { $cliArgs += "`"$Source`"" }
if ($Destination) { $cliArgs += "`"$Destination`"" }
if ($Mode) { $cliArgs += "--mode $Mode" }
if ($DryRun) { $cliArgs += "--dry-run" }

if (Test-Path $exePath) {
    # Executa o executável autônomo compilado
    & $exePath $cliArgs
} elseif ((Test-Path $pyScript) -and (Get-Command python -ErrorAction SilentlyContinue)) {
    # Executa o script Python
    python $pyScript $cliArgs
} else {
    # Modo Remoto / Portable Download (caso executado direto pela web sem clone local)
    $targetDir = Join-Path $env:LOCALAPPDATA "RoboCopyManager"
    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }
    $downloadExe = Join-Path $targetDir "RoboCopyCLI.exe"
    
    if (-not (Test-Path $downloadExe)) {
        Write-Host "Baixando RoboCopyCLI.exe portatil..." -ForegroundColor Cyan
        $downloadUrl = "https://github.com/pedro-paiva/RoboCopy/raw/main/dist/RoboCopyCLI.exe"
        Invoke-WebRequest -Uri $downloadUrl -OutFile $downloadExe -UseBasicParsing
    }
    
    & $downloadExe $cliArgs
}
