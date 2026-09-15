<#
.SYNOPSIS
    RoboCopy Manager - Versão de Terminal Autônoma (Padrão Win11Debloat)
.DESCRIPTION
    Script PowerShell autônomo e interativo para transferência, backup e sincronização
    GoodSync no Windows 10 e 11. Pode ser executado localmente ou via web one-liner
    sem necessidade de download manual ou instalação de dependências.
.EXAMPLE
    irm https://raw.githubusercontent.com/pedropaivaf/RoboCopyManager/main/RoboCopy.ps1 | iex
.EXAMPLE
    & ([scriptblock]::Create((irm "https://raw.githubusercontent.com/pedropaivaf/RoboCopyManager/main/RoboCopy.ps1"))) -CLI
.EXAMPLE
    .\RoboCopy.ps1 -Source "C:\Origem" -Destination "D:\Destino" -Mode backup -DryRun
.NOTES
    A interface grafica nao depende de executavel compilado: o script baixa os
    modulos Python da branch main para %LOCALAPPDATA%\RoboCopyManager\app e os
    executa com o Python da maquina, instalando o que faltar automaticamente.
#>

[CmdletBinding()]
param(
    [switch]$GUI,
    [switch]$CLI,
    [switch]$Console,
    [switch]$Update,
    [string]$Source = "",
    [string]$Destination = "",
    [ValidateSet("", "backup", "fast", "mirror", "move", "goodsync_mirror", "goodsync_update", "goodsync_two_way", "goodsync_move", "goodsync_filter")]
    [string]$Mode = "",
    [switch]$DryRun,
    [switch]$NonInteractive,
    [switch]$RequireAdmin,
    [int]$Threads = 8,
    [int]$Retries = 1,
    [int]$WaitSec = 3,
    [string]$ExcludeFiles = "",
    [string]$ExcludeDirs = ""
)

# ------------------------------------------------------------------------------
# 1. CHECAGEM E ELEVAÇÃO DE ADMINISTRADOR
# ------------------------------------------------------------------------------
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$global:IsAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

