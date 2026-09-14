#!/usr/bin/env python3
"""
Cross-platform packager for KrokBot offline edge node deployment bundle.
"""
import os
import sys
import shutil
import tarfile
from pathlib import Path

def create_bundle(include_models: bool = False, include_image: bool = False):
    repo_root = Path(__file__).resolve().parent.parent
    dist_root = repo_root / "dist"
    bundle_dir = dist_root / "krokbot_offline_bundle"
    
    # Clean previous
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
        
    (bundle_dir / "images").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "models").mkdir(parents=True, exist_ok=True)
    
    src_bundle = repo_root / "scripts" / "offline_bundle"
    shutil.copy(src_bundle / "install.sh", bundle_dir / "install.sh")
    shutil.copy(src_bundle / "install.ps1", bundle_dir / "install.ps1")
    shutil.copy(src_bundle / "README_ENGINEER.md", bundle_dir / "README.md")
    
    if include_models:
        models_src = repo_root / "models"
        for m in models_src.glob("*.gguf"):
            print(f"Adding model: {m.name}")
            shutil.copy(m, bundle_dir / "models" / m.name)

    archive_path = dist_root / "krokbot-offline-bundle.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(bundle_dir, arcname="krokbot_offline_bundle")
        
    print(f"Successfully packaged offline bundle to: {archive_path}")
    return archive_path

if __name__ == "__main__":
    include_models = "--include-models" in sys.argv or "--full" in sys.argv
    include_image = "--include-image" in sys.argv or "--full" in sys.argv
    create_bundle(include_models, include_image)
