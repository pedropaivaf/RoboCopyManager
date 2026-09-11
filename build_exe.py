"""
Script de Build Automatizado para o RoboCopy Manager.
Compila a aplicação em um executável único (.exe) autônomo e portátil,
pronto para uso plug-and-play no Windows 10 e Windows 11.
"""

import os
import sys
import subprocess
import shutil

def build():
    print("=" * 60)
    print("Iniciando compilação do RoboCopy Manager em executável único (.exe)...")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(base_dir, "robocopy_gui.py")
    icon_path = os.path.join(base_dir, "assets", "desktop_icon.ico")
    if not os.path.exists(icon_path):
        icon_path = os.path.join(base_dir, "assets", "app_icon.ico")
    assets_dir = os.path.join(base_dir, "assets")

    # Comando PyInstaller
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name=RoboCopyManager",
        f"--icon={icon_path}",
        f"--add-data={assets_dir};assets",
        "--collect-all=customtkinter",
        "--collect-all=windnd",
        main_script,
    ]

    print("Executando PyInstaller:")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=base_dir)

    if result.returncode == 0:
        exe_path = os.path.join(base_dir, "dist", "RoboCopyManager.exe")
        print("\n" + "=" * 60)
        print("Compilação concluída com sucesso!")
        print(f"Executável gerado em: {exe_path}")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"Tamanho do arquivo: {size_mb:.2f} MB")
        print("=" * 60)
        return True
    else:
        print(f"\nFalha na compilação. Código de saída: {result.returncode}")
        return False

if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