function Restart-ScriptAsAdmin {
    Write-Host "`n[RoboCopy Manager] Solicitando elevacao de Administrador (UAC)..." -ForegroundColor Cyan
    $argsList = @("-NoProfile", "-ExecutionPolicy", "Bypass")

    if ($PSCommandPath -and (Test-Path $PSCommandPath)) {
        $argsList += @("-File", "`"$PSCommandPath`"")
        if ($Source) { $argsList += @("-Source", "`"$Source`"") }
        if ($Destination) { $argsList += @("-Destination", "`"$Destination`"") }
        if ($Mode) { $argsList += @("-Mode", "`"$Mode`"") }
        if ($DryRun) { $argsList += "-DryRun" }
        if ($NonInteractive) { $argsList += "-NonInteractive" }
    } else {
        $remoteScriptUrl = "https://raw.githubusercontent.com/pedropaivaf/RoboCopyManager/main/RoboCopy.ps1"
        $argsList += @("-Command", "irm $remoteScriptUrl | iex")
    }

    try {
        Start-Process powershell.exe -Verb RunAs -ArgumentList $argsList
        exit
    } catch {
        Write-Host "[AVISO] Solicitacao de Administrador cancelada ou negada.`n" -ForegroundColor Red
    }
}

if ($RequireAdmin -and (-not $global:IsAdmin)) {
    Restart-ScriptAsAdmin
}

# ------------------------------------------------------------------------------
# 2. FUNÇÕES AUXILIARES DE INTERFACE E ENTRADA
# ------------------------------------------------------------------------------
function Show-Banner {
    Clear-Host
    Write-Host "==========================================================================" -ForegroundColor Cyan
    Write-Host "   ROBOCOPY MANAGER - MODO TERMINAL POWERSHELL (WIN11DEBLOAT STYLE)       " -ForegroundColor White -NoNewline
    if ($global:IsAdmin) {
        Write-Host "   [ADMINISTRADOR ATIVO]" -ForegroundColor Green
    } else {
        Write-Host "   [USUARIO COMUM]" -ForegroundColor Yellow
    }
    Write-Host "   Transferencia, Backup e Sincronizacao GoodSync no Windows 10 e 11      " -ForegroundColor Gray
    Write-Host "==========================================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Clean-PathString([string]$path) {
    if (-not $path) { return "" }
    $p = $path.Trim()
    if (($p.StartsWith('"') -and $p.EndsWith('"')) -or ($p.StartsWith("'") -and $p.EndsWith("'"))) {
        $p = $p.Substring(1, $p.Length - 2).Trim()
    }
    return $p.TrimEnd('\')
}

function Select-FolderDialog([string]$title) {
    try {
        Add-Type -AssemblyName System.Windows.Forms | Out-Null
        $fbd = New-Object System.Windows.Forms.FolderBrowserDialog
        $fbd.Description = $title
        $fbd.ShowNewFolderButton = $true
        if ($fbd.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            return $fbd.SelectedPath
        }
    } catch {}
    return ""
}

# ------------------------------------------------------------------------------
# BOOTSTRAP DO APLICATIVO (PADRAO Win11Debloat): CODIGO-FONTE DIRETO DO GITHUB
# ------------------------------------------------------------------------------
# Nao usa executavel compilado. O script baixa os modulos Python da branch main
# para o cache local e abre a interface grafica com o Python da maquina.
$global:RcmRepoRaw = "https://raw.githubusercontent.com/pedropaivaf/RoboCopyManager/main"
$global:RcmAppDir = "$env:LOCALAPPDATA\RoboCopyManager\app"

# Modulos que compoem a aplicacao.
$global:RcmModules = @(
    "robocopy_gui.py",
    "robocopy_engine.py",
    "sync_analyzer.py",
    "presets.py",
    "robocopy_cli.py"
)

$global:RcmAssets = @(
    "assets/desktop_icon.ico",
    "assets/app_icon.ico"
)

function Get-AppSource {
    <#
        Baixa a versao mais recente dos modulos Python direto da branch main.
        Os arquivos somam poucos KB, entao a atualizacao e sempre instantanea.
    #>
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    } catch { }

    if ($Update -and (Test-Path $global:RcmAppDir)) {
        Remove-Item $global:RcmAppDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    $assetsDir = Join-Path $global:RcmAppDir "assets"
    foreach ($dir in @($global:RcmAppDir, $assetsDir)) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }

    $previousProgress = $ProgressPreference
    $ProgressPreference = "SilentlyContinue"

    try {
        Write-Host "[RoboCopy Manager] Baixando a versao mais recente do GitHub..." -ForegroundColor Yellow

        # Parametro aleatorio evita o cache de 5 minutos do raw.githubusercontent.com
        $cacheBuster = [DateTime]::UtcNow.Ticks

        foreach ($module in $global:RcmModules) {
            $destination = Join-Path $global:RcmAppDir $module
            Invoke-WebRequest -Uri "$global:RcmRepoRaw/$module`?nocache=$cacheBuster" `
                              -OutFile $destination -UseBasicParsing -ErrorAction Stop
            Write-Host "   $module" -ForegroundColor DarkGray
        }

        # Os icones mudam raramente: baixados apenas na primeira vez.
        foreach ($asset in $global:RcmAssets) {
            $destination = Join-Path $global:RcmAppDir ($asset -replace "/", "\")
            if (Test-Path $destination) { continue }
            try {
                Invoke-WebRequest -Uri "$global:RcmRepoRaw/$asset" -OutFile $destination -UseBasicParsing -ErrorAction Stop
            } catch {
                # Sem icone a aplicacao abre normalmente.
            }
        }

        Write-Host "[RoboCopy Manager] Codigo-fonte atualizado em: $global:RcmAppDir" -ForegroundColor Gray
        return $global:RcmAppDir
    } catch {
        Write-Host "[ERRO] Falha ao baixar o codigo-fonte: $($_.Exception.Message)" -ForegroundColor Red
        # Se ja existe uma copia local de uma execucao anterior, usa ela.
        if (Test-Path (Join-Path $global:RcmAppDir "robocopy_gui.py")) {
            Write-Host "[INFO] Usando a copia local baixada anteriormente." -ForegroundColor Yellow
            return $global:RcmAppDir
        }
        return $null
    } finally {
        $ProgressPreference = $previousProgress
    }
}

function Find-Python {
    <# Localiza um Python 3 utilizavel, ignorando o atalho da Microsoft Store. #>
    $candidates = @()

    if (Get-Command "py.exe" -ErrorAction SilentlyContinue) {
        $resolved = & py.exe -3 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $resolved) { $candidates += $resolved.Trim() }
    }

    foreach ($name in @("python.exe", "python3.exe")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { $candidates += $command.Source }
    }

    $programsDir = "$env:LOCALAPPDATA\Programs\Python"
    if (Test-Path $programsDir) {
        $candidates += (Get-ChildItem $programsDir -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue |
                        ForEach-Object { $_.FullName })
    }

    foreach ($candidate in $candidates) {
        if (-not $candidate -or -not (Test-Path $candidate)) { continue }
        # O stub em WindowsApps apenas abre a Microsoft Store, nao executa nada.
        if ($candidate -like "*\WindowsApps\*") { continue }

        $major = & $candidate -c "import sys; print(sys.version_info[0])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $major -and $major.Trim() -eq "3") {
            return $candidate
        }
    }
    return $null
}

function Install-Python {
    <# Instala o Python pelo winget quando a maquina ainda nao tem. #>
    if (-not (Get-Command "winget.exe" -ErrorAction SilentlyContinue)) {
        return $null
    }

    Write-Host "[RoboCopy Manager] Python nao encontrado. Instalando pelo winget (so na primeira vez)..." -ForegroundColor Yellow
    & winget.exe install --id Python.Python.3.12 --exact --source winget `
                 --accept-package-agreements --accept-source-agreements --silent | Out-Null

    # O PATH da sessao atual nao e atualizado pelo instalador: recarrega do registro.
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"

    return (Find-Python)
}

function Ensure-PythonPackages([string]$python) {
    <# Garante customtkinter e pillow, as unicas dependencias da interface. #>
    & $python -c "import customtkinter, PIL" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { return $true }

    Write-Host "[RoboCopy Manager] Instalando as bibliotecas da interface (customtkinter)..." -ForegroundColor Yellow
    & $python -m pip install --quiet --disable-pip-version-check customtkinter pillow 2>$null | Out-Null

    & $python -c "import customtkinter, PIL" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        # Em Python instalado para todos os usuarios o pip pode exigir escopo de usuario.
        & $python -m pip install --quiet --disable-pip-version-check --user customtkinter pillow 2>$null | Out-Null
        & $python -c "import customtkinter, PIL" 2>$null | Out-Null
    }

    return ($LASTEXITCODE -eq 0)
}

function Resolve-PythonRuntime {
    <# Devolve o Python a ser usado, instalando-o se necessario. #>
    $python = Find-Python
    if (-not $python) { $python = Install-Python }

    if (-not $python) {
        Write-Host "`n[AVISO] Nao foi possivel localizar nem instalar o Python nesta maquina." -ForegroundColor Yellow
        Write-Host "        Instale em https://www.python.org/downloads/ (marque 'Add python.exe to PATH')" -ForegroundColor Yellow
        Write-Host "        ou execute:  winget install Python.Python.3.12`n" -ForegroundColor Yellow
        return $null
    }

    Write-Host "[RoboCopy Manager] Python encontrado: $python" -ForegroundColor Gray
    return $python
}

function Launch-GUIApp {
    Write-Host "`n==========================================================================" -ForegroundColor Cyan
    Write-Host "   ROBOCOPY MANAGER - INICIALIZANDO APLICATIVO GRAFICO (GUI)              " -ForegroundColor White
    Write-Host "==========================================================================" -ForegroundColor Cyan

    $python = Resolve-PythonRuntime
    if (-not $python) { return $false }

    $appDir = Get-AppSource
    if (-not $appDir) { return $false }

    if (-not (Ensure-PythonPackages $python)) {
        Write-Host "[ERRO] Nao foi possivel instalar as bibliotecas da interface grafica." -ForegroundColor Red
        Write-Host "[INFO] Alternando para o menu em modo terminal (TUI)...`n" -ForegroundColor Yellow
        return $false
    }

    # pythonw.exe abre a janela sem deixar um console preto aberto atras dela.
    $pythonw = Join-Path (Split-Path $python -Parent) "pythonw.exe"
    if (-not (Test-Path $pythonw)) { $pythonw = $python }

    $entryPoint = Join-Path $appDir "robocopy_gui.py"
    if (-not (Test-Path $entryPoint)) {
        Write-Host "[ERRO] Arquivo principal da interface nao encontrado." -ForegroundColor Red
        return $false
    }

    Write-Host "[RoboCopy Manager] Abrindo interface grafica..." -ForegroundColor Green
    try {
        # A propria aplicacao tem o botao "Executar como Administrador" quando precisar,
        # entao aqui ela abre sem forcar o UAC a cada inicializacao.
        Start-Process -FilePath $pythonw -ArgumentList "`"$entryPoint`"" -WorkingDirectory $appDir
        Write-Host "[RoboCopy Manager] Aplicativo carregado com sucesso!`n" -ForegroundColor Cyan
        return $true
    } catch {
        Write-Host "[ERRO] Nao foi possivel iniciar a interface grafica: $($_.Exception.Message)`n" -ForegroundColor Red
        return $false
    }
}

function Launch-PythonCLI {
    <#
        Abre o terminal interativo em Python (com analise de divergencias,
        log colorido e flags livres). Retorna $false para cair na TUI do
        proprio PowerShell quando o Python nao estiver disponivel.
    #>
    $python = Find-Python
    if (-not $python) { return $false }

    $appDir = Get-AppSource
    if (-not $appDir) { return $false }

    $entryPoint = Join-Path $appDir "robocopy_cli.py"
    if (-not (Test-Path $entryPoint)) { return $false }

    Push-Location $appDir
    try {
        & $python $entryPoint
        return $true
    } catch {
        return $false
    } finally {
        Pop-Location
    }
}


function Prompt-Folder([string]$label, [bool]$mustExist) {
    while ($true) {
        Write-Host "$($label):" -ForegroundColor Yellow
        Write-Host "  -> Digite/cole o caminho ou digite " -NoNewline -ForegroundColor Gray
        Write-Host "[B]" -ForegroundColor White -NoNewline
        Write-Host " para abrir a janela de selecao de pastas." -ForegroundColor Gray
        
        $inputVal = Read-Host "Caminho"
        if (-not $inputVal) {
            Write-Host "[AVISO] O caminho nao pode ser vazio.`n" -ForegroundColor Red
            continue
        }

        if ($inputVal.Trim().ToUpper() -eq "B") {
            $dialogPath = Select-FolderDialog $label
            if ($dialogPath) {
                Write-Host "Selecionado: $dialogPath`n" -ForegroundColor Green
                return $dialogPath
            } else {
                Write-Host "Selecao cancelada. Digite manualmente:`n" -ForegroundColor DarkYellow
                continue
            }
        }

        $cleaned = Clean-PathString $inputVal
        if ($mustExist -and (-not (Test-Path -LiteralPath $cleaned))) {
            Write-Host "[ERRO] A pasta de origem informada nao existe: '$cleaned'`n" -ForegroundColor Red
            continue
        }

        return $cleaned
    }
}

function Format-RobocopySummary([int]$exitCode) {
    Write-Host "`n==========================================================================" -ForegroundColor Cyan
    $statusColor = if ($exitCode -lt 8) { [ConsoleColor]::Green } else { [ConsoleColor]::Red }
    
    switch ($exitCode) {
        0 { Write-Host "   STATUS FINAL: [0] Sucesso - Nenhum arquivo precisou ser copiado (ja sincronizado)." -ForegroundColor $statusColor }
        1 { Write-Host "   STATUS FINAL: [1] Sucesso - Todos os arquivos foram copiados com sucesso." -ForegroundColor $statusColor }
        2 { Write-Host "   STATUS FINAL: [2] Aviso - Existem arquivos extras no destino." -ForegroundColor $statusColor }
        3 { Write-Host "   STATUS FINAL: [3] Sucesso Parcial - Arquivos copiados e arquivos extras detectados." -ForegroundColor $statusColor }
        4 { Write-Host "   STATUS FINAL: [4] Aviso - Arquivos com discrepancias detectados." -ForegroundColor $statusColor }
        5 { Write-Host "   STATUS FINAL: [5] Sucesso Parcial - Alguns arquivos copiados e discrepancias encontradas." -ForegroundColor $statusColor }
        6 { Write-Host "   STATUS FINAL: [6] Aviso - Arquivos extras e discrepancias presentes." -ForegroundColor $statusColor }
        7 { Write-Host "   STATUS FINAL: [7] Sucesso Parcial - Arquivos copiados e discrepancias detectadas." -ForegroundColor $statusColor }
        8 { Write-Host "   STATUS FINAL: [8] Falha de Copia - Alguns arquivos nao puderam ser copiados." -ForegroundColor $statusColor }
        16 { Write-Host "   STATUS FINAL: [16] Erro Critico - Acesso negado ou caminho invalido." -ForegroundColor $statusColor }
        Default {
            if ($exitCode -lt 8) {
                Write-Host "   STATUS FINAL: [$exitCode] Operacao concluida sem erros fatais." -ForegroundColor $statusColor
            } else {
                Write-Host "   STATUS FINAL: [$exitCode] Falha na copia do RoboCopy." -ForegroundColor $statusColor
            }
        }
    }
    Write-Host "==========================================================================`n" -ForegroundColor Cyan
}

# ------------------------------------------------------------------------------
# 3. CONSTRUÇÃO E EXECUÇÃO DO ROBOCOPY
# ------------------------------------------------------------------------------
function Execute-RobocopyTask([string]$src, [string]$dst, [string[]]$extraArgs, [bool]$isDryRun, [bool]$isTwoWay) {
    $src = Clean-PathString $src
    $dst = Clean-PathString $dst

    if (-not (Test-Path -LiteralPath $src)) {
        Write-Host "[ERRO] Pasta de origem inexistente: '$src'" -ForegroundColor Red
        return 16
    }

    if ($isTwoWay) {
        # Sincronização Bidirecional (Fusão 2-Way Sync) em 2 etapas
        Write-Host "`n>>> [ETAPA 1 DE 2]: Copiando novidades da Origem para o Destino..." -ForegroundColor Cyan
        $args1 = @("`"$src`"", "`"$dst`"", "*.*", "/E", "/XO", "/R:3", "/W:5", "/NP")
        if ($isDryRun) { $args1 += "/L" }
        $args1 += $extraArgs

        Write-Host "Comando: robocopy $($args1 -join ' ')`n" -ForegroundColor Gray
        & robocopy.exe @args1
        $code1 = $LASTEXITCODE

        if ($code1 -lt 8) {
            Write-Host "`n>>> [ETAPA 2 DE 2]: Copiando novidades do Destino para a Origem..." -ForegroundColor Cyan
            $args2 = @("`"$dst`"", "`"$src`"", "*.*", "/E", "/XO", "/R:3", "/W:5", "/NP")
            if ($isDryRun) { $args2 += "/L" }
            $args2 += $extraArgs

            Write-Host "Comando: robocopy $($args2 -join ' ')`n" -ForegroundColor Gray
            & robocopy.exe @args2
            $code2 = $LASTEXITCODE
            $finalCode = [Math]::Max($code1, $code2)
        } else {
            $finalCode = $code1
        }
    } else {
        $fullArgs = @("`"$src`"", "`"$dst`"", "*.*") + $extraArgs
        if ($isDryRun -and ($fullArgs -notcontains "/L")) {
            $fullArgs += "/L"
        }

        Write-Host "`nComando RoboCopy preparado:" -ForegroundColor Cyan
        Write-Host "  robocopy $($fullArgs -join ' ')`n" -ForegroundColor White

        Write-Host "------------------- [INICIO DA EXECUCAO ROBOCOPY] -------------------" -ForegroundColor Gray
        & robocopy.exe @fullArgs
        $finalCode = $LASTEXITCODE
        Write-Host "------------------- [FINAL DA EXECUCAO ROBOCOPY] -------------------`n" -ForegroundColor Gray
    }

    Format-RobocopySummary $finalCode
    return $finalCode
}

# ------------------------------------------------------------------------------
# 4. MODO INTERATIVO (TUI)
# ------------------------------------------------------------------------------
function Start-InteractiveUI {
    Show-Banner

    # 1. Pastas
    Write-Host "--- 1. DEFINICAO DE PASTAS ---" -ForegroundColor White
    $src = Prompt-Folder "Pasta de Origem (De onde copiar)" $true
    $dst = Prompt-Folder "Pasta de Destino (Para onde enviar)" $false

    # 2. Menu de Modos
    while ($true) {
        Write-Host "`n--- 2. ESCOLHA A OPERACAO ---" -ForegroundColor White
        Write-Host "  [1] Backup Seguro (Recomendado)     - Copia novos/alterados sem apagar nada" -ForegroundColor Cyan
        Write-Host "  [2] Copia Rapida (/MT:16)          - Velocidade maxima ignorando subpastas vazias" -ForegroundColor Cyan
        Write-Host "  [3] Espelhamento Identico (/MIR)    - Deixa o destino 100% igual a origem (apaga orfaos)" -ForegroundColor Cyan
        Write-Host "  [4] Mover Arquivos (/MOVE)         - Transfere e recorta da pasta de origem" -ForegroundColor Cyan
        Write-Host "  [5] Central GoodSync               - Submenu: Espelhamento, Atualizacao, 2-Way Sync (Fusao) e Filtros" -ForegroundColor Cyan
        Write-Host "  [6] Opcoes Avancadas Customizadas  - Definir threads, tentativas e exclusoes manuais" -ForegroundColor Cyan
        if (-not $global:IsAdmin) {
            Write-Host "  [7] Reiniciar como Administrador   - Solicita permissao de Admin para pastas protegidas" -ForegroundColor Yellow
        }
        Write-Host "  [0] Sair" -ForegroundColor White

        $choice = (Read-Host "`nOpcao desejada [1-7, 0]").Trim()
        $extraArgs = @("/COPY:DAT", "/DCOPY:DAT", "/XJ", "/NP")
        $isTwoWay = $false

        switch ($choice) {
            "1" {
                $extraArgs += @("/E", "/XO", "/R:1", "/W:3", "/MT:8")
                break
            }
            "2" {
                $extraArgs = @("/S", "/MT:16", "/R:1", "/W:2", "/COPY:DAT", "/DCOPY:DAT", "/XJ", "/NP")
                break
            }
            "3" {
                $confirm = Read-Host "ATENCAO: O modo espelhamento apagará arquivos no destino que foram deletados na origem. Confirmar? (S/N)"
                if ($confirm.Trim().ToUpper() -ne "S") { continue }
                $extraArgs += @("/MIR", "/R:1", "/W:3", "/MT:8")
                break
            }
            "4" {
                $confirm = Read-Host "ATENCAO: Os arquivos transferidos serao APAGADOS da pasta de origem. Confirmar mover? (S/N)"
                if ($confirm.Trim().ToUpper() -ne "S") { continue }
                $extraArgs += @("/MOVE", "/E", "/R:1", "/W:3", "/MT:8")
                break
            }
            "5" {
                # Submenu GoodSync
                Write-Host "`n--- Central de Sincronizacao GoodSync ---" -ForegroundColor White
                Write-Host "  [1] Espelhamento Rigido (Mirror / 1-Way Sync)     - /MIR /R:3 /W:5 /V /TS /FP" -ForegroundColor Cyan
                Write-Host "  [2] Atualizacao Sem Exclusao (Contribute / Update) - /E /XO /R:3 /W:5" -ForegroundColor Cyan
                Write-Host "  [3] Sincronizacao Bidirecional (2-Way Sync / Fusao) - Executa em 2 etapas A->B e B->A" -ForegroundColor Cyan
                Write-Host "  [4] Mover Arquivos GoodSync (Move / Cut & Paste)    - /E /MOVE /R:3 /W:5" -ForegroundColor Cyan
                Write-Host "  [5] Sincronizacao com Filtro de Extensao ou Tamanho - /E /MAX:n /XF ..." -ForegroundColor Cyan
                Write-Host "  [0] Voltar" -ForegroundColor White

                $gChoice = (Read-Host "`nSelecione o modo GoodSync [1-5, 0]").Trim()
                switch ($gChoice) {
                    "1" { $extraArgs += @("/MIR", "/R:3", "/W:5", "/V", "/TS", "/FP", "/MT:8"); break }
                    "2" { $extraArgs += @("/E", "/XO", "/R:3", "/W:5", "/MT:8"); break }
                    "3" { $isTwoWay = $true; break }
                    "4" { $extraArgs += @("/E", "/MOVE", "/R:3", "/W:5", "/MT:8"); break }
                    "5" {
                        $xf = Read-Host "Extensoes para excluir (Enter para padrao '*.tmp *.bak')"
                        if (-not $xf) { $xf = "*.tmp *.bak" }
                        $maxb = Read-Host "Tamanho maximo em bytes (Enter para padrao '52428800' = 50MB)"
                        if (-not $maxb) { $maxb = "52428800" }
                        $extraArgs += @("/E", "/XF", $xf, "/MAX:$maxb", "/R:3", "/W:5", "/MT:8")
                        break
                    }
                    Default { continue }
                }
                break
            }
            "6" {
                # Opções avançadas
                Write-Host "`n--- Opcoes Avancadas Customizadas ---" -ForegroundColor White
                $t = Read-Host "Numero de Threads (/MT: 1 a 64, padrao 8)"
                $tVal = if ($t -match '^\d+$' -and [int]$t -ge 1 -and [int]$t -le 64) { [int]$t } else { 8 }

                $r = Read-Host "Tentativas em arquivo bloqueado (/R: padrao 1)"
                $rVal = if ($r -match '^\d+$') { [int]$r } else { 1 }

                $w = Read-Host "Segundos de espera entre tentativas (/W: padrao 3)"
                $wVal = if ($w -match '^\d+$') { [int]$w } else { 3 }

                $xf = Read-Host "Arquivos para excluir (/XF ex: *.log *.tmp, Enter para nenhum)"
                $xd = Read-Host "Pastas para excluir (/XD ex: node_modules .git, Enter para nenhuma)"

                $extraArgs += @("/E", "/MT:$tVal", "/R:$rVal", "/W:$wVal")
                if ($xf) { $extraArgs += @("/XF", $xf) }
                if ($xd) { $extraArgs += @("/XD", $xd) }
                break
            }
            "7" {
                if (-not $global:IsAdmin) {
                    Restart-ScriptAsAdmin
                }
                continue
            }
            "0" {
                Write-Host "`nEncerrando RoboCopy Manager. Ate logo!`n" -ForegroundColor Cyan
                exit
            }
            Default {
                Write-Host "[Opcao invalida. Tente novamente.]" -ForegroundColor Red
                continue
            }
        }

        # 3. Confirmação de Execução
        Write-Host "`n--- 3. CONFIRMACAO DE EXECUCAO ---" -ForegroundColor White
        Write-Host "  [1] Iniciar Copia Imediata" -ForegroundColor Green
        Write-Host "  [2] Simular Primeiro (Dry-Run /L - Sem alterar arquivos)" -ForegroundColor Yellow
        Write-Host "  [0] Cancelar e Voltar" -ForegroundColor White

        $runChoice = (Read-Host "`nEscolha [1, 2 ou 0]").Trim()
        if ($runChoice -eq "1") {
            Execute-RobocopyTask $src $dst $extraArgs $false $isTwoWay
            break
        } elseif ($runChoice -eq "2") {
            Execute-RobocopyTask $src $dst $extraArgs $true $isTwoWay
            break
        }
    }

    Write-Host "Pressione qualquer tecla para sair..." -ForegroundColor Gray
    [void][System.Console]::ReadKey($true)
}

# ------------------------------------------------------------------------------
# 5. PONTO DE ENTRADA PRINCIPAL
# ------------------------------------------------------------------------------
if ($Source -and $Destination) {
    # Modo Direto por Parâmetros (Linha de Comando / Scripts Headless)
    $argsList = @("/COPY:DAT", "/DCOPY:DAT", "/XJ", "/NP")
    $isTwoWay = $false

    switch ($Mode) {
        "fast" { $argsList = @("/S", "/MT:$Threads", "/R:$Retries", "/W:$WaitSec", "/COPY:DAT", "/DCOPY:DAT", "/XJ", "/NP") }
        "mirror" { $argsList += @("/MIR", "/R:$Retries", "/W:$WaitSec", "/MT:$Threads") }
        "move" { $argsList += @("/MOVE", "/E", "/R:$Retries", "/W:$WaitSec", "/MT:$Threads") }
        "goodsync_mirror" { $argsList += @("/MIR", "/R:3", "/W:5", "/V", "/TS", "/FP", "/MT:$Threads") }
        "goodsync_update" { $argsList += @("/E", "/XO", "/R:3", "/W:5", "/MT:$Threads") }
        "goodsync_two_way" { $isTwoWay = $true }
        "goodsync_move" { $argsList += @("/E", "/MOVE", "/R:3", "/W:5", "/MT:$Threads") }
        "goodsync_filter" { $argsList += @("/E", "/R:3", "/W:5", "/MT:$Threads") }
        Default { $argsList += @("/E", "/XO", "/R:$Retries", "/W:$WaitSec", "/MT:$Threads") }
    }

    if ($ExcludeFiles) { $argsList += @("/XF", $ExcludeFiles) }
    if ($ExcludeDirs) { $argsList += @("/XD", $ExcludeDirs) }

    $exitCode = Execute-RobocopyTask $Source $Destination $argsList $DryRun $isTwoWay
    exit $exitCode
} elseif ($CLI -or $Console) {
    # Modo Interativo de Terminal Texto: usa o terminal completo em Python quando
    # disponivel e cai na TUI nativa do PowerShell caso contrario.
    if (-not (Launch-PythonCLI)) {
        Start-InteractiveUI
    }
} else {
    # Modo Padrão (Padrão Win11Debloat): Iniciar a Interface Gráfica Desktop (GUI)
    $launched = Launch-GUIApp
    if (-not $launched) {
        # Fallback de segurança caso a interface gráfica não possa ser aberta
        Start-InteractiveUI
    }
}
