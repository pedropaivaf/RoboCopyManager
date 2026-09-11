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
    .\RoboCopy.ps1 -Source "C:\Origem" -Destination "D:\Destino" -Mode backup -DryRun
#>

[CmdletBinding()]
param(
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
if (-not $Source -or -not $Destination) {
    Start-InteractiveUI
} else {
    # Modo Direto por Parâmetros (Linha de Comando / Scripts)
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
}
