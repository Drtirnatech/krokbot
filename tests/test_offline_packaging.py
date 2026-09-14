import os
import tarfile
import tempfile
import pytest
from pathlib import Path
from scripts.package_offline_node import create_bundle

def test_offline_bundle_scripts_exist():
    repo_root = Path(__file__).resolve().parent.parent
    install_sh = repo_root / "scripts" / "offline_bundle" / "install.sh"
    install_ps1 = repo_root / "scripts" / "offline_bundle" / "install.ps1"
    readme = repo_root / "scripts" / "offline_bundle" / "README_ENGINEER.md"

    assert install_sh.exists(), "install.sh must exist"
    assert install_ps1.exists(), "install.ps1 must exist"
    assert readme.exists(), "README_ENGINEER.md must exist"

    # Verify script content
    sh_content = install_sh.read_text(encoding="utf-8")
    assert "docker load" in sh_content
    assert "/opt/krokbot" in sh_content
    assert "5150:5150" in sh_content
    assert "krokbot_agent:latest" in sh_content

    ps1_content = install_ps1.read_text(encoding="utf-8")
    assert "docker load" in ps1_content
    assert "5150:5150" in ps1_content
    assert "krokbot_agent" in ps1_content

def test_package_offline_bundle_creates_valid_archive():
    archive_path = create_bundle(include_models=False, include_image=False)
    assert archive_path.exists()
    assert archive_path.stat().st_size > 0

    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
        assert "krokbot_offline_bundle/install.sh" in names
        assert "krokbot_offline_bundle/install.ps1" in names
        assert "krokbot_offline_bundle/README.md" in names
