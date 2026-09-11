"""
Presets e Gerenciamento de Perfis de Configuração do RoboCopy.
Permite carregar predefinições de 1 clique ou salvar perfis customizados em JSON.
Visual corporativo e profissional sem elementos decorativos desnecessários.
"""

import json
import os
from typing import Dict, Any
from robocopy_engine import RobocopyConfig

PRESETS: Dict[str, Dict[str, Any]] = {
    "espelhamento": {
        "name": "Espelhamento Total (/MIR)",
        "description": "Replica integralmente a origem no destino. Remove no destino arquivos que foram apagados na origem.",
        "config": {
            "mirror": True,
            "copy_subdirs_empty": False,
            "copy_subdirs": False,
            "purge": False,
            "restartable_backup": False,
            "multi_threaded": 8,
            "retries": 1,
            "wait_time": 3,
            "exclude_junctions": True,
            "dry_run": False,
        }
    },
    "backup_incremental": {
        "name": "Backup Incremental (/E /XO)",
        "description": "Copia subdiretórios (inclusive vazios) e ignora arquivos que não sofreram alterações.",
        "config": {
            "mirror": False,
            "copy_subdirs_empty": True,
            "exclude_older": True,
            "purge": False,
            "restartable_backup": False,
            "multi_threaded": 8,
            "retries": 1,
            "wait_time": 3,
            "exclude_junctions": True,
            "dry_run": False,
        }
    },
    "copia_rapida": {
        "name": "Cópia Rápida (/S)",
        "description": "Copia subdiretórios que contenham conteúdo, ignorando pastas vazias.",
        "config": {
            "mirror": False,
            "copy_subdirs_empty": False,
            "copy_subdirs": True,
            "purge": False,
            "restartable_backup": False,
            "multi_threaded": 16,
            "retries": 1,
            "wait_time": 2,
            "exclude_junctions": True,
            "dry_run": False,
        }
    },
    "mover": {
        "name": "Mover Arquivos e Pastas (/MOVE)",
        "description": "Transfere arquivos e subdiretórios para o destino, removendo-os da origem após a conclusão.",
        "config": {
            "mirror": False,
            "copy_subdirs_empty": True,
            "move_all": True,
            "restartable_backup": False,
            "multi_threaded": 8,
            "retries": 1,
            "wait_time": 3,
            "exclude_junctions": True,
            "dry_run": False,
        }
    },
    "simulacao": {
        "name": "Simulação / Listagem (/L)",
        "description": "Executa o comando em modo de teste (dry run). Nenhum arquivo é alterado ou gravado no disco.",
        "config": {
            "dry_run": True,
            "mirror": True,
            "multi_threaded": 8,
            "retries": 1,
            "wait_time": 2,
            "exclude_junctions": True,
        }
    },
    "goodsync_mirror": {
        "name": "Espelhamento Rígido (1-Way Sync)",
        "description": "Cria uma réplica exata da origem no destino. Arquivos excluídos na origem são apagados no destino. Arquivos extras no destino são removidos.",
        "config": {
            "mirror": True,
            "copy_subdirs_empty": False,
            "copy_subdirs": False,
            "purge": False,
            "is_two_way_sync": False,
            "retries": 3,
            "wait_time": 5,
            "multi_threaded": 32,
            "verbose_timestamps": True,
            "exclude_junctions": True,
            "dry_run": False
        }
    },
    "goodsync_update": {
        "name": "Atualização Sem Exclusão (Update / Contribute)",
        "description": "Copia arquivos novos e modificados da origem para o destino. Arquivos deletados na origem NUNCA são apagados no destino.",
        "config": {
            "mirror": False,
            "copy_subdirs_empty": True,
            "exclude_older": True,
            "purge": False,
            "is_two_way_sync": False,
            "retries": 3,
            "wait_time": 5,
            "multi_threaded": 32,
            "exclude_junctions": True,
            "dry_run": False
        }
    },
    "goodsync_two_way": {
        "name": "Sincronização Bidirecional (2-Way Sync / Fusão)",
        "description": "Mescla o conteúdo de ambas as pastas em 2 etapas sequenciais (Origem ➔ Destino e Destino ➔ Origem). Ninguém perde arquivos.",
        "config": {
            "mirror": False,
            "copy_subdirs_empty": True,
            "exclude_older": True,
            "purge": False,
            "is_two_way_sync": True,
            "retries": 3,
            "wait_time": 5,
            "multi_threaded": 32,
            "exclude_junctions": True,
            "dry_run": False
        }
    },
    "goodsync_move": {
        "name": "Mover Arquivos (Cut & Paste / Move)",
        "description": "Transfere todos os arquivos e pastas para o destino e limpa a pasta de origem após a conclusão.",
        "config": {
            "mirror": False,
            "copy_subdirs_empty": True,
            "move_all": True,
            "is_two_way_sync": False,
            "retries": 3,
            "wait_time": 5,
            "multi_threaded": 32,
            "exclude_junctions": True,
            "dry_run": False
        }
    },
    "goodsync_filter": {
        "name": "Sincronização com Filtros de Extensão/Tamanho",
        "description": "Permite sincronizar com exclusão de extensões ou filtrando por tamanho máximo de arquivo.",
        "config": {
            "mirror": False,
            "copy_subdirs_empty": True,
            "is_two_way_sync": False,
            "retries": 3,
            "wait_time": 5,
            "multi_threaded": 32,
            "exclude_junctions": True,
            "dry_run": False
        }
    }
}

PRESET_RESET_DEFAULTS = {
    "mirror": False,
    "copy_subdirs": False,
    "copy_subdirs_empty": True,
    "purge": False,
    "move_files": False,
    "move_all": False,
    "exclude_older": False,
    "exclude_newer": False,
    "is_two_way_sync": False,
    "verbose_timestamps": False,
    "dry_run": False,
}

def apply_preset_to_config(config: RobocopyConfig, preset_key: str) -> RobocopyConfig:
    """Aplica os valores do preset sobre a configuração atual mantendo origem e destino."""
    if preset_key not in PRESETS:
        return config
    
    # Reseta flags operacionais exclusivas antes de aplicar os valores do preset
    for key, default_val in PRESET_RESET_DEFAULTS.items():
        if hasattr(config, key):
            setattr(config, key, default_val)

    preset_data = PRESETS[preset_key]["config"]
    for key, value in preset_data.items():
        if hasattr(config, key):
            setattr(config, key, value)
    return config

def export_profile_to_json(config: RobocopyConfig, filepath: str):
    """Exporta a configuração atual para um arquivo JSON."""
    data = config.__dict__.copy()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def import_profile_from_json(filepath: str) -> RobocopyConfig:
    """Carrega as configurações a partir de um arquivo JSON."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    config = RobocopyConfig()
    for key, value in data.items():
        if hasattr(config, key):
            setattr(config, key, value)
    return config
