import pytest
from unittest.mock import patch, MagicMock
from krokbot.supervisor import AgentSupervisor, get_supervisor
from fastapi.testclient import TestClient
from krokbot.dashboard.server import app

client = TestClient(app)

def test_supervisor_initial_state(tmp_path):
    sup = AgentSupervisor(workspaces_root=str(tmp_path))
    agents = sup.list_agents()
    assert len(agents) >= 1
    primary = agents[0]
    assert primary["id"] == "krok-prime-01"
    assert primary["status"] == "running"

def test_supervisor_spawn_and_stop_agent(tmp_path):
    sup = AgentSupervisor(workspaces_root=str(tmp_path))
    
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        
        result = sup.spawn_agent(agent_id="krok-worker-02", agent_name="Weather Sentinel Worker")
        assert result["status"] == "running"
        assert result["id"] == "krok-worker-02"
        assert result["name"] == "Weather Sentinel Worker"
        assert "port" in result
        
        # Verify listed
        agents = sup.list_agents()
        worker_ids = [a["id"] for a in agents]
        assert "krok-worker-02" in worker_ids
        
        # Stop agent
        stopped = sup.stop_agent("krok-worker-02")
        assert stopped is True
        
        # Cannot stop primary agent
        assert sup.stop_agent("krok-prime-01") is False

def test_dashboard_agent_deployment_endpoints(tmp_path):
    sup = get_supervisor()
    with patch.object(sup, "spawn_agent") as mock_spawn, \
         patch.object(sup, "stop_agent") as mock_stop:
        
        mock_spawn.return_value = {
            "status": "running",
            "id": "krok-sub-99",
            "name": "Test Subagent",
            "port": 5152
        }
        mock_stop.return_value = True
        
        # 1. List agents
        r_list = client.get("/api/agents")
        assert r_list.status_code == 200
        data_list = r_list.json()
        assert "agents" in data_list
        
        # 2. Deploy agent
        r_deploy = client.post("/api/agents/deploy", json={
            "id": "krok-sub-99",
            "name": "Test Subagent"
        })
        assert r_deploy.status_code == 200
        assert r_deploy.json()["id"] == "krok-sub-99"
        
        # 3. Stop agent
        r_stop = client.post("/api/agents/krok-sub-99/stop")
        assert r_stop.status_code == 200
        assert r_stop.json()["status"] == "success"
