# RoboCopy Manager & GoodSync Automation Engine

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%20Windows%2011%20%7C%20Server-0078D6?style=flat-square&logo=windows&logoColor=white)](https://github.com/pedropaivaf/RoboCopyManager)
[![PowerShell](https://img.shields.io/badge/PowerShell-5.1%20%7C%207%2B-5391FE?style=flat-square&logo=powershell&logoColor=white)](https://github.com/pedropaivaf/RoboCopyManager)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://github.com/pedropaivaf/RoboCopyManager)
[![Tests](https://img.shields.io/badge/Tests-137%2F137%20Passing-brightgreen?style=flat-square)](https://github.com/pedropaivaf/RoboCopyManager)
[![Speed](https://img.shields.io/badge/Engine-Native%20Kernel%20%2FMT%3A128-orange?style=flat-square)](https://github.com/pedropaivaf/RoboCopyManager)
[![Architecture](https://img.shields.io/badge/Architecture-GUI%20%2B%20TUI%20%2B%20CLI-purple?style=flat-square)](https://github.com/pedropaivaf/RoboCopyManager)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

> Sistema corporativo de alta performance para transferencia, replicacao, backup e sincronizacao bidirecional de dados no Windows. Combina a velocidade maxima do utilitario nativo de baixo nivel da Microsoft (`robocopy.exe`) com a usabilidade inteligente do **GoodSync** e a conveniencia de execucao remota em um clique no padrao **Win11Debloat**.

---

## Indice

- [Por que RoboCopy Manager?](#por-que-robocopy-manager)
- [Inicio Rapido em 3 Segundos](#inicio-rapido-em-3-segundos)
  - [Metodo 1: PowerShell Web One-Liner (Sem Baixar Nada)](#metodo-1-powershell-web-one-liner-sem-baixar-nada)
  - [Metodo 2: Aplicativo Desktop Executavel (GUI Portatil)](#metodo-2-aplicativo-desktop-executavel-gui-portatil)
  - [Metodo 3: Execucao Local em Lote (Run.bat)](#metodo-3-execucao-local-em-lote-runbat)
- [Demonstracao Visual do Terminal (TUI)](#demonstracao-visual-do-terminal-tui)
- [Recursos da Interface Grafica (GUI)](#recursos-da-interface-grafica-gui)
- [Console Colorido e Painel de Ocorrencias](#console-colorido-e-painel-de-ocorrencias)
- [Predefinicoes Basicas de Produtividade](#predefinicoes-basicas-de-produtividade)
- [Central de Sincronizacao GoodSync](#central-de-sincronizacao-goodsync)
  - [1. Espelhamento Rigido (Mirror / 1-Way Sync)](#1-espelhamento-rigido-mirror--1-way-sync)
  - [2. Atualizacao Sem Exclusao (Contribute / Update)](#2-atualizacao-sem-exclusao-contribute--update)
  - [3. Sincronizacao Bidirecional (2-Way Sync / Fusao)](#3-sincronizacao-bidirecional-2-way-sync--fusao)
  - [4. Mover Arquivos (Move / Cut & Paste)](#4-mover-arquivos-move--cut--paste)
  - [5. Sincronizacao com Filtros Avancados](#5-sincronizacao-com-filtros-avancados)
- [Analisar e Resolver Divergencias](#analisar-e-resolver-divergencias)
- [Flags Personalizadas (Parametros Livres)](#flags-personalizadas-parametros-livres)
- [Recursos Avancados e Corporativos](#recursos-avancados-e-corporativos)
- [Automacao e Agendamento de Tarefas (Task Scheduler)](#automacao-e-agendamento-de-tarefas-task-scheduler)
- [Referencia Completa de Parametros CLI](#referencia-completa-de-parametros-cli)
- [Tabela de Codigos de Saida do Robocopy](#tabela-de-codigos-de-saida-do-robocopy)
- [Estrutura do Repositorio](#estrutura-do-repositorio)
- [Garantia de Qualidade e Bateria de Testes](#garantia-de-qualidade-e-bateria-de-testes)
- [Compilacao de Executaveis com PyInstaller](#compilacao-de-executaveis-com-pyinstaller)
- [Licenca e Creditos](#licenca-e-creditos)

---

## Por que RoboCopy Manager?

Transferir terabytes de dados no Windows pelo Windows Explorer frequentemente resulta em travamentos, perdas de permissao NTFS, lentidao com milhares de arquivos pequenos e congelamentos se houver qualquer oscilacao de rede.

O Microsoft Robocopy nativo resolve esses problemas no nivel do kernel, mas exige memorizar dezenas de switches complexos e qualquer erro de digitacao com `/MIR` pode apagar um disco inteiro. Ferramentas comerciais como o GoodSync sao pagas, exigem instaladores pesados e operam servicos em segundo plano desnecessarios.

O **RoboCopy Manager** oferece o melhor dos dois mundos:

| Caracteristica | Windows Explorer | Robocopy Manual (CMD) | GoodSync Comercial | RoboCopy Manager |
| :--- | :---: | :---: | :---: | :---: |
| **Velocidade de Transferencia** | Baixa (1 thread) | Maxima (/MT) | Media-Alta | **Kernel Nativo Maximo (/MT:128)** |
| **Instalacao Necessaria** | Nao | Nao | Sim (Instalador pesado) | **Nao (Zero Instalacao / Portatil)** |
| **Execucao Direta via Web** | Nao | Nao | Nao | **Sim (Padrao Win11Debloat One-Liner)** |
| **Interface Grafica Desktop** | Basica | Nenhuma | Complexa | **Moderna, Limpa e Intuitiva** |
| **Temas Escuro e Claro** | Depende do SO | Nao | Limitado | **Alternancia Imediata Dark/Light** |
| **Botoes Informativos (i)** | Nao | Nao | Documentacao web | **Tooltips Contextuais Integrados** |
| **Sincronizacao 2-Way (Fusao)** | Nao | Exige scripts manuais | Sim | **Automatico em 2 Etapas Integradas** |
| **Lista o que esta diferente** | Nao | Exige ler o log | Sim (Analyze) | **Tabela com caminho, lado e tamanho** |
| **Escolher a acao de cada arquivo** | Nao | Nao | Sim | **Copiar A->B, B->A, Excluir ou Ignorar** |
| **Simulacao Segura (Dry-Run)** | Nao | `/L` manual | Analise previa | **1 Clique com Relatorio Completo** |
| **Parametros livres do Robocopy** | Nao | Sim (decorar tudo) | Limitado | **Campo de Flags Personalizadas com aviso** |
| **Preservacao Permissoes NTFS** | Incompleta | `/COPYALL` manual | Sim | **Ativacao Visual em 1 Clique** |
| **Modo Backup Privilegiado** | Nao | `/ZB` manual | Sim | **Suporte Nativo a `SeBackupPrivilege`** |
| **Custo / Licenca** | Embutido | Embutido | Proprietario Pago | **100% Gratuito e Open Source (MIT)** |

---

## Inicio Rapido em 3 Segundos

### Metodo 1: PowerShell Web One-Liner (Sem Baixar Nada)

Ideal para suporte remoto, administradores de TI ou usuarios que precisam rodar imediatamente em qualquer estacao sem realizar downloads manuais.

Abra o **PowerShell** (ou **Windows Terminal**) e execute:

```powershell
& ([scriptblock]::Create((irm "https://raw.githubusercontent.com/pedropaivaf/RoboCopyManager/main/RoboCopy.ps1")))
```

Ou a sintaxe direta:

```powershell
irm https://raw.githubusercontent.com/pedropaivaf/RoboCopyManager/main/RoboCopy.ps1 | iex
```

#### Como Funciona (Padrao Win11Debloat):
1. O comando faz a leitura do script `RoboCopy.ps1` diretamente da branch `main` do GitHub para a memoria RAM.
2. O script localiza ou baixa a versao oficial da aplicacao grafica (`RoboCopyManager.exe`) para o cache local do Windows (`%LOCALAPPDATA%\RoboCopyManager`).
3. Solicita elevacao administrativa UAC e **abre imediatamente a Interface Grafica completa (GUI Tkinter)** na tela do computador!
4. Em execucoes posteriores, a interface grafica abre instantaneamente em menos de 1 segundo utilizando o cache.
5. Caso deseje executar o menu em modo texto dentro do terminal, basta adicionar o parametro `-CLI`:
   ```powershell
   irm https://raw.githubusercontent.com/pedropaivaf/RoboCopyManager/main/RoboCopy.ps1 | iex -CLI
   ```

---

### Metodo 2: Aplicativo Desktop Executavel (GUI Portatil)

Para quem prefere uma aplicacao de janela rica, moderna e totalmente grafica:

1. Baixe o executavel direto na pasta [`dist/RoboCopyManager.exe`](dist/RoboCopyManager.exe).
2. Execute o arquivo com duplo clique.
3. O software abre imediatamente em tela cheia sem necessidade de instalar Python, bibliotecas ou runtimes externos. Pode ser copiado e rodado diretamente de um pendrive.

---

### Metodo 3: Execucao Local em Lote (Run.bat)

Caso voce tenha clonado o repositorio em sua maquina:

- De um duplo clique no arquivo `Run.bat`.
- O lote solicita privilegios administrativos via UAC e lanca o script PowerShell local com a politica de execucao liberada (`-ExecutionPolicy Bypass`).

---

## Demonstracao Visual do Terminal (TUI)

Ao executar o script pelo PowerShell, o menu interativo em modo texto organiza todo o fluxo de trabalho com foco em seguranca:

```
================================================================================
          ROBOCOPY MANAGER - CENTRAL DE SINCRONIZACAO E TRANSFERENCIA           
================================================================================
 Status UAC: [ADMINISTRADOR] | Kernel: Microsoft Robocopy
--------------------------------------------------------------------------------

 Origem : C:\Projetos\Desenvolvimento
 Destino: D:\Backup\Projetos

 ------------------- PREDEFINICOES BASICAS -------------------
 [1] Backup Seguro (Recomendado)  -> Copia novos/modificados sem apagar nada
 [2] Copia Rapida (/MT:16)       -> Alta velocidade para arquivos pequenos
 [3] Espelhamento Identico (/MIR) -> Destino vira clone exato da Origem
 [4] Mover Arquivos (/MOVE)      -> Transfere e recorta da pasta de origem

 ------------------- CENTRAL GOODSYNC -----------------------
 [5] Central de Sincronizacao    -> Espelhamento, Atualizacao, 2-Way e Filtros

 ------------------- CONTROLES E CONFIGURACOES --------------
 [6] Opcoes Avancadas (Custom)   -> Threads, Tentativas e Exclusoes Manuais
 [7] Alternar Modo Administrador -> Elevar sessao atual
 [8] Alterar Pastas             -> Redefinir diretorios de Origem / Destino

 [S] SIMULAR PRIMEIRO (Dry-Run)  -> Analisa sem alterar nenhum arquivo
 [I] INICIAR COPIA IMEDIATA      -> Executa a transferencia em tempo real
 [Q] Sair
--------------------------------------------------------------------------------
 Digite a opcao desejada: 
```

---

## Recursos da Interface Grafica (GUI)

A interface grafica foi projetada com arquitetura focada no usuario final e em equipes de suporte:

- **Alternancia Imediata de Tema**: Suporte completo a **Tema Escuro** (Dark Mode - fundo `#1E1E1E` para menor fadiga visual) e **Tema Claro** (Light Mode - alto contraste para ambientes iluminados) com preservacao de visibilidade de labels e botoes.
- **Botoes de Indice Contextual `(i)`**: Cada opcao e parametro possui um icone explicativo minimalista. Ao posicionar o mouse sobre ele, uma janela suspensa explica em linguagem simples o que a opcao faz, quando usar e quais riscos ela pode apresentar.
- **Console de Streaming em Tempo Real**: Monitor integrado com auto-scroll que exibe linha a linha a saida do Robocopy, incluindo percentual de transferencia, velocidade e tabela resumo final de arquivos copiados, ignorados e falhados.
- **Dialogos Nativos do Windows Explorer**: Botoes "Procurar..." que abrem a selecao nativa de pastas do Windows, alem de aceitar caminhos colados com ou sem aspas e caminhos de rede UNC (`\\servidor\compartilhamento`).
- **Validacao Proativa Contra Perda de Dados**: O sistema impede operacoes caso a Origem seja identica ao Destino, avisa se a pasta de origem nao existir e alerta com destaque vermelho antes de qualquer operacao destrutiva (`/MIR` ou `/MOVE`).
- **Botao de Ajuda do Status `?`**: Ao lado da mensagem final (ex: `Status: [2] Aviso`) existe um botao que abre a explicacao completa do codigo de saida: o que cada bit significa, qual o impacto real nos seus arquivos, o que fazer para resolver e qual foi o resultado de cada etapa executada.
- **Atalho "Resolver Divergencias"**: Quando a execucao termina com arquivos extras ou incompativeis, um botao aparece no rodape e leva direto para a analise item a item na Central de Sincronizacao.

---

## Console Colorido e Painel de Ocorrencias

O monitor de execucao possui duas abas complementares:

**Aba "Console ao Vivo"** - a saida completa do Robocopy com destaque de sintaxe por tipo de evento (funciona tanto em Windows em portugues quanto em ingles):

| Cor | Tipo de linha | Exemplo da saida do Robocopy |
| :--- | :--- | :--- |
| Verde | Arquivo novo copiado | `Novo Arquivo` / `New File` |
| Azul claro | Arquivo atualizado | `Mais Recente` / `Newer` / `Changed` |
| Amarelo | Item extra no destino | `*Arquivo EXTRA` / `*EXTRA File` / `*EXTRA Dir` |
| Laranja | Item incompativel | `*INCOMPATIVEL` / `*Mismatch` |
| Vermelho | Falha ou acesso negado | `ERRO 5 (0x00000005)` / `Acesso negado` |
| Azul | Cabecalho de etapa | `>>> [ETAPA 1 DE 2]` |

**Aba "Ocorrencias"** - uma tabela que recolhe automaticamente do log **apenas o que exige decisao**, sem que voce precise procurar no meio do texto:

```
+--------------------------------------------------------------------------------------+
| Tipo de Ocorrencia | Tamanho  | Caminho completo do item                              |
+--------------------------------------------------------------------------------------+
| Arquivo EXTRA      |   512 B  | D:\Destino\relatorio_antigo.bak                        |
| Pasta EXTRA        |      -   | D:\Destino\cache_temporario\                           |
| Incompatibilidade  |      -   | D:\Destino\config                                     |
| FALHA              |  1,2 MB  | C:\Origem\banco_em_uso.mdb                            |
+--------------------------------------------------------------------------------------+
Total: 4  |  Arquivos/Pastas EXTRA: 2  |  Falhas e acessos negados: 1  |  Incompatibilidades: 1
```

- Filtros de um clique: **Todas**, **Arquivos EXTRA**, **Falhas** e **Incompatibilidades**.
- **Exportar CSV** gera a planilha com tipo, tamanho, caminho e a linha original do Robocopy.
- **Abrir Pasta** (ou duplo clique) localiza o item diretamente no Windows Explorer.
- Mensagens de detalhe como `Acesso negado.` sao anexadas ao erro correspondente, e nao viram linhas soltas.

---

## Predefinicoes Basicas de Produtividade

Para 90% das tarefas cotidianas, basta selecionar a Origem, o Destino e escolher um dos 4 fluxos basicos:

### 1. Backup Seguro (Recomendado)
- **O que faz**: Copia apenas arquivos novos ou que tenham data de modificacao mais recente que os arquivos existentes na pasta de destino. **Jamais apaga nada** na pasta de destino.
- **Parametros Robocopy**: `/E /XO /R:1 /W:3`
- **Uso ideal**: Backups diarios, pastas de documentos e salvamento em discos externos sem risco de perda de historico.

### 2. Copia Rapida
- **O que faz**: Otimiza a velocidade de transferencia usando processamento multithread concorrente (16 threads paralelas) e ignora diretorios vazios.
- **Parametros Robocopy**: `/E /MT:16 /R:1 /W:3`
- **Uso ideal**: Transferencia massiva de fotos, codigos-fonte, bibliotecas de audio e milhares de pequenos arquivos.

### 3. Espelhamento Identico
- **O que faz**: Torna a pasta de destino uma copia 100% identica a pasta de origem. Se um arquivo for apagado na origem, ele **sera apagado no destino**. Arquivos extras que existam apenas no destino serao expurgados.
- **Parametros Robocopy**: `/MIR /R:1 /W:3`
- **Uso ideal**: Clones de discos de trabalho, replicacao exata de servidores de arquivos e sincronizacao mestre-escravo.

### 4. Mover Arquivos
- **O que faz**: Transfere os arquivos para a pasta de destino e, imediatamente apos a confirmacao de escrita correta, remove os arquivos da pasta de origem (equivalente ao recortar e colar do Windows Explorer, porem com verificacao de integridade).
- **Parametros Robocopy**: `/MOVE /E /R:1 /W:3`
- **Uso ideal**: Liberacao de espaco em disco, arquivamento de logs e organizacao de pastas de downloads.

### 5. Sincronizacao Dupla (2 vias, em um clique)
- **O que faz**: Com um unico clique executa a rotina completa em duas etapas automaticas: **Etapa 1 (Origem -> Destino)** e **Etapa 2 (Destino -> Origem)**, ambas com `/XO` (somente o que for mais novo). Nenhum arquivo e apagado em nenhum dos lados.
- **Parametros Robocopy**: `/E /XO /R:3 /W:5` aplicados nas duas direcoes.
- **Status final**: o rodape exibe o **resultado consolidado** das duas etapas. Se a Etapa 1 apontou arquivos extras e a Etapa 2 trouxe esses arquivos de volta, a divergencia foi resolvida e o status final indica sucesso completo em vez de continuar avisando sobre pendencias.
- **Uso ideal**: notebook e servidor, dois computadores da mesma equipe, pasta local e pendrive usados de forma independente.

> O mesmo modo tambem esta disponivel como caixa de selecao em **Opcoes Avancadas > Estrutura e Modos** e pelo parametro `--two-way` no terminal.

---

## Central de Sincronizacao GoodSync

Ao clicar no botao **"Sincronizar Pastas (Modo GoodSync)"**, uma interface especializada e apresentada, trazendo as 5 topologias classicas de sincronizacao de dados:

```
+-----------------------------------------------------------------------------+
|                         TOPOLOGIAS DE SINCRONIZACAO                         |
+-----------------------------------------------------------------------------+

1. ESPELHAMENTO RIGIDO (1-Way Mirror):
   [ Origem ] -----------------( /MIR /V /TS /FP )----------------> [ Destino ]
   (Destino e clonado. Arquivos apagados na Origem sao excluidos no Destino)

2. ATUALIZACAO SEM EXCLUSAO (Contribute / Update):
   [ Origem ] ----------------------( /E /XO )--------------------> [ Destino ]
   (Novidades vao para o Destino. Arquivos existentes NUNCA sao apagados)

3. SINCRONIZACAO BIDIRECIONAL (2-Way Sync / Fusao):
   [ Pasta A ] <=========( Etapa 1: A -> B com /E /XO )==========> [ Pasta B ]
   [ Pasta A ] <=========( Etapa 2: B -> A com /E /XO )==========> [ Pasta B ]
   (Harmonizacao total das duas pastas sem nenhuma perda de dados)

4. MOVER ARQUIVOS (Cut & Paste Seguro):
   [ Origem ] --------------------( /E /MOVE )--------------------> [ Destino ]
   (Transfere para o Destino e limpa os arquivos processados na Origem)

5. SINCRONIZACAO COM FILTROS:
   [ Origem ] ---------( /XF *.tmp /XD .git /MAX:500MB )----------> [ Destino ]
   (Aplica regras refinadas de extensao, pastas ignoradas e limites de tamanho)
```

### 1. Espelhamento Rigido (Mirror / 1-Way Sync)
- **Equivalente GoodSync**: 1-Way Sync with Delete.
- **Comportamento**: A Origem e a fonte absoluta da verdade. Qualquer item excluido na origem e removido no destino para evitar acumulo de arquivos obsoletos.
- **Flags**: `/MIR /R:3 /W:5 /V /TS /FP`

### 2. Atualizacao Sem Exclusao (Contribute / Update)
- **Equivalente GoodSync**: Contribute Sync (1-Way without Delete).
- **Comportamento**: Apenas envia novidades da Origem para o Destino. Se voce apagar um arquivo na Origem, ele continuara preservado intacto no Destino.
- **Flags**: `/E /XO /R:3 /W:5`

### 3. Sincronizacao Bidirecional (2-Way Sync / Fusao)
- **Equivalente GoodSync**: 2-Way Synchronization.
- **Comportamento**: Harmoniza duas pastas que sofreram alteracoes independentes atraves de um pipeline automatizado em 2 etapas:
  - **Etapa 1**: Varre a Pasta A e envia todos os arquivos novos e mais recentes para a Pasta B (`A -> B /E /XO`).
  - **Etapa 2**: Varre a Pasta B e envia todos os arquivos novos e mais recentes de volta para a Pasta A (`B -> A /E /XO`).
- **Resultado**: Ambas as pastas terminam com o conjunto completo e atualizado de todos os arquivos, sem que nenhum arquivo seja apagado em nenhum dos lados.

### 4. Mover Arquivos (Move / Cut & Paste)
- **Equivalente GoodSync**: Move / Archive Job.
- **Comportamento**: Transfere toda a estrutura de subpastas e apaga os arquivos da origem apenas apos a confirmacao de gravacao segura no destino.
- **Flags**: `/E /MOVE /R:3 /W:5`

### 5. Sincronizacao com Filtros Avancados
- Permite definir extensoes a serem ignoradas (`/XF *.tmp *.bak *.log *.iso`).
- Permite definir nomes de pastas a serem ignoradas (`/XD "node_modules" ".git" "cache"`).
- Suporta limitacao de tamanho maximo de arquivo (`/MAX:<bytes>`).
- Suporta selecao por idade minima ou maxima de modificacao (`/MINAGE:<dias>`).

---

## Analisar e Resolver Divergencias

Saber que "existem divergencias" nao resolve nada se o programa nao diz **quais arquivos**, **em que caminho** e **o que fazer com cada um**. E exatamente isso que o painel **Analisar e Resolver Divergencias**, dentro da Central de Sincronizacao, entrega:

```
1. ANALISAR  ->  2. REVISAR E AJUSTAR AS ACOES  ->  3. APLICAR
```

### Passo 1 - Analisar (nao altera nada)

O botao **"Analisar Diferencas (nao altera nada)"** roda o Robocopy em modo **somente-listagem** (`/L /MIR /FP /BYTES`). O `/MIR` combinado com `/L` e o que faz o Robocopy **relatar** tambem os itens que existem apenas no destino, sem apagar coisa alguma: nenhum arquivo e copiado, movido ou excluido nessa etapa.

### Passo 2 - Revisar item a item

O resultado vira uma tabela com uma linha por divergencia:

```
+-------------------------------------------------------------------------------------------------+
| Acao a executar      | Situacao encontrada    | Existe em | Tamanho | Caminho                    |
+-------------------------------------------------------------------------------------------------+
| Copiar para o Destino| Novo Arquivo           | Origem    | 1,0 KB  | relatorio.docx             |
| Copiar para o Destino| Mais recente na origem | Origem    | 20,0 KB | sub\planilha.xlsx          |
| Copiar para a Origem | Mais antigo na origem  | Origem    | 4,0 KB  | notas.txt                  |
| Copiar para a Origem | Arquivo EXTRA          | Destino   | 512 B   | antigo.bak                 |
| Copiar para a Origem | Pasta EXTRA            | Destino   |    -    | lixo\                      |
| Ignorar              | Incompatibilidade      | Destino   |    -    | config                     |
+-------------------------------------------------------------------------------------------------+
Plano atual: 2 -> destino | 3 -> origem | 0 exclusoes | 1 ignorado
```

| Situacao | O que significa na pratica |
| :--- | :--- |
| **Novo Arquivo / Nova Pasta** | Existe so na origem e ainda nao foi para o destino. |
| **Mais recente na origem** | Existe dos dois lados, mas a versao da origem e mais nova. |
| **Mais antigo na origem** | Existe dos dois lados, e quem esta mais novo e o **destino**. |
| **Conteudo alterado** | Mesmo horario nos dois lados, porem tamanho/conteudo diferente. |
| **Arquivo EXTRA / Pasta EXTRA** | Existe so no destino: foi apagado da origem ou criado direto no destino. |
| **Incompatibilidade** | O mesmo nome e arquivo de um lado e pasta do outro. Exige renomeacao manual. |

Recursos da tabela:

- **Selecionar uma linha** mostra a explicacao daquela situacao e **os caminhos completos dos dois lados** (incluindo onde o item ainda nao existe).
- **Acoes em lote** para os itens selecionados (Ctrl+clique ou Shift+clique): *Copiar para o Destino*, *Copiar para a Origem*, *Excluir do Destino* e *Ignorar*. **Duplo clique** alterna a acao de um item.
- Acoes impossiveis sao bloqueadas: um arquivo que so existe na origem nao pode ser "excluido do destino", e itens incompativeis so aceitam *Ignorar*.
- **Filtros**: Todas, So na Origem, So no Destino, Atualizacoes e Marcadas para excluir.
- **Restaurar sugestao do modo** devolve todas as acoes ao padrao do modo GoodSync selecionado (trocar de modo tambem re-sugere tudo automaticamente).
- **Exportar Lista CSV** gera a planilha com acao, situacao, lado, tamanho, caminho relativo e os dois caminhos absolutos.
- **Abrir no Explorer** localiza o item selecionado no Windows.

### Acao sugerida por modo

| Situacao | Espelhamento Rigido | Atualizacao sem Exclusao | Sincronizacao Bidirecional |
| :--- | :--- | :--- | :--- |
| Novo / Mais recente na origem | Copiar para o Destino | Copiar para o Destino | Copiar para o Destino |
| Mais antigo na origem | Copiar para o Destino | Ignorar | Copiar para a Origem |
| Arquivo / Pasta EXTRA | **Excluir do Destino** | Ignorar | Copiar para a Origem |
| Incompatibilidade | Ignorar | Ignorar | Ignorar |

### Passo 3 - Aplicar

**"Aplicar Acoes Selecionadas"** executa exatamente o que esta na coluna *Acao*, e exibe antes um resumo com a contagem de copias e a lista dos itens que serao apagados. A execucao segue regras de seguranca:

- Arquivos da mesma pasta sao agrupados em uma unica chamada do Robocopy, com apenas os nomes escolhidos - **sem `/MIR`, sem `/PURGE` e sem `/MOVE`**.
- **Todas as copias acontecem antes de qualquer exclusao.**
- Itens dentro de uma pasta que sera apagada (ou copiada inteira) nao sao processados duas vezes.
- Ao final o sistema oferece uma nova analise para confirmar que nao sobrou divergencia.

> No terminal, o parametro `--analyze` imprime essa mesma lista de divergencias sem alterar nada.

---

## Flags Personalizadas (Parametros Livres)

Nem todo parametro do Robocopy tem uma caixa dedicada na tela. O campo **"Flags Personalizadas"** (disponivel em *Opcoes Avancadas > Comando Interno* e tambem dentro da Central de Sincronizacao) aceita qualquer argumento digitado, que e anexado ao final do comando exatamente como escrito.

Botoes de atalho adicionam e removem as flags mais pedidas:

| Flag | Para que serve |
| :--- | :--- |
| `/PURGE` | Apaga do destino os arquivos que nao existem mais na origem, sem espelhar o resto. |
| `/MIR` | Espelhamento completo (copia tudo e apaga o que nao esta na origem). |
| `/FFT` | Tolerancia de 2 segundos nos horarios - essencial para pendrives, NAS, Linux e FAT32. |
| `/Z` | Modo reiniciavel: continua a transferencia de onde parou se a rede cair. |
| `/XX` | Ignora completamente os arquivos extras do destino. |
| `/SL` | Copia links simbolicos como links, em vez do conteudo apontado. |
| `/NOSD` | Nao exibe o diretorio de origem no relatorio. |
| `/256` | Desativa o suporte a caminhos com mais de 256 caracteres. |

O campo valida o que foi digitado em tempo real e avisa em tres situacoes:

1. **Parametro que apaga arquivos** (`/MIR`, `/PURGE`, `/MOVE`, `/MOV`) - alem do aviso, uma confirmacao extra e exigida antes de iniciar.
2. **Parametro ja controlado pela interface** (`/MT`, `/R`, `/W`, `/COPY`, `/LOG`...) - avisa sobre o risco de conflito com o valor definido na tela.
3. **Texto que nao parece uma flag** (nao comeca com `/`).

Pelo terminal, o mesmo recurso esta em `--extra-args` (ou `-x`).

---

## Recursos Avancados e Corporativos

### Multi-threading de Alta Densidade (`/MT:32` e `/MT:64`)
Por padrao, o Windows copia arquivos sequencialmente (1 de cada vez). O RoboCopy Manager permite ativar ate 128 threads concorrentes, saturando barramentos SSD NVMe, redes de 10Gbps e eliminando o gargalo historico de copiar arvores com mais de 100.000 arquivos pequenos.

### Preservacao Total de Permissoes NTFS (`/COPYALL`)
Essencial para ambientes empresariais com Active Directory e servidores de arquivos Windows Server. O switch `/COPYALL` clona:
- **D**: Dados do arquivo
- **A**: Atributos (Somente leitura, oculto, sistema, compactado)
- **T**: Timestamps (Data de criacao, modificacao e ultimo acesso)
- **S**: Listas de Controle de Acesso de Seguranca (NTFS ACLs)
- **O**: Informacoes de Dono (Owner)
- **U**: Informacoes de Auditoria (SACLs)

### Modo Backup Privilegiado (`/ZB`)
Em operacoes comuns, se um arquivo tiver permissoes de leitura negadas na ACL ou estiver temporariamente em uso por outro processo, a copia comum falha com erro "Acesso Negado".
O parametro `/ZB` instrui o Robocopy a tentar a leitura normal e, caso encontre bloqueio de permissao, ativa a prerrogativa do Windows `SeBackupPrivilege`, ignorando a ACL e garantindo a continuidade ininterrupta do backup.

### Resiliencia de Rede (`/R` e `/W`)
O Robocopy nativo do Windows vem configurado de fabrica para tentar 1 milhao de vezes (`/R:1000000`) esperando 30 segundos (`/W:30`) a cada erro, o que congela operacoes indefinidamente se um unico arquivo estiver corrompido. O RoboCopy Manager padroniza valores inteligentes:
- Modo Rapido: `/R:1 /W:3` (1 tentativa, aguarda 3 segundos).
- Modo GoodSync Corporativo: `/R:3 /W:5` (3 tentativas, aguarda 5 segundos).

### Modo Simulacao Dry-Run (`/L`)
Permite inspecionar com seguranca o que exatamente aconteceria antes de executar uma copia critica. Todas as pastas sao analisadas e listadas no log, mas nenhum arquivo e gravado, movido ou apagado.

---

## Automacao e Agendamento de Tarefas (Task Scheduler)

Voce pode agendar backups diarios ou sincronizacoes silenciosas no **Agendador de Tarefas do Windows** utilizando o script autônomo `RoboCopy.ps1`:

### Exemplo 1: Backup Diario Noturno Silencioso
```powershell
powershell.exe -ExecutionPolicy Bypass -File "C:\Scripts\RoboCopy.ps1" -Source "C:\Dados" -Destination "D:\BackupDiario" -Mode backup -NonInteractive
```

### Exemplo 2: Espelhamento de Servidor de Arquivos com 32 Threads
```powershell
powershell.exe -ExecutionPolicy Bypass -File "C:\Scripts\RoboCopy.ps1" -Source "\\servidor\compartilhamento" -Destination "E:\Replicacao" -Mode goodsync_mirror -Threads 32 -NonInteractive
```

### Exemplo 3: Sincronizacao Bidirecional (2-Way) entre Notebook e Servidor
```powershell
powershell.exe -ExecutionPolicy Bypass -File "C:\Scripts\RoboCopy.ps1" -Source "C:\Documentos" -Destination "\\nas\documentos" -Mode goodsync_two_way -NonInteractive
```

---

## Referencia Completa de Parametros CLI

O script `RoboCopy.ps1` e o utilitario `RoboCopyCLI.exe` aceitam os seguintes argumentos de linha de comando:

| Parametro | Tipo | Padrao | Descricao / Exemplo |
| :--- | :---: | :---: | :--- |
| `-Source` | String | `""` | Diretorio de origem (ex: `C:\Origem` ou `\\servidor\pasta`). |
| `-Destination` | String | `""` | Diretorio de destino (ex: `D:\Destino`). |
| `-Mode` | String | `""` | Modo de execucao: `backup`, `fast`, `mirror`, `move`, `goodsync_mirror`, `goodsync_update`, `goodsync_two_way`, `goodsync_move`, `goodsync_filter`. |
| `-DryRun` | Switch | `False` | Ativa simulacao sem gravacao (`/L`). |
| `-NonInteractive` | Switch | `False` | Nao aguarda confirmacao do usuario; encerra apos concluir. |
| `-RequireAdmin` | Switch | `False` | Solicita elevacao UAC antes de executar qualquer acao. |
| `-Threads` | Inteiro | `8` | Quantidade de threads simultaneas (`/MT`, de 1 a 128). |
| `-Retries` | Inteiro | `1` | Quantidade de tentativas em caso de erro (`/R`). |
| `-WaitSec` | Inteiro | `3` | Tempo de espera em segundos entre tentativas (`/W`). |
| `-ExcludeFiles` | String | `""` | Lista de extensoes ou arquivos a ignorar (ex: `*.tmp, *.bak`). |
| `-ExcludeDirs` | String | `""` | Lista de pastas a ignorar (ex: `node_modules, .git, temp`). |

Ja o terminal em Python (`robocopy_cli.py` / `RoboCopyCLI.exe`) aceita:

| Parametro | Descricao / Exemplo |
| :--- | :--- |
| `source` / `destination` | Pastas de origem e destino (posicionais). Sem eles, abre o menu interativo. |
| `--mode` | `backup`, `fast`, `mirror`, `move`, `goodsync_mirror`, `goodsync_update`, `goodsync_two_way`, `goodsync_move`, `goodsync_filter`. |
| `--dry-run`, `-L` | Simula sem gravar nada (`/L`). |
| `--two-way` | **Sincronizacao dupla**: executa Origem -> Destino e depois Destino -> Origem, com status consolidado. |
| `--analyze` | **Lista as divergencias** entre as pastas (quais arquivos, em que caminho, de que lado) sem alterar nada. |
| `--extra-args`, `-x` | **Flags personalizadas** do Robocopy (ex: `-x "/FFT /Z"`), com aviso para parametros destrutivos. |
| `--threads` | Threads simultaneas (`/MT`). |
| `--exclude-files`, `-xf` | Arquivos/extensoes a ignorar (`/XF`). |
| `--exclude-dirs`, `-xd` | Pastas a ignorar (`/XD`). |
| `--admin` | Solicita elevacao de Administrador imediatamente. |

```bash
# Ver o que esta diferente entre as duas pastas, sem tocar em nada
python robocopy_cli.py C:\Origem D:\Destino --analyze

# Sincronizacao dupla em um comando, com tolerancia de horario para pendrive
python robocopy_cli.py C:\Origem E:\Pendrive --two-way -x "/FFT"
```

A saida ao vivo no terminal tambem sai colorida por tipo de evento, e ao final o CLI imprime a lista de ocorrencias, o resultado de cada etapa e a explicacao completa do codigo de saida.

---

## Tabela de Codigos de Saida do Robocopy

Diferente de comandos tradicionais onde qualquer codigo diferente de zero e um erro fatal, o utilitario Robocopy da Microsoft utiliza uma mascara de bits inteligente para reportar status detalhado:

| Codigo de Saida | Significado Oficial | Classificacao no RoboCopy Manager |
| :---: | :--- | :--- |
| **0** | Nenhum arquivo copiado. Origem e Destino ja estavam 100% sincronizados. | **Sucesso (Sincronizado)** |
| **1** | Um ou mais arquivos foram copiados com sucesso para o destino. | **Sucesso (Arquivos Copiados)** |
| **2** | Foram detectados arquivos extras no destino que nao existem na origem. | **Sucesso (Arquivos Extras Detectados)** |
| **3** | Arquivos foram copiados e arquivos extras estavam presentes. | **Sucesso (Copia e Extras Processados)** |
| **4** | Alguns arquivos ou diretorios foram incompatíveis ou desconsiderados. | **Aviso (Inconsistencias Menores)** |
| **8** | Alguns arquivos falharam durante a tentativa de copia (travados ou sem permissao). | **Falha Parcial (Verifique o Log)** |
| **16** | Erro fatal. Robocopy nao conseguiu acessar a origem, destino ou parametros invalidos. | **Erro Fatal (Acesso ou Sintaxe)** |

> O RoboCopy Manager analisa e traduz automaticamente esses codigos, informando ao usuario em linguagem clara o desfecho exato da operacao.

O codigo e uma **soma de sinalizadores**: `3` significa `1` (arquivos copiados) **+** `2` (arquivos extras detectados). O botao `?` ao lado do status decompoe essa soma, explica o impacto de cada bit e sugere o que fazer.

**Consolidacao em operacoes de varias etapas**: na sincronizacao dupla, os codigos das duas etapas sao unidos em um unico resultado. Como a Etapa 2 copia de volta os arquivos que a Etapa 1 apontou como extras, o sinalizador `2` deixa de ser reportado quando as duas etapas terminam sem falha - o status final passa a indicar sucesso completo:

| Etapa 1 | Etapa 2 | Status consolidado |
| :---: | :---: | :--- |
| `2` (extras no destino) | `1` (copiados de volta) | **`1` Sucesso** - a divergencia foi resolvida pela etapa seguinte |
| `3` | `3` | **`1` Sucesso** |
| `6` (extras + incompativeis) | `1` | **`5`** - a incompatibilidade continua exigindo decisao manual |
| `2` | `8` (falha de copia) | **`10`** - houve falha real, nada e descontado |

O detalhamento etapa a etapa continua visivel no console, no botao `?` e no rodape (`resultado consolidado de 2 etapas`).

---

## Estrutura do Repositorio

```
RoboCopyManager/
|-- assets/
|   |-- app_icon.ico               # Icone da aplicacao desktop
|   |-- desktop_icon.ico           # Icone oficial dos atalhos da area de trabalho
|   +-- desktop_icon.png           # Arte em alta resolucao
|-- dist/
|   |-- COMO_USAR.txt              # Guia para distribuicao portatil
|   |-- COMO_USAR_TERMINAL.txt     # Guia detalhado da versao terminal e web
|   |-- RoboCopy.ps1               # Script PowerShell autonomo para distribuicao
|   |-- RoboCopyCLI.exe            # Executavel portatil de linha de comando
|   |-- RoboCopyManager.exe        # Aplicativo executavel desktop completo (GUI)
|   |-- Run.bat                    # Inicializador rapido em lote com UAC
|   +-- run-cli.ps1                # Launcher complementar
|-- tests/
|   |-- test_audit_all_options.py  # Auditoria completa de todas as flags e modos
|   |-- test_cli_integration.py    # Testes de integracao da interface TUI/CLI
|   |-- test_gui_integration.py    # Testes visuais da GUI, widgets e alternancia Dark/Light
|   |-- test_powershell_script.py  # Testes sintaticos e funcionais do RoboCopy.ps1
|   |-- test_robocopy.py           # Testes unitarios do motor robocopy_engine
|   +-- test_sync_center.py        # Testes da analise de divergencias, plano de acoes e exit codes
|-- build_exe.py                   # Script de compilacao da GUI com PyInstaller
|-- build_cli_exe.py               # Script de compilacao da CLI com PyInstaller
|-- presets.py                     # Dicionario centralizado de predefinicoes e tooltips
|-- pytest.ini                     # Configuracao do runner de testes automatizados
|-- requirements.txt               # Dependencias Python (pytest, pyinstaller)
|-- robocopy_cli.py                # Interface de linha de comando Python
|-- robocopy_engine.py             # Motor agnostico de geracao e execucao de comandos
|-- robocopy_gui.py                # Aplicativo desktop em Tkinter com suporte Dark/Light
|-- sync_analyzer.py               # Analise de divergencias, sugestao de acoes e execucao do plano
|-- RoboCopy.ps1                   # Script PowerShell autonomo de raiz (para Web One-Liner)
|-- Run.bat                        # Inicializador em lote da raiz
|-- .gitignore                     # Filtro de arquivos temporarios e caches
+-- README.md                      # Documentacao oficial completa
```

---

## Garantia de Qualidade e Bateria de Testes

O projeto conta com **137 testes automatizados**, assegurando que qualquer modificacao futura preserve a compatibilidade e a seguranca dos dados:

```bash
pytest tests/ -v
```

Exemplo de execucao da suite:
```
============================= test session starts =============================
platform win32 -- Python 3.10+, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\...\RoboCopyManager, configfile: pytest.ini
collected 137 items

tests\test_audit_all_options.py .............................            [ 21%]
tests\test_cli_integration.py ....                                       [ 24%]
tests\test_gui_integration.py .....................                      [ 40%]
tests\test_powershell_script.py .....                                    [ 43%]
tests\test_robocopy.py .......................                           [ 60%]
tests\test_sync_center.py .......................................................  [100%]

============================= 137 passed in 5.10s =============================
```

A suite cobre, entre outros pontos:

```
- Leitura da saida do Robocopy em portugues E em ingles
- Cabecalho do resumo (que contem as palavras FALHA e Incompativel) nao vira ocorrencia
- Consolidacao de exit codes em operacoes de duas etapas
- Analise de divergencias: caminho, lado, tamanho e acao sugerida por modo
- Plano de acoes: agrupamento por pasta, exclusoes sempre depois das copias,
  itens dentro de pasta apagada nao processados duas vezes
- Comando de cada etapa do plano nunca recebe /MIR, /PURGE ou /MOVE
- Criacao e exclusao reais em disco, inclusive em modo simulacao
```

---

## Compilacao de Executaveis com PyInstaller

Se voce deseja reconstruir os binarios portateis a partir do codigo-fonte:

1. Clone o repositorio:
   ```cmd
   git clone https://github.com/pedropaivaf/RoboCopyManager.git
   cd RoboCopyManager
   ```
2. Instale as dependencias:
   ```cmd
   pip install -r requirements.txt
   ```
3. Gere o executavel da Interface Grafica (GUI):
   ```cmd
   python build_exe.py
   ```
4. Gere o executavel do Console (CLI):
   ```cmd
   python build_cli_exe.py
   ```

Os executaveis gerados serao gravados na pasta `dist/`.

---

## Licenca e Creditos

Desenvolvido por **Pedro Paiva**.

Distribuido sob a licenca **MIT**. Consulte o arquivo [LICENSE](LICENSE) para obter todos os termos de uso e distribuicao livre.
