import pytest
from krokbot.agent.core import KrokBotAgent

def test_scripting_intent_reconcile_flow(tmp_path, monkeypatch):
    agent = KrokBotAgent()
    agent.tools.sandbox.workspace_dir = tmp_path
    
    script_content = (
        "import sys\n"
        "with open('report.txt', 'w') as f: f.write('Transactions missing from B: TX00100\\nDiscrepancies found: 1')\n"
        "sys.exit(1)\n"
    )
    
    # Mock Llama.cpp chat to return the generated script block
    monkeypatch.setattr(agent.client, "chat", lambda msgs: {"message": {"content": f"Here is the python script:\n\n```python\n{script_content}\n```"}})
    
    res = agent.run_task("Create a Python script at ./reconcile.py in your working directory that reconciles ledgers and writes report.txt.", save_mode="saved")
    assert res["status"] == "success"
    assert (tmp_path / "reconcile.py").exists()
    assert (tmp_path / "report.txt").exists()
    assert "Transactions missing from B: TX00100" in res["report"]
    assert "Exit Code: `1`" in res["report"] or "exit code 1" in res["report"]
