import os
import tarfile
import tempfile
import pytest
from pathlib import Path
from scripts.package_offline_node import create_bundle
from krokbot_bootstrap.bootstrap import allocate_agent_resources

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
    assert ":5150" in sh_content
    assert "krokbot_agent" in sh_content
    assert "WEB_PORT" in sh_content

    ps1_content = install_ps1.read_text(encoding="utf-8")
    assert "docker load" in ps1_content
    assert ":5150" in ps1_content
    assert "krokbot_agent" in ps1_content
    assert "Get-NextFreePort" in ps1_content

def test_multi_agent_resource_and_port_adjustment():
    # 1. First agent on blank machine
    existing_containers = []
    used_ports = set()
    alloc1 = allocate_agent_resources(existing_containers, used_ports)

    assert alloc1["container_name"] == "krokbot_agent"
    assert alloc1["web_port"] == 5150
    assert alloc1["vnc_port"] == 8081
    assert alloc1["bridge_port"] == 8992
    assert alloc1["data_dir"] == "/opt/krokbot/data"
    assert alloc1["is_secondary"] is False

    # 2. Second agent on same machine (ports in use and container exists)
    existing_containers = ["krokbot_agent"]
    used_ports = {5150, 8081, 8992}
    alloc2 = allocate_agent_resources(existing_containers, used_ports)

    assert alloc2["container_name"] == "krokbot_agent_2"
    assert alloc2["web_port"] == 5151
    assert alloc2["vnc_port"] == 8082
    assert alloc2["bridge_port"] == 8993
    assert alloc2["data_dir"] == "/opt/krokbot/data_2"
    assert alloc2["is_secondary"] is True

    # 3. Third agent with gaps or multiple containers
    existing_containers = ["krokbot_agent", "krokbot_agent_2"]
    used_ports = {5150, 5151, 8081, 8082, 8992, 8993}
    alloc3 = allocate_agent_resources(existing_containers, used_ports)

    assert alloc3["container_name"] == "krokbot_agent_3"
    assert alloc3["web_port"] == 5152
    assert alloc3["vnc_port"] == 8083
    assert alloc3["bridge_port"] == 8994
    assert alloc3["data_dir"] == "/opt/krokbot/data_3"
    assert alloc3["is_secondary"] is True

def test_package_offline_bundle_creates_valid_archive():
    archive_path = create_bundle(include_models=False, include_image=False)
    assert archive_path.exists()
    assert archive_path.stat().st_size > 0

    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
        assert "krokbot_offline_bundle/install.sh" in names
        assert "krokbot_offline_bundle/install.ps1" in names
        assert "krokbot_offline_bundle/README.md" in names
