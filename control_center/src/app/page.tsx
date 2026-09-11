'use client';

import React, { useState, useEffect, useCallback } from 'react';

interface Agent {
  id: string;
  name: string;
  port: number;
  pid?: number;
  status: string;
  is_primary: boolean | number;
  workspace?: string;
}

interface LiveHealth {
  agentId: string;
  agentName: string;
  dashboardPort: number;
  cpuPercent: number;
  memoryUsedGb: number;
  memoryPercent: number;
  storageMb: number;
  activeModel: string;
  isOnline: boolean;
  agents: Agent[];
}

interface NodeRecord {
  id: string;
  name: string;
  ip_address: string;
  status: string;
  active_model: string;
  hardware_info: string | null;
  last_seen: string;
  agents?: Agent[];
  liveHealth?: LiveHealth;
}

interface AuditLog {
  id: number;
  node_id: string | null;
  agent_id: string;
  task_name: string;
  status: string;
  exit_code: number;
  duration_ms: number;
  timestamp: string;
}

interface ModelItem {
  filename: string;
  size_formatted?: string;
  size_mb?: number;
}

export default function ControlCenterDashboard() {
  const [nodes, setNodes] = useState<NodeRecord[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<string>('');

  // Modals state
  const [deployModalNode, setDeployModalNode] = useState<NodeRecord | null>(null);
  const [newAgentId, setNewAgentId] = useState('krok-agent-02');
  const [newAgentName, setNewAgentName] = useState('KrokBot Recon Worker');
  const [deploying, setDeploying] = useState(false);

  const [modelModalNode, setModelModalNode] = useState<NodeRecord | null>(null);
  const [availableModels, setAvailableModels] = useState<ModelItem[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [switchingModel, setSwitchingModel] = useState(false);

  const [registerModalOpen, setRegisterModalOpen] = useState(false);
  const [regNodeId, setRegNodeId] = useState('');
  const [regNodeName, setRegNodeName] = useState('');
  const [regNodeIp, setRegNodeIp] = useState('');
  const [registering, setRegistering] = useState(false);

  // Command prompt terminal state
  const [targetNode, setTargetNode] = useState<string>('');
  const [targetAgent, setTargetAgent] = useState<{ id: string; port: number } | null>(null);
  const [commandPrompt, setCommandPrompt] = useState('');
  const [commandExecuting, setCommandExecuting] = useState(false);
  const [commandOutput, setCommandOutput] = useState<any>(null);

  // Fetch Fleet Nodes & Status
  const fetchFleet = useCallback(async () => {
    try {
      const res = await fetch('/api/fleet/nodes');
      if (!res.ok) throw new Error(`Failed to fetch fleet: ${res.statusText}`);
      const data = await res.json();
      setNodes(data.nodes || []);
      setLastRefreshed(new Date().toLocaleTimeString());
      setError(null);

      // Default select target node if none selected
      if (!targetNode && data.nodes && data.nodes.length > 0) {
        setTargetNode(data.nodes[0].id);
        if (data.nodes[0].agents && data.nodes[0].agents.length > 0) {
          setTargetAgent({ id: data.nodes[0].agents[0].id, port: data.nodes[0].agents[0].port });
        }
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [targetNode]);

  // Fetch Audit Logs
  const fetchAuditLogs = useCallback(async () => {
    try {
      const res = await fetch('/api/fleet/audit');
      if (res.ok) {
        const data = await res.json();
        setAuditLogs(data.logs || []);
      }
    } catch (err) {
      // ignore
    }
  }, []);

  // Initial load & Polling Loop
  useEffect(() => {
    fetchFleet();
    fetchAuditLogs();

    const interval = setInterval(() => {
      if (autoRefresh) {
        fetchFleet();
        fetchAuditLogs();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchFleet, fetchAuditLogs, autoRefresh]);

  // Open Deploy Modal
  const openDeployModal = (node: NodeRecord) => {
    const existingCount = (node.agents || []).length;
    const nextIdx = existingCount < 9 ? `0${existingCount + 1}` : `${existingCount + 1}`;
    setNewAgentId(`krok-worker-${nextIdx}`);
    setNewAgentName(`KrokBot Recon Subagent ${nextIdx}`);
    setDeployModalNode(node);
  };

  // Submit Deploy Agent
  const handleDeployAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deployModalNode) return;
    setDeploying(true);
    try {
      const res = await fetch(`/api/fleet/nodes/${deployModalNode.id}/deploy-agent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: newAgentId, name: newAgentName })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || 'Deploy failed');

      setDeployModalNode(null);
      await fetchFleet();
      await fetchAuditLogs();
    } catch (err: any) {
      alert(`Deployment Error: ${err.message}`);
    } finally {
      setDeploying(false);
    }
  };

  // Stop Agent
  const handleStopAgent = async (nodeId: string, agentId: string) => {
    if (!confirm(`Are you sure you want to stop in-container agent ${agentId}?`)) return;
    try {
      const res = await fetch(`/api/fleet/nodes/${nodeId}/agents/${agentId}/stop`, {
        method: 'POST'
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.message || 'Stop failed');
      }
      await fetchFleet();
      await fetchAuditLogs();
    } catch (err: any) {
      alert(`Stop Error: ${err.message}`);
    }
  };

  // Open Model Switch Modal
  const openModelModal = async (node: NodeRecord) => {
    setModelModalNode(node);
    setSelectedModel(node.active_model);
    try {
      const res = await fetch(`/api/fleet/nodes/${node.id}/models`);
      if (res.ok) {
        const data = await res.json();
        setAvailableModels(data.available || []);
      }
    } catch (err) {
      setAvailableModels([]);
    }
  };

  // Submit Switch Model
  const handleSwitchModel = async () => {
    if (!modelModalNode || !selectedModel) return;
    setSwitchingModel(true);
    try {
      const res = await fetch(`/api/fleet/nodes/${modelModalNode.id}/models/${encodeURIComponent(selectedModel)}/activate`, {
        method: 'POST'
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.message || 'Model switch failed');
      }
      setModelModalNode(null);
      await fetchFleet();
      await fetchAuditLogs();
    } catch (err: any) {
      alert(`Switch Model Error: ${err.message}`);
    } finally {
      setSwitchingModel(false);
    }
  };

  // Register New Node
  const handleRegisterNode = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegistering(true);
    try {
      const res = await fetch('/api/fleet/nodes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: regNodeId,
          name: regNodeName,
          ip_address: regNodeIp
        })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.message || 'Registration failed');
      }
      setRegisterModalOpen(false);
      setRegNodeId('');
      setRegNodeName('');
      setRegNodeIp('');
      await fetchFleet();
    } catch (err: any) {
      alert(`Register Error: ${err.message}`);
    } finally {
      setRegistering(false);
    }
  };

  // Execute Command Dispatch
  const handleSendCommand = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commandPrompt.trim() || !targetNode) return;
    setCommandExecuting(true);
    setCommandOutput(null);
    try {
      const res = await fetch(`/api/fleet/nodes/${targetNode}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: commandPrompt,
          agentId: targetAgent?.id,
          port: targetAgent?.port
        })
      });
      const data = await res.json();
      setCommandOutput(data);
      await fetchAuditLogs();
    } catch (err: any) {
      setCommandOutput({ status: 'error', message: err.message });
    } finally {
      setCommandExecuting(false);
    }
  };

  const totalAgents = nodes.reduce((sum, n) => sum + (n.agents?.length || 0), 0);
  const onlineNodes = nodes.filter(n => n.status === 'online').length;

  return (
    <div className="min-h-screen bg-[#070908] crt-grid text-[#c4d6cc] flex flex-col font-mono selection:bg-[#00ff66]/20 selection:text-[#00ff66]">
      {/* C2 TOP COMMAND BAR */}
      <header className="border-b border-[#141d18] bg-[#0a0f0c]/90 backdrop-blur sticky top-0 z-40 px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-3.5 h-3.5 rounded-sm bg-[#00ff66] shadow-[0_0_12px_#00ff66] radar-pulse"></div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[#00ff66] font-bold tracking-wider text-base glow-green">KROKBOT // C2</span>
              <span className="text-[10px] uppercase tracking-widest px-1.5 py-0.5 rounded bg-[#132219] text-[#00ff66] border border-[#00ff66]/30">
                CONTROL CENTER v2.0
              </span>
            </div>
            <p className="text-[11px] text-[#5b7a6b] tracking-tight">Autonomous Edge Agent & In-Container Swarm Fleet Manager</p>
          </div>
        </div>

        {/* Global Telemetry & Status Badges */}
        <div className="flex items-center gap-5 text-xs">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-[#0e1511] border border-[#18261e]">
            <span className="text-[#5b7a6b]">NODES:</span>
            <span className="text-[#00ff66] font-bold">{onlineNodes}/{nodes.length} ONLINE</span>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-[#0e1511] border border-[#18261e]">
            <span className="text-[#5b7a6b]">AGENTS:</span>
            <span className="text-[#00e5ff] font-bold">{totalAgents} ACTIVE</span>
          </div>

          <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded bg-[#0e1511] border border-[#18261e]">
            <span className="text-[#5b7a6b]">INFERENCE:</span>
            <span className="text-[#ffb000] font-semibold">SHARED LLAMA.CPP ARBITER</span>
          </div>

          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded bg-[#0e1511] border border-[#18261e]">
            <span className="text-[#5b7a6b]">STORE:</span>
            <span className="text-[#96b8a8]">c2_fleet.db (WAL)</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`text-[11px] px-2.5 py-1 rounded border transition-colors ${
                autoRefresh
                  ? 'bg-[#102419] border-[#00ff66]/50 text-[#00ff66]'
                  : 'bg-[#141c17] border-[#223329] text-[#718c7e]'
              }`}
              title="Toggle 5-second telemetry polling"
            >
              AUTO: {autoRefresh ? 'ON' : 'PAUSED'}
            </button>
            <button
              onClick={() => { fetchFleet(); fetchAuditLogs(); }}
              className="text-[11px] px-3 py-1 rounded bg-[#16221b] hover:bg-[#1f3126] border border-[#273a2e] text-[#c4d6cc] transition-colors"
            >
              SYNC ↻
            </button>
          </div>

          <button
            onClick={() => setRegisterModalOpen(true)}
            className="text-xs px-3.5 py-1.5 rounded bg-[#00ff66] text-[#050a07] font-bold hover:bg-[#1aff75] transition-all shadow-[0_0_15px_rgba(0,255,102,0.3)] cursor-pointer"
          >
            + REGISTER NODE
          </button>
        </div>
      </header>

      {/* ERROR BANNER IF ANY */}
      {error && (
        <div className="bg-[#240a0c] border-b border-[#ff3344]/40 px-6 py-2 text-xs text-[#ff5566] flex items-center justify-between">
          <span>FLEET TELEMETRY ERROR: {error}</span>
          <button onClick={() => setError(null)} className="text-[#ff99a4] font-bold">×</button>
        </div>
      )}

      {/* MAIN C2 CONTENT */}
      <main className="flex-1 p-6 space-y-8 max-w-7xl w-full mx-auto">
        {/* FLEET NODES SECTION */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold tracking-wider text-[#00ff66] flex items-center gap-2 uppercase">
              <span className="text-[#5b7a6b]">///</span> Edge Devices & Master Container Nodes ({nodes.length})
            </h2>
            <span className="text-[11px] text-[#5b7a6b]">Last telemetry refresh: {lastRefreshed || 'Just now'}</span>
          </div>

          {loading ? (
            <div className="p-12 border border-[#16221b] rounded-lg bg-[#0a0f0c] text-center text-sm text-[#5b7a6b]">
              <div className="inline-block w-6 h-6 border-2 border-[#00ff66] border-t-transparent rounded-full animate-spin mb-3"></div>
              <div>CONNECTING TO KROKBOT FLEET & IN-CONTAINER ARBITER...</div>
            </div>
          ) : nodes.length === 0 ? (
            <div className="p-12 border border-[#16221b] rounded-lg bg-[#0a0f0c] text-center space-y-3">
              <p className="text-sm text-[#7a998b]">No edge nodes registered yet.</p>
              <button
                onClick={() => setRegisterModalOpen(true)}
                className="px-4 py-2 rounded bg-[#00ff66] text-black font-bold text-xs"
              >
                Register Local or Jetson Node
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-6">
              {nodes.map((node) => {
                const health = node.liveHealth;
                const isOnline = node.status === 'online';
                const nodeAgents = node.agents || [];

                return (
                  <div
                    key={node.id}
                    className="border border-[#18261e] hover:border-[#00ff66]/40 rounded-xl bg-[#0b100d] overflow-hidden transition-all shadow-lg"
                  >
                    {/* Node Header */}
                    <div className="p-5 border-b border-[#141f19] bg-[#0d1410] flex flex-wrap items-center justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-3">
                          <span className={`w-2.5 h-2.5 rounded-full ${isOnline ? 'bg-[#00ff66] shadow-[0_0_8px_#00ff66]' : 'bg-[#ff3344]'}`}></span>
                          <h3 className="text-base font-bold text-white tracking-wide">{node.name}</h3>
                          <span className="text-[10px] px-2 py-0.5 rounded bg-[#15231b] text-[#7da895] border border-[#23382c]">
                            ID: {node.id}
                          </span>
                        </div>
                        <div className="text-xs text-[#5b7a6b] flex items-center gap-4">
                          <span>Endpoint: <strong className="text-[#a4c5b5]">{node.ip_address}</strong></span>
                          <span>Status: <strong className={isOnline ? 'text-[#00ff66]' : 'text-[#ff3344]'}>{node.status.toUpperCase()}</strong></span>
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => openModelModal(node)}
                          className="px-3 py-1.5 rounded text-xs bg-[#131f18] hover:bg-[#1a2b21] border border-[#213529] text-[#ffb000] font-medium transition-colors flex items-center gap-1.5"
                        >
                          <span>🧠 Switch Model</span>
                        </button>
                        <button
                          onClick={() => openDeployModal(node)}
                          className="px-3.5 py-1.5 rounded text-xs bg-[#0e271a] hover:bg-[#143524] border border-[#00ff66]/40 text-[#00ff66] font-semibold transition-colors flex items-center gap-1.5"
                        >
                          <span>+ Deploy Agent in Container</span>
                        </button>
                      </div>
                    </div>

                    {/* Node Metrics & Active Model Bar */}
                    <div className="p-5 grid grid-cols-1 md:grid-cols-4 gap-4 border-b border-[#141f19] bg-[#080d0a]/60">
                      {/* CPU Usage */}
                      <div className="p-3 rounded-lg bg-[#0c1310] border border-[#16231c] space-y-1.5">
                        <div className="flex justify-between text-[11px] text-[#5b7a6b]">
                          <span>CONTAINER CPU</span>
                          <span className="text-white font-bold">{health ? `${health.cpuPercent.toFixed(1)}%` : '0.0%'}</span>
                        </div>
                        <div className="w-full bg-[#142019] h-2 rounded-full overflow-hidden">
                          <div
                            className="bg-[#00ff66] h-full transition-all duration-500 shadow-[0_0_8px_#00ff66]"
                            style={{ width: `${Math.min(100, Math.max(2, health?.cpuPercent || 0))}%` }}
                          ></div>
                        </div>
                      </div>

                      {/* Memory Usage */}
                      <div className="p-3 rounded-lg bg-[#0c1310] border border-[#16231c] space-y-1.5">
                        <div className="flex justify-between text-[11px] text-[#5b7a6b]">
                          <span>RAM CONSUMPTION</span>
                          <span className="text-white font-bold">{health ? `${health.memoryUsedGb.toFixed(2)} GB (${health.memoryPercent.toFixed(0)}%)` : '0.0 GB'}</span>
                        </div>
                        <div className="w-full bg-[#142019] h-2 rounded-full overflow-hidden">
                          <div
                            className="bg-[#00e5ff] h-full transition-all duration-500 shadow-[0_0_8px_#00e5ff]"
                            style={{ width: `${Math.min(100, Math.max(2, health?.memoryPercent || 0))}%` }}
                          ></div>
                        </div>
                      </div>

                      {/* Container Storage */}
                      <div className="p-3 rounded-lg bg-[#0c1310] border border-[#16231c] space-y-1.5">
                        <div className="flex justify-between text-[11px] text-[#5b7a6b]">
                          <span>ISOLATED STORAGE</span>
                          <span className="text-white font-bold">{health ? `${health.storageMb.toFixed(1)} MB` : '0.0 MB'}</span>
                        </div>
                        <div className="w-full bg-[#142019] h-2 rounded-full overflow-hidden">
                          <div className="bg-[#9c27b0] h-full w-[12%]"></div>
                        </div>
                      </div>

                      {/* Active Shared Model */}
                      <div className="p-3 rounded-lg bg-[#0c1310] border border-[#16231c] space-y-1">
                        <span className="text-[11px] text-[#5b7a6b] block">SHARED INFERENCE MODEL</span>
                        <div className="text-xs font-bold text-[#ffb000] truncate" title={node.active_model}>
                          {node.active_model}
                        </div>
                        <span className="text-[10px] text-[#5b7a6b]">Shared on 127.0.0.1:8081</span>
                      </div>
                    </div>

                    {/* Co-located Agents in Master Container */}
                    <div className="p-5 space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-[#a4c5b5] flex items-center gap-2">
                          <span>📦 In-Container Co-Located Agents</span>
                          <span className="text-[10px] px-2 py-0.2 rounded-full bg-[#16241c] text-[#00ff66] border border-[#233a2d]">
                            {nodeAgents.length} Running
                          </span>
                        </h4>
                        <span className="text-[11px] text-[#5b7a6b]">
                          All agents share the container's GPU/CPU llama.cpp service via InferenceArbiter
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
                        {nodeAgents.map((agent) => {
                          const isPrimary = agent.is_primary === 1 || agent.is_primary === true;
                          return (
                            <div
                              key={agent.id}
                              className="p-4 rounded-lg bg-[#0e1612] border border-[#1c2c22] hover:border-[#00ff66]/50 transition-all space-y-2.5 relative group"
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div>
                                  <div className="flex items-center gap-1.5">
                                    <span className="w-2 h-2 rounded-full bg-[#00ff66]"></span>
                                    <span className="text-xs font-bold text-white">{agent.name}</span>
                                  </div>
                                  <span className="text-[10px] text-[#6b8c7c] font-mono block mt-0.5">
                                    ID: {agent.id}
                                  </span>
                                </div>
                                <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${
                                  isPrimary
                                    ? 'bg-[#183523] text-[#00ff66] border border-[#00ff66]/40'
                                    : 'bg-[#222a36] text-[#70a5ff] border border-[#70a5ff]/30'
                                }`}>
                                  {isPrimary ? 'PRIMARY' : 'WORKER'}
                                </span>
                              </div>

                              <div className="text-[11px] text-[#5b7a6b] space-y-1">
                                <div className="flex justify-between">
                                  <span>Port:</span>
                                  <span className="text-white font-mono">{agent.port}</span>
                                </div>
                                {agent.pid && (
                                  <div className="flex justify-between">
                                    <span>Process PID:</span>
                                    <span className="text-white font-mono">{agent.pid}</span>
                                  </div>
                                )}
                                <div className="flex justify-between">
                                  <span>Isolated Workspace:</span>
                                  <span className="text-[#a4c5b5] font-mono truncate max-w-[140px]" title={agent.workspace || `/app/workspaces/agent_${agent.id}`}>
                                    {agent.workspace || `/app/workspaces/agent_${agent.id}`}
                                  </span>
                                </div>
                              </div>

                              {/* Agent Actions */}
                              <div className="pt-2 border-t border-[#18261e] flex items-center justify-between gap-2">
                                <button
                                  onClick={() => {
                                    setTargetNode(node.id);
                                    setTargetAgent({ id: agent.id, port: agent.port });
                                    // Scroll to command terminal
                                    document.getElementById('c2-terminal')?.scrollIntoView({ behavior: 'smooth' });
                                  }}
                                  className="flex-1 py-1 px-2 rounded bg-[#15231b] hover:bg-[#1e3327] border border-[#273d2f] text-[#00ff66] text-[11px] font-semibold transition-colors text-center"
                                >
                                  ⚡ Command
                                </button>

                                {!isPrimary && (
                                  <button
                                    onClick={() => handleStopAgent(node.id, agent.id)}
                                    className="py-1 px-2.5 rounded bg-[#2a1315] hover:bg-[#3d181c] border border-[#ff3344]/30 text-[#ff5566] text-[11px] transition-colors"
                                    title="Stop in-container agent"
                                  >
                                    Stop
                                  </button>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* BOTTOM SECTION: COMMAND DISPATCHER & AUDIT LOGS */}
        <section id="c2-terminal" className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* INTERACTIVE FLEET COMMAND DISPATCHER */}
          <div className="lg:col-span-6 border border-[#18261e] rounded-xl bg-[#0b100d] p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[#16231c] pb-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#00ff66] flex items-center gap-2">
                <span>💻 Autonomous Agent Command Console</span>
              </h3>
              <span className="text-[10px] text-[#5b7a6b]">Direct API Proxy to Container</span>
            </div>

            <form onSubmit={handleSendCommand} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-[#5b7a6b] block mb-1">TARGET NODE</label>
                  <select
                    value={targetNode}
                    onChange={(e) => setTargetNode(e.target.value)}
                    className="w-full bg-[#080d0a] border border-[#1e2e24] rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[#00ff66]"
                  >
                    {nodes.map(n => (
                      <option key={n.id} value={n.id}>{n.name} ({n.id})</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-[10px] text-[#5b7a6b] block mb-1">TARGET AGENT</label>
                  <select
                    value={targetAgent?.id || ''}
                    onChange={(e) => {
                      const selNode = nodes.find(n => n.id === targetNode);
                      const ag = selNode?.agents?.find(a => a.id === e.target.value);
                      if (ag) setTargetAgent({ id: ag.id, port: ag.port });
                    }}
                    className="w-full bg-[#080d0a] border border-[#1e2e24] rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[#00ff66]"
                  >
                    {nodes.find(n => n.id === targetNode)?.agents?.map(a => (
                      <option key={a.id} value={a.id}>
                        {a.name} ({a.is_primary ? 'Primary' : 'Worker'} : {a.port})
                      </option>
                    )) || <option value="">No Agents Available</option>}
                  </select>
                </div>
              </div>

              <div>
                <label className="text-[10px] text-[#5b7a6b] block mb-1">PROMPT / INSTRUCTION</label>
                <textarea
                  value={commandPrompt}
                  onChange={(e) => setCommandPrompt(e.target.value)}
                  placeholder="Enter autonomous prompt, e.g.: Analyze hardware memory overhead and summarize system readiness."
                  rows={3}
                  className="w-full bg-[#080d0a] border border-[#1e2e24] rounded p-2.5 text-xs text-[#00ff66] focus:outline-none focus:border-[#00ff66] font-mono resize-none"
                />
              </div>

              <div className="flex justify-between items-center">
                <span className="text-[10px] text-[#5b7a6b]">
                  Routing to: <strong className="text-white">{targetAgent ? `${targetAgent.id} (Port ${targetAgent.port})` : 'None'}</strong>
                </span>
                <button
                  type="submit"
                  disabled={commandExecuting || !commandPrompt.trim()}
                  className="px-4 py-1.5 rounded bg-[#00ff66] text-black text-xs font-bold hover:bg-[#1aff75] disabled:opacity-50 transition-all cursor-pointer"
                >
                  {commandExecuting ? 'DISPATCHING...' : 'DISPATCH COMMAND ↵'}
                </button>
              </div>
            </form>

            {/* Execution Result Box */}
            {commandOutput && (
              <div className="mt-3 p-3 rounded bg-[#070b09] border border-[#1c2c22] max-h-48 overflow-y-auto space-y-1 text-xs">
                <div className="text-[10px] text-[#5b7a6b] flex justify-between border-b border-[#141f19] pb-1">
                  <span>DISPATCH RESULT</span>
                  <span className={commandOutput.status === 'error' ? 'text-[#ff3344]' : 'text-[#00ff66]'}>
                    {commandOutput.status?.toUpperCase()}
                  </span>
                </div>
                <pre className="text-[11px] text-[#a4c5b5] whitespace-pre-wrap font-mono pt-1">
                  {typeof commandOutput.result?.response === 'string'
                    ? commandOutput.result.response
                    : JSON.stringify(commandOutput, null, 2)}
                </pre>
              </div>
            )}
          </div>

          {/* REAL-TIME FLEET AUDIT LOG */}
          <div className="lg:col-span-6 border border-[#18261e] rounded-xl bg-[#0b100d] p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[#16231c] pb-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#00e5ff] flex items-center gap-2">
                <span>📜 Real-Time Fleet Audit Log</span>
              </h3>
              <button
                onClick={fetchAuditLogs}
                className="text-[10px] text-[#5b7a6b] hover:text-white"
              >
                Refresh Log
              </button>
            </div>

            <div className="max-h-80 overflow-y-auto space-y-2 pr-1">
              {auditLogs.length === 0 ? (
                <div className="text-xs text-[#5b7a6b] text-center py-8">
                  No fleet audit events logged yet.
                </div>
              ) : (
                auditLogs.map((log) => (
                  <div
                    key={log.id}
                    className="p-2.5 rounded bg-[#080d0a] border border-[#16221b] text-xs space-y-1 hover:border-[#283d30] transition-colors"
                  >
                    <div className="flex items-center justify-between text-[10px]">
                      <span className="text-[#00ff66] font-bold">{log.agent_id}</span>
                      <span className="text-[#5b7a6b]">{new Date(log.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <div className="text-[#d4e4dc] font-mono text-[11px] truncate" title={log.task_name}>
                      {log.task_name}
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-[#5b7a6b]">
                      <span className="text-[#00e5ff]">{log.status}</span>
                      <span>{log.duration_ms.toFixed(0)} ms</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>
      </main>

      {/* MODAL: DEPLOY IN-CONTAINER AGENT */}
      {deployModalNode && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0c1310] border border-[#00ff66]/40 rounded-xl max-w-md w-full p-6 space-y-5 box-glow-green">
            <div className="flex items-center justify-between border-b border-[#18261e] pb-3">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <span className="text-[#00ff66]">+</span> Deploy Agent in Container
              </h3>
              <button
                onClick={() => setDeployModalNode(null)}
                className="text-[#5b7a6b] hover:text-white text-lg font-bold"
              >
                ×
              </button>
            </div>

            <p className="text-xs text-[#7da895]">
              Spawns an independent uniform agent inside master container <strong>{deployModalNode.name}</strong>.
              The agent receives an allocated port, isolated workspace, and connects to the shared Llama.cpp inference arbiter.
            </p>

            <form onSubmit={handleDeployAgent} className="space-y-4 text-xs">
              <div>
                <label className="text-[10px] text-[#5b7a6b] block mb-1">AGENT IDENTIFIER (ID)</label>
                <input
                  type="text"
                  required
                  value={newAgentId}
                  onChange={(e) => setNewAgentId(e.target.value)}
                  className="w-full bg-[#080d0a] border border-[#1e2e24] rounded p-2 text-white font-mono focus:border-[#00ff66] outline-none"
                  placeholder="e.g. krok-agent-02"
                />
              </div>

              <div>
                <label className="text-[10px] text-[#5b7a6b] block mb-1">AGENT DISPLAY NAME</label>
                <input
                  type="text"
                  required
                  value={newAgentName}
                  onChange={(e) => setNewAgentName(e.target.value)}
                  className="w-full bg-[#080d0a] border border-[#1e2e24] rounded p-2 text-white focus:border-[#00ff66] outline-none"
                  placeholder="e.g. KrokBot Recon Subagent 02"
                />
              </div>

              <div className="pt-2 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setDeployModalNode(null)}
                  className="px-4 py-2 rounded bg-[#141e18] text-[#8aa89b] hover:bg-[#1a2720]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={deploying}
                  className="px-5 py-2 rounded bg-[#00ff66] text-black font-bold hover:bg-[#1aff75] disabled:opacity-50"
                >
                  {deploying ? 'Deploying...' : 'Deploy Agent Now'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: SWITCH SHARED MODEL */}
      {modelModalNode && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0c1310] border border-[#ffb000]/40 rounded-xl max-w-md w-full p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-[#18261e] pb-3">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <span className="text-[#ffb000]">🧠</span> Switch In-Container LLM Model
              </h3>
              <button
                onClick={() => setModelModalNode(null)}
                className="text-[#5b7a6b] hover:text-white text-lg font-bold"
              >
                ×
              </button>
            </div>

            <p className="text-xs text-[#7da895]">
              Switching the model reloads the central <strong>Llama.cpp</strong> server in container <strong>{modelModalNode.name}</strong>. All agents on this node will immediately use the new model.
            </p>

            <div className="space-y-3 text-xs">
              <label className="text-[10px] text-[#5b7a6b] block">AVAILABLE MODELS ON NODE</label>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {availableModels.map((m) => (
                  <label
                    key={m.filename}
                    className={`flex items-center justify-between p-2.5 rounded border cursor-pointer transition-colors ${
                      selectedModel === m.filename
                        ? 'bg-[#1e2617] border-[#ffb000] text-white'
                        : 'bg-[#080d0a] border-[#18261e] text-[#a4c5b5] hover:border-[#273d2f]'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="model"
                        value={m.filename}
                        checked={selectedModel === m.filename}
                        onChange={() => setSelectedModel(m.filename)}
                        className="accent-[#ffb000]"
                      />
                      <span className="font-mono text-[11px]">{m.filename}</span>
                    </div>
                    {m.size_formatted && (
                      <span className="text-[10px] text-[#ffb000]">{m.size_formatted}</span>
                    )}
                  </label>
                ))}
              </div>

              <div className="pt-2 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setModelModalNode(null)}
                  className="px-4 py-2 rounded bg-[#141e18] text-[#8aa89b] hover:bg-[#1a2720]"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSwitchModel}
                  disabled={switchingModel || !selectedModel}
                  className="px-5 py-2 rounded bg-[#ffb000] text-black font-bold hover:bg-[#ffbe26] disabled:opacity-50"
                >
                  {switchingModel ? 'Switching...' : 'Activate Model'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: REGISTER REMOTE NODE */}
      {registerModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0c1310] border border-[#00ff66]/40 rounded-xl max-w-md w-full p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-[#18261e] pb-3">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <span className="text-[#00ff66]">+</span> Register Remote Edge Node
              </h3>
              <button
                onClick={() => setRegisterModalOpen(false)}
                className="text-[#5b7a6b] hover:text-white text-lg font-bold"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleRegisterNode} className="space-y-4 text-xs">
              <div>
                <label className="text-[10px] text-[#5b7a6b] block mb-1">NODE ID</label>
                <input
                  type="text"
                  required
                  value={regNodeId}
                  onChange={(e) => setRegNodeId(e.target.value)}
                  className="w-full bg-[#080d0a] border border-[#1e2e24] rounded p-2 text-white font-mono focus:border-[#00ff66] outline-none"
                  placeholder="e.g. node-jetson-orin-01"
                />
              </div>

              <div>
                <label className="text-[10px] text-[#5b7a6b] block mb-1">NODE NAME / LOCATION</label>
                <input
                  type="text"
                  required
                  value={regNodeName}
                  onChange={(e) => setRegNodeName(e.target.value)}
                  className="w-full bg-[#080d0a] border border-[#1e2e24] rounded p-2 text-white focus:border-[#00ff66] outline-none"
                  placeholder="e.g. NVIDIA Jetson Orin Nano (Edge Device)"
                />
              </div>

              <div>
                <label className="text-[10px] text-[#5b7a6b] block mb-1">ENDPOINT BASE URL</label>
                <input
                  type="text"
                  required
                  value={regNodeIp}
                  onChange={(e) => setRegNodeIp(e.target.value)}
                  className="w-full bg-[#080d0a] border border-[#1e2e24] rounded p-2 text-white font-mono focus:border-[#00ff66] outline-none"
                  placeholder="e.g. http://192.168.1.150:5150"
                />
              </div>

              <div className="pt-2 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setRegisterModalOpen(false)}
                  className="px-4 py-2 rounded bg-[#141e18] text-[#8aa89b] hover:bg-[#1a2720]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={registering}
                  className="px-5 py-2 rounded bg-[#00ff66] text-black font-bold hover:bg-[#1aff75] disabled:opacity-50"
                >
                  {registering ? 'Registering...' : 'Register Node'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
