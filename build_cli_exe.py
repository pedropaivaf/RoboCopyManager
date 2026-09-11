"""
Script de Build Automatizado para o RoboCopy CLI (Terminal / Console).
Compila a versão de terminal em um executável único (.exe) de console autônomo,
deixando a versão com interface gráfica (RoboCopyManager.exe) intacta em dist/.
"""

import os
import sys
import subprocess

def build():
    print("=" * 65)
    print("Iniciando compilação do RoboCopy CLI (Modo Terminal) (.exe)...")
    print("=" * 65)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(base_dir, "robocopy_cli.py")
    icon_path = os.path.join(base_dir, "assets", "desktop_icon.ico")
    if not os.path.exists(icon_path):
        icon_path = os.path.join(base_dir, "assets", "app_icon.ico")

    # Comando PyInstaller com flag --console (terminal nativo)
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--name=RoboCopyCLI",
        f"--icon={icon_path}",
        main_script,
    ]

    print("Executando PyInstaller:")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=base_dir)

    if result.returncode == 0:
        exe_path = os.path.join(base_dir, "dist", "RoboCopyCLI.exe")
        print("\n" + "=" * 65)
        print("Compilação da versão CLI concluída com sucesso!")
        print(f"Executável de console gerado em: {exe_path}")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"Tamanho do arquivo: {size_mb:.2f} MB")
        print("=" * 65)
        return True
    else:
        print(f"\nFalha na compilação do CLI. Código de saída: {result.returncode}")
        return False

if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
