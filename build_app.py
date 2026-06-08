#!/usr/bin/env python3
"""
MiniSearch Build Script
Generates the icon, then runs PyInstaller to produce MiniSearch.app
"""

import os
import sys
import subprocess
import shutil

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    # 1. Generate icon
    print("[build] generating icon ...")
    subprocess.run([sys.executable, os.path.join(PROJECT_DIR, "generate_icon.py")], check=True)

    # 2. Call PyInstaller
    spec = os.path.join(PROJECT_DIR, "MiniSearch.spec")
    print("[build] running PyInstaller ...")
    subprocess.run([
        sys.executable, "-m", "PyInstaller",
        spec,
        "--noconfirm",
        "--clean",
        "--distpath", os.path.join(PROJECT_DIR, "dist"),
        "--workpath", os.path.join(PROJECT_DIR, "build"),
    ], check=True)

    app_path = os.path.join(PROJECT_DIR, "dist", "MiniSearch.app")
    if os.path.exists(app_path):
        size_mb = round(sum(
            os.path.getsize(os.path.join(root, f))
            for root, _, files in os.walk(app_path)
            for f in files
        ) / (1024 * 1024), 1)
        print(f"[build] done → {app_path} ({size_mb} MB)")
    else:
        print("[build] failed — .app not found")
        sys.exit(1)


if __name__ == "__main__":
    main()
