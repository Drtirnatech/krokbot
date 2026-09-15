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
  diskUsedGb?: number;
  diskTotalGb?: number;
  diskPercent?: number;
  containerFootprintGb?: number;
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

export interface PendingNode {
  id: string;
  token: string;
  hostname: string;
  ip_address: string;
  arch: string;
  ram_total_gb: number;
  ram_free_gb: number;
  disk_free_gb: number;
  gpu_info?: string | null;
  status: 'pending_approval' | 'approved' | 'streaming' | 'failed' | 'completed';
  selected_model?: string | null;
  target_node_name?: string | null;
  progress_percent: number;
  progress_status?: string | null;
  last_heartbeat: string;
  created_at: string;
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

  // Deployment & Enrollment state
  const [pendingNodes, setPendingNodes] = useState<PendingNode[]>([]);
  const [enrollModalOpen, setEnrollModalOpen] = useState(false);
  const [enrollTab, setEnrollTab] = useState<'automated' | 'manual' | 'direct'>('automated');
  const [shellFormat, setShellFormat] = useState<'powershell' | 'bash' | 'prompt_ps' | 'prompt_bash' | 'single'>('powershell');
  const [generatedToken, setGeneratedToken] = useState<string | null>(null);
  const [generatedCommand, setGeneratedCommand] = useState<string | null>(null);
  const [generatedBashCommand, setGeneratedBashCommand] = useState<string | null>(null);
  const [generatedPsCommand, setGeneratedPsCommand] = useState<string | null>(null);
  const [generatedPromptBashCommand, setGeneratedPromptBashCommand] = useState<string | null>(null);
  const [generatedPromptPsCommand, setGeneratedPromptPsCommand] = useState<string | null>(null);
  const [tokenLoading, setTokenLoading] = useState(false);
  const [copiedCommand, setCopiedCommand] = useState(false);
  const [approvingNodeId, setApprovingNodeId] = useState<string | null>(null);
  const [selectedDeployModels, setSelectedDeployModels] = useState<Record<string, string>>({});
  const [customDeployNames, setCustomDeployNames] = useState<Record<string, string>>({});

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

  // Expandable tab states for Edge Devices and Agents
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({
    'node-jetson-primary': true
  });
  const [expandedAgents, setExpandedAgents] = useState<Record<string, boolean>>({
    'krok-prime-01': true
  });

  // Inline prompt runners inside expanded agent drawers
  const [inlinePrompts, setInlinePrompts] = useState<Record<string, string>>({});
  const [inlineExecuting, setInlineExecuting] = useState<Record<string, boolean>>({});
  const [inlineOutputs, setInlineOutputs] = useState<Record<string, any>>({});

  // Edge SysOps & Process Inspector state
  const [processModalNode, setProcessModalNode] = useState<NodeRecord | null>(null);
  const [processList, setProcessList] = useState<any[]>([]);
  const [loadingProcesses, setLoadingProcesses] = useState(false);
  const [killingPid, setKillingPid] = useState<number | null>(null);
  const [cleaningNodeId, setCleaningNodeId] = useState<string | null>(null);
  const [cleanupModalData, setCleanupModalData] = useState<{
    nodeName: string;
    memoryRecoveredMb: number;
    tempFilesPruned: number;
    mallocTrimmed: boolean;
    timestamp: string;
  } | null>(null);
  const [broadcastMode, setBroadcastMode] = useState(false);
  const [broadcastIncludeSubagents, setBroadcastIncludeSubagents] = useState(false);
  const [watchdogPolicies, setWatchdogPolicies] = useState<Record<string, any[]>>({});
  const [nodeThermals, setNodeThermals] = useState<Record<string, any>>({});

  // Confirmation selection notices for immediate visual feedback
  const [selectedConfirmation, setSelectedConfirmation] = useState<{
    label: string;
    value: string;
    status: 'processing' | 'done';
  } | null>(null);

  // Renaming Modal State
  const [renameModalOpen, setRenameModalOpen] = useState(false);
  const [renameType, setRenameType] = useState<'node' | 'agent'>('node');
  const [renameTargetId, setRenameTargetId] = useState('');
  const [renameNodeId, setRenameNodeId] = useState('');
  const [renameNameInput, setRenameNameInput] = useState('');
  const [renaming, setRenaming] = useState(false);

  // Custom Deletion Modal State
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteType, setDeleteType] = useState<'node' | 'agent'>('agent');
  const [deleteTargetId, setDeleteTargetId] = useState('');
  const [deleteTargetName, setDeleteTargetName] = useState('');
  const [deleteNodeId, setDeleteNodeId] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteComplete, setDeleteComplete] = useState(false);
  const [deleteSteps, setDeleteSteps] = useState<Array<{ step: string; description: string; status: 'pending' | 'running' | 'success' | 'warning' | 'error'; instructions?: string }>>([]);
 
  const openDeleteModal = (type: 'node' | 'agent', targetId: string, targetName: string, nodeId: string) => {
    setDeleteType(type);
    setDeleteTargetId(targetId);
    setDeleteTargetName(targetName);
    setDeleteNodeId(nodeId);
    setDeleteError(null);
    setDeleteComplete(false);
    setDeleting(false);
    setDeleteSteps(
      type === 'agent'
        ? [
            { step: 'supervisor_contact', description: 'Contacting node supervisor & checking status', status: 'pending' },
            { step: 'process_termination', description: 'Stopping worker process / container', status: 'pending' },
            { step: 'docker_teardown', description: 'Purging container workspace & Docker resources', status: 'pending' },
            { step: 'database_cleanup', description: 'Updating C2 fleet database & audit log', status: 'pending' }
          ]
        : [
            { step: 'remote_disenroll', description: 'Sending disenrollment signal to edge node', status: 'pending' },
            { step: 'container_teardown', description: 'Terminating active container connections', status: 'pending' },
            { step: 'database_cascade_purge', description: 'Purging node, subagents, and telemetry from C2 DB', status: 'pending' }
          ]
    );
    setDeleteModalOpen(true);
  };

  const handleExecuteDelete = async () => {
    setDeleting(true);
    setDeleteError(null);

    setDeleteSteps(prev => prev.map((s, i) => i === 0 ? { ...s, status: 'running' } : s));

    try {
      const url = deleteType === 'node'
        ? `/api/fleet/nodes/${encodeURIComponent(deleteTargetId)}`
        : `/api/fleet/nodes/${encodeURIComponent(deleteNodeId)}/agents/${encodeURIComponent(deleteTargetId)}`;

      const res = await fetch(url, { method: 'DELETE' });
      const data = await res.json();

      if (!res.ok) {
        setDeleteError(data.message || 'Delete operation failed.');
        setDeleteSteps(prev => prev.map(s => s.status === 'running' ? { ...s, status: 'error' } : s));
        return;
      }

      if (data.steps && Array.isArray(data.steps)) {
        setDeleteSteps(data.steps.map((st: any) => ({
          step: st.step,
          description: st.description,
          status: st.status as 'success' | 'warning' | 'error',
          instructions: st.instructions
        })));
      } else {
        setDeleteSteps(prev => prev.map(s => ({ ...s, status: 'success' })));
      }

      setDeleteComplete(true);
      await fetchFleet();
      await fetchAuditLogs();
    } catch (err: any) {
      setDeleteError(err.message || 'Network error during deletion');
      setDeleteSteps(prev => prev.map(s => s.status === 'running' ? { ...s, status: 'error' } : s));
    } finally {
      setDeleting(false);
    }
  };

  const openRenameModal = (type: 'node' | 'agent', targetId: string, currentName: string, nodeId: string) => {
    setRenameType(type);
    setRenameTargetId(targetId);
    setRenameNodeId(nodeId);
    setRenameNameInput(currentName);
    setRenameModalOpen(true);
  };

  const handleRenameSubmit = async () => {
    if (!renameNameInput.trim()) return;
    setRenaming(true);
    try {
      const url = renameType === 'node'
        ? `/api/fleet/nodes/${renameNodeId}/rename`
        : `/api/fleet/nodes/${renameNodeId}/agents/${renameTargetId}/rename`;

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: renameNameInput.trim() })
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.message || 'Failed to rename target');
      }

      setRenameModalOpen(false);
      await fetchFleet();
      await fetchAuditLogs();
    } catch (err: any) {
      alert(`Rename Error: ${err.message}`);
    } finally {
      setRenaming(false);
    }
  };

  const [inlineConfirmations, setInlineConfirmations] = useState<Record<string, {
    label: string;
    value: string;
    status: 'processing' | 'done';
  }>>({});

  const toggleNode = (nodeId: string) => {
    setExpandedNodes(prev => ({ ...prev, [nodeId]: !prev[nodeId] }));
  };

  const toggleAgent = (agentId: string) => {
    setExpandedAgents(prev => ({ ...prev, [agentId]: !prev[agentId] }));
  };

  const expandAllNodes = () => {
    const all: Record<string, boolean> = {};
    nodes.forEach(n => { all[n.id] = true; });
    setExpandedNodes(all);
  };

  const collapseAllNodes = () => {
    setExpandedNodes({});
  };

  const expandAllAgents = (node: NodeRecord) => {
    setExpandedAgents(prev => {
      const next = { ...prev };
      (node.agents || []).forEach(a => { next[a.id] = true; });
      return next;
    });
  };

  const collapseAllAgents = (node: NodeRecord) => {
    setExpandedAgents(prev => {
      const next = { ...prev };
      (node.agents || []).forEach(a => { next[a.id] = false; });
      return next;
    });
  };

  const handleInlinePromptSubmit = async (nodeId: string, agentId: string, port: number) => {
    const prompt = (inlinePrompts[agentId] || '').trim();
    if (!prompt) return;

    setInlineConfirmations(prev => {
      const next = { ...prev };
      delete next[agentId];
      return next;
    });
    setInlineExecuting(prev => ({ ...prev, [agentId]: true }));
    try {
      const res = await fetch(`/api/fleet/nodes/${nodeId}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, agentId, port })
      });
      const data = await res.json();
      setInlineOutputs(prev => ({ ...prev, [agentId]: data }));
      await fetchAuditLogs();
    } catch (err: any) {
      setInlineOutputs(prev => ({ ...prev, [agentId]: { status: 'error', message: err.message } }));
    } finally {
      setInlineExecuting(prev => ({ ...prev, [agentId]: false }));
    }
  };

  const handleConfirmOption = async (optionValue: string, optionLabel?: string) => {
    if (!targetNode) return;
    const label = optionLabel || (optionValue === 'saved' || optionValue === 'save' ? '💾 Save to Script Assets Library' : '⚡ One-Time Only');
    
    // 1. Immediately record selection and show notice (buttons disappear instantly!)
    setSelectedConfirmation({
      label,
      value: optionValue,
      status: 'processing'
    });
    setCommandExecuting(true);

    const promptToRun = commandOutput?.result?.original_prompt || commandPrompt || optionValue;

    try {
      const res = await fetch(`/api/fleet/nodes/${targetNode}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: promptToRun,
          save_mode: optionValue,
          agentId: targetAgent?.id,
          port: targetAgent?.port
        })
      });
      const data = await res.json();
      setCommandOutput(data);
      setSelectedConfirmation({
        label,
        value: optionValue,
        status: 'done'
      });
      await fetchAuditLogs();
    } catch (err: any) {
      setCommandOutput({ status: 'error', message: err.message });
      setSelectedConfirmation(null);
    } finally {
      setCommandExecuting(false);
    }
  };

  const handleInlineConfirmOption = async (nodeId: string, agentId: string, port: number, optionValue: string, optionLabel?: string) => {
    const label = optionLabel || (optionValue === 'saved' || optionValue === 'save' ? '💾 Save to Script Assets Library' : '⚡ One-Time Only');
    
    // 1. Immediately record selection and show notice (buttons disappear instantly!)
    setInlineConfirmations(prev => ({
      ...prev,
      [agentId]: { label, value: optionValue, status: 'processing' }
    }));
    setInlineExecuting(prev => ({ ...prev, [agentId]: true }));

    const promptToRun = inlineOutputs[agentId]?.result?.original_prompt || inlinePrompts[agentId] || optionValue;

    try {
      const res = await fetch(`/api/fleet/nodes/${nodeId}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: promptToRun,
          save_mode: optionValue,
          agentId,
          port
        })
      });
      const data = await res.json();
      setInlineOutputs(prev => ({ ...prev, [agentId]: data }));
      setInlineConfirmations(prev => ({
        ...prev,
        [agentId]: { label, value: optionValue, status: 'done' }
      }));
      await fetchAuditLogs();
    } catch (err: any) {
      setInlineOutputs(prev => ({ ...prev, [agentId]: { status: 'error', message: err.message } }));
      setInlineConfirmations(prev => {
        const next = { ...prev };
        delete next[agentId];
        return next;
      });
    } finally {
      setInlineExecuting(prev => ({ ...prev, [agentId]: false }));
    }
  };

  // Fetch Fleet Nodes & Status
  const fetchFleet = useCallback(async () => {
    try {
      const res = await fetch('/api/fleet/nodes');
      if (!res.ok) throw new Error(`Failed to fetch fleet: ${res.statusText}`);
      const data = await res.json();
      setNodes(data.nodes || []);
      setLastRefreshed(new Date().toLocaleTimeString());
      setError(null);

      // Fetch sysops diagnostics and watchdog policies
      (data.nodes || []).forEach((n: NodeRecord) => {
        fetchNodeSysops(n.id);
      });

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

  // Fetch Pending Edge Nodes (Approval Queue)
  const fetchPendingNodes = useCallback(async () => {
    try {
      const res = await fetch('/api/fleet/enroll/pending');
      if (res.ok) {
        const data = await res.json();
        setPendingNodes(data.pending_nodes || []);
      }
    } catch {
      // ignore
    }
  }, []);

  // Initial load & Polling Loop
  useEffect(() => {
    fetchFleet();
    fetchAuditLogs();
    fetchPendingNodes();

    const interval = setInterval(() => {
      if (autoRefresh) {
        fetchFleet();
        fetchAuditLogs();
        fetchPendingNodes();
      }
    }, 4000);

    return () => clearInterval(interval);
  }, [fetchFleet, fetchAuditLogs, fetchPendingNodes, autoRefresh]);

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

  // Permanently Remove Agent
  const handleDeleteAgent = (nodeId: string, agentId: string, agentName: string) => {
    openDeleteModal('agent', agentId, agentName, nodeId);
  };

  // Permanently Remove Node from Fleet
  const handleDeleteNode = (nodeId: string, nodeName: string) => {
    openDeleteModal('node', nodeId, nodeName, nodeId);
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
      // Adaptive rapid follow-up sweeps at +1.5s, +3.5s, and +5.5s to capture stabilized working set & active model immediately after llama.cpp reloads
      setTimeout(() => { fetchFleet(); fetchAuditLogs(); }, 1500);
      setTimeout(() => { fetchFleet(); fetchAuditLogs(); }, 3500);
      setTimeout(() => { fetchFleet(); fetchAuditLogs(); }, 5500);
    } catch (err: any) {
      alert(`Switch Model Error: ${err.message}`);
    } finally {
      setSwitchingModel(false);
    }
  };

  // Open Process Inspector Modal
  const openProcessModal = async (node: NodeRecord) => {
    setProcessModalNode(node);
    setLoadingProcesses(true);
    try {
      const res = await fetch(`/api/fleet/nodes/${node.id}/sysops/processes`);
      if (res.ok) {
        const data = await res.json();
        setProcessList(data.processes || []);
      }
    } catch {
      setProcessList([]);
    } finally {
      setLoadingProcesses(false);
    }
  };

  // Terminate Process Action
  const handleKillProcess = async (nodeId: string, pid: number) => {
    if (!confirm(`Are you sure you want to terminate process PID ${pid}?`)) return;
    setKillingPid(pid);
    try {
      const res = await fetch(`/api/fleet/nodes/${nodeId}/sysops/processes/${pid}/kill`, {
        method: 'POST'
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || 'Failed to terminate process');
      // Refresh process list
      const pRes = await fetch(`/api/fleet/nodes/${nodeId}/sysops/processes`);
      if (pRes.ok) {
        const pData = await pRes.json();
        setProcessList(pData.processes || []);
      }
      await fetchAuditLogs();
    } catch (err: any) {
      alert(`Process Action Error: ${err.message}`);
    } finally {
      setKillingPid(null);
    }
  };

  // Run System Memory & Temporary Cache Cleanup
  const handleRunCleanup = async (nodeTarget: NodeRecord | string) => {
    const nodeId = typeof nodeTarget === 'string' ? nodeTarget : nodeTarget.id;
    const nodeObj = typeof nodeTarget === 'string' ? nodes.find(n => n.id === nodeId) : nodeTarget;
    const nodeName = nodeObj?.name || nodeId;

    setCleaningNodeId(nodeId);
    try {
      const res = await fetch(`/api/fleet/nodes/${nodeId}/sysops/cleanup`, {
        method: 'POST'
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || 'Cleanup failed');
      const resData = data.result || {};
      setCleanupModalData({
        nodeName,
        memoryRecoveredMb: resData.memory_recovered_mb || 0,
        tempFilesPruned: resData.temp_files_pruned || 0,
        mallocTrimmed: resData.malloc_trimmed ?? true,
        timestamp: resData.timestamp || new Date().toLocaleTimeString()
      });
      await fetchFleet();
      await fetchAuditLogs();
    } catch (err: any) {
      setError(`Cleanup Error: ${err.message}`);
    } finally {
      setCleaningNodeId(null);
    }
  };

  // Fetch Edge Node SysOps Telemetry & Watchdog
  const fetchNodeSysops = useCallback(async (nodeId: string) => {
    try {
      const [tRes, wRes] = await Promise.all([
        fetch(`/api/fleet/nodes/${nodeId}/sysops/telemetry`),
        fetch(`/api/fleet/nodes/${nodeId}/sysops/watchdog`)
      ]);
      if (tRes.ok) {
        const tData = await tRes.json();
        if (tData.diagnostics?.thermals) {
          setNodeThermals(prev => ({ ...prev, [nodeId]: tData.diagnostics.thermals }));
        }
      }
      if (wRes.ok) {
        const wData = await wRes.json();
        if (wData.policies) {
          setWatchdogPolicies(prev => ({ ...prev, [nodeId]: wData.policies }));
        }
      }
    } catch {
      // ignore
    }
  }, []);

  // Toggle Self-Healing Watchdog Policy
  const handleToggleWatchdog = async (nodeId: string, policyId: string) => {
    try {
      const res = await fetch(`/api/fleet/nodes/${nodeId}/sysops/watchdog`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ policyId })
      });
      if (res.ok) {
        await fetchNodeSysops(nodeId);
        await fetchAuditLogs();
      }
    } catch (err: any) {
      alert(`Watchdog toggle error: ${err.message}`);
    }
  };

  // Generate Single-Use Enrollment Token
  const handleGenerateEnrollmentToken = async () => {
    setTokenLoading(true);
    try {
      const res = await fetch('/api/fleet/enroll/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expiry_minutes: 60 })
      });
      const data = await res.json();
      if (res.ok && data.token) {
        setGeneratedToken(data.token);
        setGeneratedCommand(data.docker_command);
        setGeneratedBashCommand(data.bash_command || data.docker_command);
        setGeneratedPsCommand(data.powershell_command || data.docker_command);
        setGeneratedPromptBashCommand(data.prompt_bash_command || data.docker_command);
        setGeneratedPromptPsCommand(data.prompt_powershell_command || data.docker_command);
        setCopiedCommand(false);
      } else {
        alert(`Token generation failed: ${data.message || 'Unknown error'}`);
      }
    } catch (err: any) {
      alert(`Token generation failed: ${err.message}`);
    } finally {
      setTokenLoading(false);
    }
  };

  // Approve Pending Edge Node Deployment
  const handleApproveNode = async (nodeId: string) => {
    const model = selectedDeployModels[nodeId] || 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf';
    const targetName = customDeployNames[nodeId] || undefined;
    setApprovingNodeId(nodeId);
    try {
      const res = await fetch('/api/fleet/enroll/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          node_id: nodeId,
          selected_model: model,
          target_name: targetName
        })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.message || 'Approval failed');
      }
      await fetchPendingNodes();
      await fetchFleet();
      await fetchAuditLogs();
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    } finally {
      setApprovingNodeId(null);
    }
  };

  // Reject Pending Edge Node
  const handleRejectPendingNode = async (nodeId: string) => {
    if (!confirm(`Are you sure you want to reject and cancel deployment for pending node ${nodeId}?`)) return;
    try {
      const res = await fetch(`/api/fleet/enroll/pending?id=${encodeURIComponent(nodeId)}`, {
        method: 'DELETE'
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.message || 'Rejection failed');
      }
      await fetchPendingNodes();
    } catch (err: any) {
      alert(`Reject error: ${err.message}`);
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

  // Execute Command Dispatch (Supports Single Agent and Fleet Broadcast)
  const handleSendCommand = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commandPrompt.trim()) return;
    setCommandExecuting(true);
    setCommandOutput(null);
    setSelectedConfirmation(null);

    try {
      if (broadcastMode) {
        const res = await fetch('/api/fleet/broadcast', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt: commandPrompt.trim(),
            include_subagents: broadcastIncludeSubagents
          })
        });
        const data = await res.json();
        setCommandOutput({ status: 'success', broadcast: true, result: data });
        await fetchAuditLogs();
      } else {
        if (!targetNode) throw new Error('Please select a target node or enable Fleet Broadcast');
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
      }
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
            onClick={() => setEnrollModalOpen(true)}
            className="text-xs px-3.5 py-1.5 rounded bg-[#00ff66] text-[#050a07] font-bold hover:bg-[#1aff75] transition-all shadow-[0_0_15px_rgba(0,255,102,0.3)] cursor-pointer flex items-center gap-1.5"
          >
            <span>+</span>
            <span>ENROLL / DEPLOY NODE</span>
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
        {/* PENDING APPROVAL QUEUE */}
        {pendingNodes.length > 0 && (
          <section className="p-5 rounded-xl bg-[#141208] border border-[#ffb000]/60 space-y-4 shadow-[0_0_25px_rgba(255,176,0,0.15)]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="w-3 h-3 rounded-full bg-[#ffb000] animate-ping"></span>
                <h2 className="text-sm font-bold tracking-wider text-[#ffb000] uppercase flex items-center gap-2">
                  <span>///</span> Pending Nodes — Operator Approval Required ({pendingNodes.length})
                </h2>
              </div>
              <span className="text-[11px] text-[#ffb000]/80 font-mono">
                Outbound bootstrap nodes awaiting deployment confirmation
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {pendingNodes.map((pNode) => {
                const isStreaming = pNode.status === 'streaming' || pNode.status === 'approved';
                const currentModel = selectedDeployModels[pNode.id] || 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf';

                return (
                  <div key={pNode.id} className="p-4 rounded-lg bg-[#0c0f0d] border border-[#2b2915] space-y-3.5">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-white font-mono">{pNode.hostname}</span>
                          <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-[#212417] text-[#ffb000] border border-[#ffb000]/30 font-bold">
                            {pNode.arch.toUpperCase()}
                          </span>
                        </div>
                        <span className="text-[11px] text-[#7a8a81] font-mono">{pNode.ip_address} • ID: {pNode.id}</span>
                      </div>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase font-bold ${
                        isStreaming
                          ? 'bg-[#0e291d] text-[#00ff66] border-[#00ff66]/40 animate-pulse'
                          : 'bg-[#291f0e] text-[#ffb000] border-[#ffb000]/40'
                      }`}>
                        {pNode.status.replace('_', ' ')}
                      </span>
                    </div>

                    {/* Hardware Specs Grid */}
                    <div className="grid grid-cols-3 gap-2 text-center text-xs font-mono">
                      <div className="p-2 rounded bg-[#070a08] border border-[#18261e]">
                        <span className="text-[10px] text-[#5b7a6b] block">RAM</span>
                        <span className="text-white font-bold">{pNode.ram_total_gb.toFixed(1)} GB</span>
                        <span className="text-[9px] text-[#00ff66] block">({pNode.ram_free_gb.toFixed(1)} GB Free)</span>
                      </div>
                      <div className="p-2 rounded bg-[#070a08] border border-[#18261e]">
                        <span className="text-[10px] text-[#5b7a6b] block">FREE DISK</span>
                        <span className="text-white font-bold">{pNode.disk_free_gb.toFixed(0)} GB</span>
                        <span className="text-[9px] text-[#00e5ff] block">Required: &gt;10 GB</span>
                      </div>
                      <div className="p-2 rounded bg-[#070a08] border border-[#18261e]">
                        <span className="text-[10px] text-[#5b7a6b] block">ACCELERATOR</span>
                        <span className="text-white font-bold text-[11px] truncate block" title={pNode.gpu_info || 'CPU Only'}>
                          {pNode.gpu_info || 'CPU Only'}
                        </span>
                      </div>
                    </div>

                    {/* Action Controls */}
                    {!isStreaming ? (
                      <div className="space-y-2.5 pt-1">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                          <div>
                            <label className="text-[10px] text-[#8aa89b] block mb-1">TARGET NODE NAME</label>
                            <input
                              type="text"
                              value={customDeployNames[pNode.id] ?? pNode.hostname}
                              onChange={(e) => setCustomDeployNames({ ...customDeployNames, [pNode.id]: e.target.value })}
                              placeholder="e.g. Field Sentinel Alpha"
                              className="w-full bg-[#070a08] border border-[#1f3126] rounded px-2.5 py-1.5 text-white font-mono text-xs focus:border-[#00ff66] outline-none"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] text-[#8aa89b] block mb-1">SELECT LLM MODEL</label>
                            <select
                              value={currentModel}
                              onChange={(e) => setSelectedDeployModels({ ...selectedDeployModels, [pNode.id]: e.target.value })}
                              className="w-full bg-[#070a08] border border-[#1f3126] rounded px-2 py-1.5 text-white font-mono text-xs focus:border-[#00ff66] outline-none"
                            >
                              <option value="qwen2.5-coder-1.5b-instruct-q4_k_m.gguf">Qwen2.5-Coder 1.5B (Edge/Jetson, 1.1 GB)</option>
                              <option value="qwen2.5-coder-7b-instruct-q4_k_m.gguf">Qwen2.5-Coder 7B (Workstation, 4.4 GB)</option>
                            </select>
                          </div>
                        </div>

                        <div className="flex items-center justify-end gap-2 pt-1">
                          <button
                            type="button"
                            onClick={() => handleRejectPendingNode(pNode.id)}
                            className="px-3 py-1.5 rounded bg-[#1f1214] hover:bg-[#2b1619] border border-[#ff3344]/30 text-[#ff5566] text-xs font-bold transition-colors cursor-pointer"
                          >
                            ✕ Reject
                          </button>
                          <button
                            type="button"
                            disabled={approvingNodeId === pNode.id}
                            onClick={() => handleApproveNode(pNode.id)}
                            className="px-4 py-1.5 rounded bg-[#00ff66] hover:bg-[#1aff75] text-[#050a07] text-xs font-bold transition-all shadow-[0_0_12px_rgba(0,255,102,0.3)] cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
                          >
                            {approvingNodeId === pNode.id ? 'Approving...' : '✓ Approve & Stream Deploy'}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2 pt-1">
                        <div className="flex items-center justify-between text-xs font-mono">
                          <span className="text-[#00ff66] font-bold">STATUS: {pNode.progress_status || 'STREAMING'}</span>
                          <span className="text-[#00e5ff] font-bold">{pNode.progress_percent.toFixed(0)}%</span>
                        </div>
                        <div className="w-full h-2.5 rounded-full bg-[#0a140e] border border-[#1a3323] overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-[#00ff66] to-[#00e5ff] transition-all duration-500 rounded-full"
                            style={{ width: `${Math.max(5, pNode.progress_percent)}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-[#5b7a6b] block">
                          Streaming container image tarball and model weights to blank node...
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* FLEET NODES SECTION */}
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-semibold tracking-wider text-[#00ff66] flex items-center gap-2 uppercase">
                <span className="text-[#5b7a6b]">///</span> Edge Devices &amp; Master Container Nodes ({nodes.length})
              </h2>
              <div className="flex items-center gap-1.5 text-[11px]">
                <button
                  type="button"
                  onClick={expandAllNodes}
                  className="px-2 py-0.5 rounded bg-[#101a14] hover:bg-[#182920] border border-[#1e3025] text-[#7da895] hover:text-[#00ff66] transition-colors cursor-pointer"
                  title="Expand all edge device accordions"
                >
                  Expand All
                </button>
                <button
                  type="button"
                  onClick={collapseAllNodes}
                  className="px-2 py-0.5 rounded bg-[#101a14] hover:bg-[#182920] border border-[#1e3025] text-[#7da895] hover:text-[#ffb000] transition-colors cursor-pointer"
                  title="Collapse all edge device accordions to summary lines"
                >
                  Collapse All
                </button>
              </div>
            </div>
            <span className="text-[11px] text-[#5b7a6b]">Last telemetry refresh: {lastRefreshed || 'Just now'}</span>
          </div>

          {loading ? (
            <div className="p-12 border border-[#16221b] rounded-lg bg-[#0a0f0c] text-center text-sm text-[#5b7a6b]">
              <div className="inline-block w-6 h-6 border-2 border-[#00ff66] border-t-transparent rounded-full animate-spin mb-3"></div>
              <div>CONNECTING TO KROKBOT FLEET &amp; IN-CONTAINER ARBITER...</div>
            </div>
          ) : nodes.length === 0 ? (
            <div className="p-12 border border-[#16221b] rounded-lg bg-[#0a0f0c] text-center space-y-3">
              <p className="text-sm text-[#7a998b]">No edge nodes registered yet.</p>
              <button
                onClick={() => setEnrollModalOpen(true)}
                className="px-4 py-2 rounded bg-[#00ff66] text-black font-bold text-xs hover:bg-[#1aff75] transition-all cursor-pointer shadow-[0_0_12px_rgba(0,255,102,0.3)]"
              >
                Register a new Agent
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {nodes.map((node) => {
                const health = node.liveHealth;
                const isOnline = node.status === 'online';
                const nodeAgents = node.agents || [];
                const isNodeExpanded = !!expandedNodes[node.id];

                return (
                  <div
                    key={node.id}
                    className="border border-[#18261e] hover:border-[#00ff66]/40 rounded-xl bg-[#0b100d] overflow-hidden transition-all shadow-lg"
                  >
                    {/* Edge Device Accordion Header / Contracted Summary Line */}
                    <div
                      onClick={() => toggleNode(node.id)}
                      className={`p-3.5 sm:p-4 bg-[#0d1410] flex flex-wrap items-center justify-between gap-3 cursor-pointer select-none transition-colors border-b ${
                        isNodeExpanded ? 'border-[#18261e]' : 'border-transparent hover:bg-[#101813]'
                      }`}
                      title={isNodeExpanded ? 'Click to collapse edge device tab' : 'Click to expand edge device tab'}
                    >
                      {/* Left: Chevron + Status Indicator + Name + ID + IP */}
                      <div className="flex items-center gap-2.5 sm:gap-3.5 flex-wrap">
                        {/* Chevron Indicator */}
                        <div
                          className={`w-6 h-6 rounded flex items-center justify-center bg-[#131f18] border border-[#1e3327] text-[#00ff66] text-xs font-mono transition-transform duration-200 ${
                            isNodeExpanded ? 'rotate-90 text-[#00ff66]' : 'text-[#7da895]'
                          }`}
                        >
                          ▶
                        </div>

                        {/* Status Pulse */}
                        <span
                          className={`w-2.5 h-2.5 rounded-full ${
                            isOnline
                              ? 'bg-[#00ff66] shadow-[0_0_8px_#00ff66] radar-pulse'
                              : 'bg-[#ff3344]'
                          }`}
                        ></span>

                        {/* Device Name and Identifier */}
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="text-sm sm:text-base font-bold text-white tracking-wide">{node.name}</h3>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                openRenameModal('node', node.id, node.name, node.id);
                              }}
                              className="text-[#5b7a6b] hover:text-[#00ff66] text-xs p-1 rounded hover:bg-[#15231b] transition-colors cursor-pointer"
                              title={`Rename Edge Node ${node.name}`}
                            >
                              ✏️
                            </button>
                            <span className="text-[10px] px-2 py-0.5 rounded bg-[#15231b] text-[#7da895] border border-[#23382c] font-mono">
                              {node.id}
                            </span>
                          </div>
                          <div className="text-[11px] text-[#5b7a6b] flex items-center gap-2">
                            <span className="font-mono text-[#8aa89b]">{node.ip_address}</span>
                            <span>•</span>
                            <span className={isOnline ? 'text-[#00ff66] font-semibold' : 'text-[#ff3344]'}>
                              {node.status.toUpperCase()}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Middle & Right: Rich Telemetry Summary Line (Visible when Contracted AND Expanded) */}
                      <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
                        {/* CPU Chip */}
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#090e0b] border border-[#17261e] text-[11px]">
                          <span className="text-[#5b7a6b]">CPU:</span>
                          <span className="text-[#00ff66] font-bold font-mono">
                            {health ? `${health.cpuPercent.toFixed(1)}%` : '0.0%'}
                          </span>
                        </div>

                        {/* RAM Chip */}
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#090e0b] border border-[#17261e] text-[11px]">
                          <span className="text-[#5b7a6b]">RAM:</span>
                          <span className="text-[#00e5ff] font-bold font-mono">
                            {health ? `${health.memoryUsedGb.toFixed(1)}GB` : '0GB'}
                          </span>
                          <span className="text-[10px] text-[#5b7a6b]">
                            ({health ? health.memoryPercent.toFixed(0) : 0}%)
                          </span>
                        </div>

                        {/* Shared Model Chip */}
                        <div
                          className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#090e0b] border border-[#17261e] text-[11px] max-w-[220px] truncate"
                          title={`Active Shared Model: ${health?.activeModel || node.active_model}`}
                        >
                          <span className="text-[#ffb000]">🧠</span>
                          <span className="text-[#d8a834] truncate font-mono text-[10px]">
                            {(health?.activeModel || node.active_model).split('/').pop() || (health?.activeModel || node.active_model)}
                          </span>
                        </div>

                        {/* SoC Thermal Chip */}
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#090e0b] border border-[#17261e] text-[11px]" title="Edge SoC Hardware Thermal Package">
                          <span className="text-[#ffb000]">🌡️</span>
                          <span className={`font-mono font-bold ${
                            (nodeThermals[node.id]?.max_temp_c || 46.2) >= 75.0 ? 'text-[#ff3344] animate-pulse' : 'text-[#ffb000]'
                          }`}>
                            {nodeThermals[node.id]?.max_temp_c ? `${nodeThermals[node.id].max_temp_c.toFixed(1)}°C` : '46.2°C'}
                          </span>
                        </div>

                        {/* Active Agents Badge */}
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#122018] border border-[#1e3829] text-[11px]">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#00ff66]"></span>
                          <span className="text-[#00ff66] font-bold font-mono">
                            {nodeAgents.filter(a => a.status === 'running').length}/{nodeAgents.length}
                          </span>
                          <span className="text-[#7da895] text-[10px] uppercase">Agents</span>
                        </div>

                        {/* Quick Action Buttons */}
                        <div className="flex items-center gap-1.5 ml-1">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              openProcessModal(node);
                            }}
                            className="px-2.5 py-1 rounded text-xs bg-[#0b1a20] hover:bg-[#122833] border border-[#00e5ff]/40 text-[#00e5ff] font-medium transition-colors flex items-center gap-1 cursor-pointer"
                            title="Inspect live processes running on edge node"
                          >
                            <span>⚙️ SysOps</span>
                          </button>
                          <button
                            type="button"
                            disabled={cleaningNodeId === node.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRunCleanup(node);
                            }}
                            className="px-2.5 py-1 rounded text-xs bg-[#102419] hover:bg-[#183625] border border-[#00ff66]/30 text-[#00ff66] font-medium transition-colors flex items-center gap-1 cursor-pointer disabled:opacity-50"
                            title="Trigger temporary storage pruning & memory trim"
                          >
                            <span>{cleaningNodeId === node.id ? '🧹...' : '🧹 Clean'}</span>
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              openModelModal(node);
                            }}
                            className="px-2.5 py-1 rounded text-xs bg-[#131f18] hover:bg-[#1d2f24] border border-[#213529] text-[#ffb000] font-medium transition-colors flex items-center gap-1 cursor-pointer"
                            title="Switch shared in-container model"
                          >
                            <span>🧠 Model</span>
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              openDeployModal(node);
                            }}
                            className="px-2.5 py-1 rounded text-xs bg-[#0e271a] hover:bg-[#143524] border border-[#00ff66]/40 text-[#00ff66] font-semibold transition-colors flex items-center gap-1 cursor-pointer"
                            title="Deploy an additional agent inside container"
                          >
                            <span>+ Deploy</span>
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteNode(node.id, node.name);
                            }}
                            className="px-2 py-1 rounded text-xs bg-[#241315] hover:bg-[#3d181c] border border-[#ff3344]/30 text-[#ff5566] font-medium transition-colors cursor-pointer"
                            title="Remove edge node from fleet"
                          >
                            <span>🗑️</span>
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Expanded Tab Content */}
                    {isNodeExpanded && (
                      <div>
                        {/* Node Metrics & Detailed Hardware Resources */}
                        <div className="p-4 sm:p-5 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3.5 border-b border-[#141f19] bg-[#080d0a]/60">
                          {/* CPU Usage */}
                          <div className="p-3 rounded-lg bg-[#0c1310] border border-[#16231c] space-y-1.5">
                            <div className="flex justify-between text-[11px] text-[#5b7a6b]">
                              <span>CONTAINER CPU</span>
                              <span className="text-white font-bold font-mono">{health ? `${health.cpuPercent.toFixed(1)}%` : '0.0%'}</span>
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
                              <span className="text-white font-bold font-mono">{health ? `${health.memoryUsedGb.toFixed(2)} GB (${health.memoryPercent.toFixed(0)}%)` : '0.0 GB'}</span>
                            </div>
                            <div className="w-full bg-[#142019] h-2 rounded-full overflow-hidden">
                              <div
                                className="bg-[#00e5ff] h-full transition-all duration-500 shadow-[0_0_8px_#00e5ff]"
                                style={{ width: `${Math.min(100, Math.max(2, health?.memoryPercent || 0))}%` }}
                              ></div>
                            </div>
                          </div>

                          {/* Host Disk Space Used by Agent */}
                          <div className="p-3 rounded-lg bg-[#0c1310] border border-[#16231c] space-y-1.5">
                            <div className="flex justify-between text-[11px] text-[#5b7a6b]">
                              <span>HOST DISK USED</span>
                              <span className="text-white font-bold font-mono">
                                {health?.containerFootprintGb ? `${health.containerFootprintGb.toFixed(2)} GB` : `${((health?.storageMb || 0) / 1024).toFixed(2)} GB`}
                              </span>
                            </div>
                            <div className="flex justify-between text-[10px] text-[#5b7a6b]">
                              <span>Models: {health ? `${health.storageMb.toFixed(0)} MB` : '0 MB'}</span>
                              <span className="text-[#a0c0b0] font-mono">Base Image: 1.28 GB</span>
                            </div>
                          </div>

                          {/* Active Shared Model */}
                          <div className="p-3 rounded-lg bg-[#0c1310] border border-[#16231c] space-y-1">
                            <span className="text-[11px] text-[#5b7a6b] block">SHARED INFERENCE MODEL</span>
                            <div className="text-xs font-bold text-[#ffb000] truncate font-mono" title={health?.activeModel || node.active_model}>
                              {health?.activeModel || node.active_model}
                            </div>
                            <span className="text-[10px] text-[#5b7a6b]">Llama.cpp Arbiter on 127.0.0.1:5155</span>
                          </div>
                        </div>

                        {/* Edge Node Automated Operations & Optimization */}
                        <div className="p-3.5 sm:p-4 border-b border-[#141f19] bg-[#070b09] flex flex-wrap items-center justify-between gap-3">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold uppercase tracking-wider text-[#7da895] flex items-center gap-1.5">
                              <span>🛡️ Automated Operations &amp; Optimization</span>
                            </span>
                          </div>
                          <div className="flex items-center gap-2 flex-wrap">
                            {(watchdogPolicies[node.id] || [
                              { id: 'storage_pressure', name: 'Auto-Clean (85% Disk)', enabled: true },
                              { id: 'thermal_throttling', name: 'Thermal Guard (75°C)', enabled: true },
                              { id: 'worker_memory_leak', name: 'Memory Leak Recovery (800MB)', enabled: true }
                            ]).map((policy: any) => (
                              <button
                                key={policy.id}
                                type="button"
                                onClick={() => handleToggleWatchdog(node.id, policy.id)}
                                className={`px-2.5 py-1 rounded text-[11px] font-mono border transition-all cursor-pointer flex items-center gap-1.5 ${
                                  policy.enabled
                                    ? 'bg-[#102419] border-[#00ff66]/40 text-[#00ff66] shadow-[0_0_8px_rgba(0,255,102,0.15)]'
                                    : 'bg-[#141a16] border-[#222e26] text-[#5b7a6b]'
                                }`}
                                title={`Click to ${policy.enabled ? 'disable' : 'enable'} watchdog policy`}
                              >
                                <span className={`w-1.5 h-1.5 rounded-full ${policy.enabled ? 'bg-[#00ff66]' : 'bg-[#5b7a6b]'}`}></span>
                                <span>{policy.name}</span>
                                <span className="text-[9px] uppercase font-bold px-1 py-0.2 rounded bg-black/40">
                                  {policy.enabled ? 'ACTIVE' : 'OFF'}
                                </span>
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Co-located Agents in Master Container (Expandable List Format) */}
                        <div className="p-4 sm:p-5 space-y-3">
                          <div className="flex flex-wrap items-center justify-between gap-2 pb-1">
                            <div className="flex items-center gap-2">
                              <h4 className="text-xs font-bold uppercase tracking-wider text-[#a4c5b5] flex items-center gap-2">
                                <span>📦 In-Container Co-Located Agents</span>
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#16241c] text-[#00ff66] border border-[#233a2d] font-mono">
                                  {nodeAgents.filter(a => a.status === 'running').length} Active / {nodeAgents.length} Total
                                </span>
                              </h4>
                            </div>
                            <div className="flex items-center gap-2 text-[11px]">
                              <button
                                type="button"
                                onClick={() => expandAllAgents(node)}
                                className="px-2 py-0.5 rounded bg-[#101a14] hover:bg-[#182920] border border-[#1e3025] text-[#7da895] hover:text-[#00ff66] transition-colors cursor-pointer"
                              >
                                Expand Agents
                              </button>
                              <button
                                type="button"
                                onClick={() => collapseAllAgents(node)}
                                className="px-2 py-0.5 rounded bg-[#101a14] hover:bg-[#182920] border border-[#1e3025] text-[#7da895] hover:text-[#ffb000] transition-colors cursor-pointer"
                              >
                                Collapse Agents
                              </button>
                            </div>
                          </div>

                          {/* Expandable Agent List */}
                          <div className="space-y-2.5">
                            {nodeAgents.length === 0 ? (
                              <div className="p-6 rounded-lg bg-[#080d0a] border border-[#16221b] text-center text-xs text-[#5b7a6b]">
                                No agents deployed on this node. Click &quot;+ Deploy&quot; to spawn an agent.
                              </div>
                            ) : (
                              nodeAgents.map((agent) => {
                                const isPrimary = agent.is_primary === 1 || agent.is_primary === true;
                                const isRunning = agent.status === 'running';
                                const isAgentExpanded = expandedAgents[agent.id] === true;

                                return (
                                  <div
                                    key={agent.id}
                                    className="rounded-lg bg-[#0c120f] border border-[#1a2820] hover:border-[#00ff66]/40 transition-all overflow-hidden"
                                  >
                                    {/* Agent Summary Row (Contracted state) */}
                                    <div
                                      onClick={() => toggleAgent(agent.id)}
                                      className={`p-3 flex flex-wrap items-center justify-between gap-3 cursor-pointer select-none transition-colors ${
                                        isAgentExpanded ? 'bg-[#0f1713] border-b border-[#18261e]' : 'hover:bg-[#101814]'
                                      }`}
                                      title={isAgentExpanded ? 'Click to collapse agent details' : 'Click to expand agent details'}
                                    >
                                      {/* Left: Chevron, Status Dot, Role Badge, Name & ID */}
                                      <div className="flex items-center gap-2.5 sm:gap-3 flex-wrap">
                                        {/* Expand Chevron */}
                                        <span className={`text-xs text-[#00ff66] font-mono transition-transform duration-200 ${isAgentExpanded ? 'rotate-90' : ''}`}>
                                          ▶
                                        </span>

                                        {/* Status Dot */}
                                        <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-[#00ff66] shadow-[0_0_6px_#00ff66]' : 'bg-[#6b7280]'}`}></span>

                                        {/* Role Pill */}
                                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider ${
                                          isPrimary
                                            ? 'bg-[#183523] text-[#00ff66] border border-[#00ff66]/40'
                                            : 'bg-[#1b2533] text-[#70a5ff] border border-[#70a5ff]/30'
                                        }`}>
                                          {isPrimary ? 'PRIMARY' : 'WORKER'}
                                        </span>

                                        {/* Agent Name */}
                                        <span className="text-xs font-bold text-white tracking-wide flex items-center gap-1.5">
                                          <span>{agent.name}</span>
                                          <button
                                            type="button"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              openRenameModal('agent', agent.id, agent.name, node.id);
                                            }}
                                            className="text-[#5b7a6b] hover:text-[#00ff66] text-xs p-0.5 rounded hover:bg-[#15231b] transition-colors cursor-pointer"
                                            title={`Rename agent ${agent.name}`}
                                          >
                                            ✏️
                                          </button>
                                        </span>

                                        {/* Agent ID */}
                                        <span className="text-[10px] text-[#6b8c7c] font-mono px-1.5 py-0.5 rounded bg-[#090e0b] border border-[#16241c]">
                                          {agent.id}
                                        </span>
                                      </div>

                                      {/* Right: Port, PID, Status Pill & Quick Action Buttons */}
                                      <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
                                        {/* Port */}
                                        <span className="text-[11px] text-[#8aa89b] font-mono">
                                          Port: <strong className="text-white">{agent.port}</strong>
                                        </span>

                                        {/* PID */}
                                        {agent.pid && (
                                          <span className="text-[11px] text-[#8aa89b] font-mono hidden sm:inline">
                                            PID: <strong className="text-white">{agent.pid}</strong>
                                          </span>
                                        )}

                                        {/* Status Pill */}
                                        <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold ${
                                          isRunning
                                            ? 'text-[#00ff66] bg-[#14281c] border border-[#00ff66]/30'
                                            : 'text-[#888] bg-[#1a1e1c] border border-[#333]'
                                        }`}>
                                          {agent.status.toUpperCase()}
                                        </span>

                                        {/* Action Buttons */}
                                        <div className="flex items-center gap-1.5">
                                          <button
                                            type="button"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              setTargetNode(node.id);
                                              setTargetAgent({ id: agent.id, port: agent.port });
                                              document.getElementById('c2-terminal')?.scrollIntoView({ behavior: 'smooth' });
                                            }}
                                            className="py-1 px-2.5 rounded bg-[#15231b] hover:bg-[#1e3327] border border-[#273d2f] text-[#00ff66] text-[11px] font-semibold transition-colors flex items-center gap-1 cursor-pointer"
                                            title="Focus in Autonomous Command Console"
                                          >
                                            <span>⚡ Command</span>
                                          </button>

                                          {!isPrimary && isRunning && (
                                            <button
                                              type="button"
                                              onClick={(e) => {
                                                e.stopPropagation();
                                                handleStopAgent(node.id, agent.id);
                                              }}
                                              className="py-1 px-2 rounded bg-[#2a1315] hover:bg-[#3d181c] border border-[#ff3344]/30 text-[#ff5566] text-[11px] transition-colors cursor-pointer"
                                              title="Stop agent process"
                                            >
                                              Stop
                                            </button>
                                          )}

                                          {!isPrimary && (
                                            <button
                                              type="button"
                                              onClick={(e) => {
                                                e.stopPropagation();
                                                handleDeleteAgent(node.id, agent.id, agent.name);
                                              }}
                                              className="py-1 px-2 rounded bg-[#241315] hover:bg-[#3d181c] border border-[#ff3344]/30 text-[#ff5566] text-[11px] font-medium transition-colors cursor-pointer"
                                              title="Permanently remove agent"
                                            >
                                              🗑️
                                            </button>
                                          )}
                                        </div>
                                      </div>
                                    </div>

                                    {/* Agent Detail Drawer (When Expanded) */}
                                    {isAgentExpanded && (
                                      <div className="p-4 bg-[#080d0a] border-t border-[#141f19] space-y-3">
                                        {/* Metadata Strip */}
                                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                                          <div className="p-2.5 rounded bg-[#0b100d] border border-[#16221b] space-y-1">
                                            <span className="text-[10px] text-[#5b7a6b] block">ISOLATED WORKSPACE PATH</span>
                                            <div className="font-mono text-[11px] text-[#a4c5b5] truncate" title={agent.workspace || `/app/workspaces/agent_${agent.id}`}>
                                              {agent.workspace || `/app/workspaces/agent_${agent.id}`}
                                            </div>
                                          </div>

                                          <div className="p-2.5 rounded bg-[#0b100d] border border-[#16221b] space-y-1">
                                            <span className="text-[10px] text-[#5b7a6b] block">INFERENCE ARBITER BACKEND</span>
                                            <div className="font-mono text-[11px] text-[#ffb000] truncate">
                                              Shared llama.cpp (127.0.0.1:5155)
                                            </div>
                                          </div>

                                          <div className="p-2.5 rounded bg-[#0b100d] border border-[#16221b] space-y-1">
                                            <span className="text-[10px] text-[#5b7a6b] block">DIRECT AGENT PROXY ENDPOINT</span>
                                            <div className="font-mono text-[11px] text-[#00e5ff] truncate">
                                              http://{node.ip_address}/api/agents/{agent.id}
                                            </div>
                                          </div>
                                        </div>

                                        {/* Inline Quick Prompt Dispatcher */}
                                        <div className="p-3 rounded bg-[#0b120e] border border-[#192b21] space-y-2">
                                          <div className="flex items-center justify-between text-[11px]">
                                            <span className="text-[#00ff66] font-semibold flex items-center gap-1">
                                              <span>⚡ Quick Prompt:</span>
                                              <span className="text-white font-mono">{agent.id}</span>
                                            </span>
                                            <span className="text-[10px] text-[#5b7a6b]">Execute prompt directly on this agent</span>
                                          </div>

                                          <div className="flex items-center gap-2">
                                            <input
                                              type="text"
                                              value={inlinePrompts[agent.id] || ''}
                                              onChange={(e) => setInlinePrompts({ ...inlinePrompts, [agent.id]: e.target.value })}
                                              onKeyDown={(e) => {
                                                if (e.key === 'Enter') {
                                                  e.preventDefault();
                                                  handleInlinePromptSubmit(node.id, agent.id, agent.port);
                                                }
                                              }}
                                              placeholder={`Enter autonomous command for ${agent.name}...`}
                                              className="flex-1 bg-[#070a08] border border-[#1e3025] rounded px-3 py-1.5 text-xs text-[#00ff66] font-mono outline-none focus:border-[#00ff66]"
                                            />
                                            <button
                                              type="button"
                                              onClick={() => handleInlinePromptSubmit(node.id, agent.id, agent.port)}
                                              disabled={inlineExecuting[agent.id] || !(inlinePrompts[agent.id] || '').trim()}
                                              className="px-3.5 py-1.5 rounded bg-[#00ff66] text-black text-xs font-bold hover:bg-[#1aff75] disabled:opacity-50 transition-colors cursor-pointer"
                                            >
                                              {inlineExecuting[agent.id] ? 'RUNNING...' : 'RUN ↵'}
                                            </button>
                                          </div>

                                          {/* Inline Output Display */}
                                          {inlineOutputs[agent.id] && (
                                            <div className="p-2.5 rounded bg-[#050806] border border-[#16231b] text-xs space-y-2">
                                              <div className="flex justify-between text-[10px] text-[#5b7a6b]">
                                                <span>INLINE EXECUTION RESULT</span>
                                                <span className={inlineOutputs[agent.id].status === 'error' ? 'text-[#ff3344]' : 'text-[#00ff66]'}>
                                                  {inlineOutputs[agent.id].result?.status?.toUpperCase() || inlineOutputs[agent.id].status?.toUpperCase()}
                                                </span>
                                              </div>

                                              {/* Prominent Selection Notice when option clicked */}
                                              {inlineConfirmations[agent.id] && (
                                                <div className={`p-3 rounded border text-xs transition-all flex items-center justify-between gap-3 ${
                                                  inlineConfirmations[agent.id].status === 'processing'
                                                    ? 'bg-[#0f2418] border-[#00ff66] shadow-[0_0_12px_rgba(0,255,102,0.25)]'
                                                    : 'bg-[#0b1610] border-[#00ff66]/40 text-[#c4d6cc]'
                                                }`}>
                                                  <div className="flex items-center gap-2.5">
                                                    {inlineConfirmations[agent.id].status === 'processing' ? (
                                                      <div className="w-4 h-4 border-2 border-[#00ff66] border-t-transparent rounded-full animate-spin"></div>
                                                    ) : (
                                                      <span className="text-[#00ff66] font-bold text-sm">✓</span>
                                                    )}
                                                    <div>
                                                      <span className="text-[10px] text-[#5b7a6b] block font-mono">SELECTION CONFIRMED</span>
                                                      <span className="text-white font-bold">{inlineConfirmations[agent.id].label}</span>
                                                    </div>
                                                  </div>
                                                  <span className="text-[11px] text-[#7da895] font-mono">
                                                    {inlineConfirmations[agent.id].status === 'processing'
                                                      ? 'Synthesizing script & running sandbox...'
                                                      : 'Execution Completed'}
                                                  </span>
                                                </div>
                                              )}

                                              {/* Interactive Confirmation Options if required and not yet chosen */}
                                              {inlineOutputs[agent.id].result?.requires_confirmation && !inlineConfirmations[agent.id] && (
                                                <div className="p-3 rounded bg-[#131f18] border border-[#00ff66]/50 space-y-2.5 box-glow-green">
                                                  <div className="text-[11px] font-bold text-[#ffb000] flex items-center gap-1.5">
                                                    <span>⚠️ Confirmation Required:</span>
                                                    <span className="text-white font-mono">{inlineOutputs[agent.id].result?.target_filename || 'Script'}</span>
                                                  </div>
                                                  <p className="text-[11px] text-[#a4c5b5]">
                                                    {inlineOutputs[agent.id].result?.question || 'Please select whether to save this script for future runs or execute one-time only:'}
                                                  </p>
                                                  <div className="flex flex-wrap items-center gap-2 pt-1">
                                                    {inlineOutputs[agent.id].result?.options?.map((opt: any) => (
                                                      <button
                                                        key={opt.value}
                                                        type="button"
                                                        disabled={inlineExecuting[agent.id]}
                                                        onClick={() => handleInlineConfirmOption(node.id, agent.id, agent.port, opt.value, opt.label)}
                                                        className={`px-3.5 py-1.5 rounded text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 active:scale-95 ${
                                                          opt.value === 'saved' || opt.value === 'save'
                                                            ? 'bg-[#00ff66] text-black hover:bg-[#1aff75] shadow-[0_0_10px_rgba(0,255,102,0.35)]'
                                                            : 'bg-[#1b2a20] text-[#a4c5b5] hover:text-white border border-[#273d2f]'
                                                        }`}
                                                      >
                                                        <span>{opt.label}</span>
                                                      </button>
                                                    )) || (
                                                      <>
                                                        <button
                                                          type="button"
                                                          disabled={inlineExecuting[agent.id]}
                                                          onClick={() => handleInlineConfirmOption(node.id, agent.id, agent.port, 'saved', '💾 Save to Script Assets Library')}
                                                          className="px-3.5 py-1.5 rounded text-xs font-bold bg-[#00ff66] text-black hover:bg-[#1aff75] shadow-[0_0_10px_rgba(0,255,102,0.35)] cursor-pointer active:scale-95"
                                                        >
                                                          💾 Save for Future Execution
                                                        </button>
                                                        <button
                                                          type="button"
                                                          disabled={inlineExecuting[agent.id]}
                                                          onClick={() => handleInlineConfirmOption(node.id, agent.id, agent.port, 'one_time', '⚡ One-Time Only')}
                                                          className="px-3.5 py-1.5 rounded text-xs font-bold bg-[#1b2a20] text-[#a4c5b5] hover:text-white border border-[#273d2f] cursor-pointer active:scale-95"
                                                        >
                                                          ⚡ One-Time Only
                                                        </button>
                                                      </>
                                                    )}
                                                  </div>
                                                </div>
                                              )}

                                              <pre className="text-[11px] text-[#a4c5b5] font-mono whitespace-pre-wrap max-h-36 overflow-y-auto">
                                                {typeof inlineOutputs[agent.id].result?.response === 'string'
                                                  ? inlineOutputs[agent.id].result.response
                                                  : JSON.stringify(inlineOutputs[agent.id], null, 2)}
                                              </pre>
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                );
                              })
                            )}
                          </div>
                        </div>
                      </div>
                    )}
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
            <div className="flex flex-wrap items-center justify-between border-b border-[#16231c] pb-3 gap-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#00ff66] flex items-center gap-2">
                <span>💻 Autonomous Agent Command Console</span>
              </h3>
              <div className="flex items-center gap-1 p-0.5 rounded bg-[#080d0a] border border-[#1a2b21]">
                <button
                  type="button"
                  onClick={() => setBroadcastMode(false)}
                  className={`px-2.5 py-1 rounded text-[11px] font-mono transition-all cursor-pointer ${
                    !broadcastMode
                      ? 'bg-[#14281c] text-[#00ff66] font-bold border border-[#00ff66]/30 shadow-[0_0_8px_rgba(0,255,102,0.2)]'
                      : 'text-[#6b8c7c] hover:text-white'
                  }`}
                >
                  🎯 Single Target
                </button>
                <button
                  type="button"
                  onClick={() => setBroadcastMode(true)}
                  className={`px-2.5 py-1 rounded text-[11px] font-mono transition-all cursor-pointer ${
                    broadcastMode
                      ? 'bg-[#122b38] text-[#00e5ff] font-bold border border-[#00e5ff]/40 shadow-[0_0_8px_rgba(0,229,255,0.25)]'
                      : 'text-[#6b8c7c] hover:text-white'
                  }`}
                >
                  📡 Fleet Broadcast (All Nodes)
                </button>
              </div>
            </div>

            <form onSubmit={handleSendCommand} className="space-y-3">
              {broadcastMode ? (
                <div className="p-3.5 rounded bg-[#09151e] border border-[#00e5ff]/40 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2.5">
                    <div className="flex items-center gap-2">
                      <span className="text-base">📡</span>
                      <div>
                        <span className="text-[#00e5ff] font-bold block font-mono text-xs">FLEET-WIDE BROADCAST ACTIVE</span>
                        <span className="text-[#7da8b5] text-[11px]">
                          {broadcastIncludeSubagents
                            ? `Swarm Mode: Concurrently dispatching to ALL primary sentinels AND co-located subagents.`
                            : `Sentinel Mode: Concurrently dispatching to primary sentinels on all ${nodes.length} registered nodes.`}
                        </span>
                      </div>
                    </div>
                    <label className="flex items-center gap-2 cursor-pointer bg-[#0c1c28] px-2.5 py-1 rounded border border-[#00e5ff]/30 hover:border-[#00e5ff] transition-all select-none">
                      <input
                        type="checkbox"
                        checked={broadcastIncludeSubagents}
                        onChange={(e) => setBroadcastIncludeSubagents(e.target.checked)}
                        className="accent-[#00e5ff] w-3.5 h-3.5 cursor-pointer"
                      />
                      <span className="text-[11px] font-mono text-white font-bold">
                        Include Subagents / Workers
                      </span>
                    </label>
                  </div>
                </div>
              ) : (
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
              )}

              <div>
                <label className="text-[10px] text-[#5b7a6b] block mb-1">PROMPT / INSTRUCTION</label>
                <textarea
                  value={commandPrompt}
                  onChange={(e) => setCommandPrompt(e.target.value)}
                  placeholder={broadcastMode ? "Enter fleet broadcast prompt (e.g. Inspect memory and report disk space)..." : "Enter autonomous prompt, e.g.: Analyze hardware memory overhead and summarize system readiness."}
                  rows={3}
                  className="w-full bg-[#080d0a] border border-[#1e2e24] rounded p-2.5 text-xs text-[#00ff66] focus:outline-none focus:border-[#00ff66] font-mono resize-none"
                />
              </div>

              <div className="flex justify-between items-center">
                <span className="text-[10px] text-[#5b7a6b]">
                  Routing to: <strong className="text-white">
                    {broadcastMode
                      ? `All Fleet Nodes (${nodes.length} targets)`
                      : targetAgent ? `${targetAgent.id} (Port ${targetAgent.port})` : 'None'}
                  </strong>
                </span>
                <button
                  type="submit"
                  disabled={commandExecuting || !commandPrompt.trim()}
                  className={`px-4 py-1.5 rounded text-black text-xs font-bold disabled:opacity-50 transition-all cursor-pointer ${
                    broadcastMode
                      ? 'bg-[#00e5ff] hover:bg-[#33ebff] shadow-[0_0_12px_rgba(0,229,255,0.4)]'
                      : 'bg-[#00ff66] hover:bg-[#1aff75] shadow-[0_0_10px_rgba(0,255,102,0.3)]'
                  }`}
                >
                  {commandExecuting
                    ? (broadcastMode ? 'BROADCASTING...' : 'DISPATCHING...')
                    : (broadcastMode ? 'BROADCAST TO FLEET 📡' : 'DISPATCH COMMAND ↵')}
                </button>
              </div>
            </form>

            {/* Execution Result Box */}
            {commandOutput && (
              <div className="mt-3 p-3 rounded bg-[#070b09] border border-[#1c2c22] space-y-2 text-xs">
                <div className="text-[10px] text-[#5b7a6b] flex justify-between border-b border-[#141f19] pb-1">
                  <span>DISPATCH RESULT</span>
                  <span className={commandOutput.status === 'error' ? 'text-[#ff3344]' : 'text-[#00ff66]'}>
                    {commandOutput.result?.status?.toUpperCase() || commandOutput.status?.toUpperCase()}
                  </span>
                </div>

                {/* Prominent Selection Notice when option clicked */}
                {selectedConfirmation && (
                  <div className={`p-3.5 rounded border text-xs transition-all flex items-center justify-between gap-3 ${
                    selectedConfirmation.status === 'processing'
                      ? 'bg-[#0f2418] border-[#00ff66] shadow-[0_0_14px_rgba(0,255,102,0.3)] box-glow-green'
                      : 'bg-[#0b1610] border-[#00ff66]/40 text-[#c4d6cc]'
                  }`}>
                    <div className="flex items-center gap-3">
                      {selectedConfirmation.status === 'processing' ? (
                        <div className="w-4 h-4 border-2 border-[#00ff66] border-t-transparent rounded-full animate-spin"></div>
                      ) : (
                        <span className="text-[#00ff66] font-bold text-base">✓</span>
                      )}
                      <div>
                        <span className="text-[10px] text-[#5b7a6b] block font-mono">SELECTION CONFIRMED</span>
                        <span className="text-white font-bold tracking-wide text-xs">{selectedConfirmation.label}</span>
                      </div>
                    </div>
                    <span className="text-[11px] text-[#7da895] font-mono">
                      {selectedConfirmation.status === 'processing'
                        ? 'Synthesizing script & running sandbox...'
                        : 'Execution Completed'}
                    </span>
                  </div>
                )}

                {/* If agent requires confirmation and user has NOT yet selected an option, render interactive buttons */}
                {commandOutput.result?.requires_confirmation && !selectedConfirmation && (
                  <div className="p-3.5 rounded bg-[#131f18] border border-[#00ff66]/50 space-y-2.5 my-2 box-glow-green">
                    <div className="text-xs font-bold text-[#ffb000] flex items-center gap-1.5">
                      <span>⚠️ Confirmation Required:</span>
                      <span className="text-white font-mono">{commandOutput.result?.target_filename || 'Script'}</span>
                    </div>
                    <p className="text-[11px] text-[#a4c5b5]">
                      {commandOutput.result?.question || 'Please choose whether to save this script to the asset library or execute one-time only in sandbox.'}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      {commandOutput.result?.options?.map((opt: any) => (
                        <button
                          key={opt.value}
                          type="button"
                          disabled={commandExecuting}
                          onClick={() => handleConfirmOption(opt.value, opt.label)}
                          className={`px-3.5 py-1.5 rounded text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 active:scale-95 ${
                            opt.value === 'saved' || opt.value === 'save'
                              ? 'bg-[#00ff66] text-black hover:bg-[#1aff75] shadow-[0_0_12px_rgba(0,255,102,0.35)]'
                              : 'bg-[#1a2b21] text-[#a4c5b5] hover:text-white border border-[#273d2f]'
                          }`}
                        >
                          <span>{opt.label}</span>
                        </button>
                      )) || (
                        <>
                          <button
                            type="button"
                            disabled={commandExecuting}
                            onClick={() => handleConfirmOption('saved', '💾 Save to Script Assets Library')}
                            className="px-3.5 py-1.5 rounded text-xs font-bold bg-[#00ff66] text-black hover:bg-[#1aff75] shadow-[0_0_12px_rgba(0,255,102,0.35)] cursor-pointer active:scale-95"
                          >
                            💾 Save for Future Execution
                          </button>
                          <button
                            type="button"
                            disabled={commandExecuting}
                            onClick={() => handleConfirmOption('one_time', '⚡ One-Time Only')}
                            className="px-3.5 py-1.5 rounded text-xs font-bold bg-[#1a2b21] text-[#a4c5b5] hover:text-white border border-[#273d2f] cursor-pointer active:scale-95"
                          >
                            ⚡ One-Time Only
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                )}

                {commandOutput.broadcast ? (
                  <div className="space-y-2.5 pt-1">
                    <div className="flex items-center justify-between text-[11px] text-[#5b7a6b] border-b border-[#141f19] pb-1.5 font-mono">
                      <span>FLEET CONCURRENT EXECUTION SUMMARY</span>
                      <span className="text-[#00e5ff] font-bold">
                        {commandOutput.result?.total_nodes || 0} Target Nodes • {commandOutput.result?.duration_ms?.toFixed(0) || 0}ms Latency
                      </span>
                    </div>
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {(commandOutput.result?.results || commandOutput.result?.broadcast_results || []).map((nodeRes: any) => (
                        <div key={nodeRes.nodeId} className="p-3 rounded bg-[#090e0b] border border-[#18261e] space-y-1.5">
                          <div className="flex items-center justify-between text-xs flex-wrap gap-2">
                            <span className="font-bold text-white font-mono flex items-center gap-1.5 flex-wrap">
                              <span className={nodeRes.status === 'success' ? 'text-[#00ff66]' : 'text-[#ff3344]'}>●</span>
                              <span>{nodeRes.nodeId}</span>
                              {nodeRes.agentId && (
                                <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                                  nodeRes.isPrimary
                                    ? 'bg-[#183523] text-[#00ff66] border border-[#00ff66]/40'
                                    : 'bg-[#1b2533] text-[#70a5ff] border border-[#70a5ff]/30'
                                }`}>
                                  {nodeRes.agentId} ({nodeRes.isPrimary ? 'PRIMARY' : 'WORKER'})
                                </span>
                              )}
                            </span>
                            <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold ${
                              nodeRes.status === 'success'
                                ? 'bg-[#102419] text-[#00ff66] border border-[#00ff66]/40'
                                : 'bg-[#241014] text-[#ff3344] border border-[#ff3344]/40'
                            }`}>
                              {nodeRes.status?.toUpperCase() || 'SUCCESS'}
                            </span>
                          </div>
                          <div className="text-[11px] text-[#a4c5b5] font-mono whitespace-pre-wrap pl-3 border-l-2 border-[#1e3325]">
                            {nodeRes.data?.response || nodeRes.message || JSON.stringify(nodeRes, null, 2)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <pre className="text-[11px] text-[#a4c5b5] whitespace-pre-wrap font-mono pt-1 max-h-48 overflow-y-auto">
                    {typeof commandOutput.result?.response === 'string'
                      ? commandOutput.result.response
                      : JSON.stringify(commandOutput, null, 2)}
                  </pre>
                )}
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

      {/* MODAL: ENROLL / DEPLOY NODE (AUTOMATED C2 PUSH & MANUAL AIR-GAPPED) */}
      {enrollModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0b120e] border border-[#00ff66]/40 rounded-xl max-w-2xl w-full p-6 space-y-5 shadow-[0_0_35px_rgba(0,255,102,0.15)]">
            <div className="flex items-center justify-between border-b border-[#18261e] pb-3">
              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <span className="text-[#00ff66]">⚡</span> Deploy New Edge Agent Container
                </h3>
                <span className="text-[11px] text-[#5b7a6b] font-mono">
                  Automated remote push to blank Docker hosts or air-gapped manual installation
                </span>
              </div>
              <button
                onClick={() => setEnrollModalOpen(false)}
                className="text-[#5b7a6b] hover:text-white text-lg font-bold px-2 cursor-pointer"
              >
                ×
              </button>
            </div>

            {/* TAB SELECTOR */}
            <div className="flex border-b border-[#18261e] text-xs font-mono">
              <button
                type="button"
                onClick={() => setEnrollTab('automated')}
                className={`px-4 py-2.5 border-b-2 font-bold transition-all cursor-pointer ${
                  enrollTab === 'automated'
                    ? 'border-[#00ff66] text-[#00ff66] bg-[#00ff66]/5'
                    : 'border-transparent text-[#6e8a7d] hover:text-[#c4d6cc]'
                }`}
              >
                1. Automated C2 Push (Phone Home)
              </button>
              <button
                type="button"
                onClick={() => setEnrollTab('manual')}
                className={`px-4 py-2.5 border-b-2 font-bold transition-all cursor-pointer ${
                  enrollTab === 'manual'
                    ? 'border-[#ffb000] text-[#ffb000] bg-[#ffb000]/5'
                    : 'border-transparent text-[#6e8a7d] hover:text-[#c4d6cc]'
                }`}
              >
                2. Air-Gapped / Offline USB
              </button>
              <button
                type="button"
                onClick={() => setEnrollTab('direct')}
                className={`px-4 py-2.5 border-b-2 font-bold transition-all cursor-pointer ${
                  enrollTab === 'direct'
                    ? 'border-[#00e5ff] text-[#00e5ff] bg-[#00e5ff]/5'
                    : 'border-transparent text-[#6e8a7d] hover:text-[#c4d6cc]'
                }`}
              >
                3. Direct Network Endpoint
              </button>
            </div>

            {/* TAB CONTENT 1: AUTOMATED C2 PUSH */}
            {enrollTab === 'automated' && (
              <div className="space-y-4 text-xs">
                <div className="p-3.5 rounded-lg bg-[#070d0a] border border-[#18261e] space-y-2">
                  <p className="text-[#a4c2b3] leading-relaxed">
                    Deploy onto any blank Linux, NVIDIA Jetson, or WSL2 machine with an active Docker daemon.
                    Run the one-line command below on the target host. It launches a minimal (<span className="text-[#00ff66] font-bold">&lt;30 MB</span>)
                    Alpine bootstrap container that profiles the hardware, securely phones home via outbound HTTPS, and registers for operator approval.
                  </p>
                </div>

                {!generatedToken ? (
                  <div className="text-center py-4 space-y-3">
                    <button
                      type="button"
                      disabled={tokenLoading}
                      onClick={handleGenerateEnrollmentToken}
                      className="px-6 py-2.5 rounded-lg bg-[#00ff66] text-[#050a07] font-bold text-xs hover:bg-[#1aff75] transition-all shadow-[0_0_15px_rgba(0,255,102,0.3)] cursor-pointer disabled:opacity-50"
                    >
                      {tokenLoading ? 'Generating Token...' : 'Generate Single-Use Enrollment Token (60 min)'}
                    </button>
                    <span className="text-[10px] text-[#5b7a6b] block">
                      Tokens are single-use and automatically expire after 60 minutes.
                    </span>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-[#00ff66] font-mono font-bold">
                        ACTIVE TOKEN: {generatedToken} (Expires in 60m)
                      </span>
                      <button
                        type="button"
                        onClick={handleGenerateEnrollmentToken}
                        className="text-[10px] text-[#7a998b] hover:text-[#00ff66] underline cursor-pointer"
                      >
                        Generate New Token ↻
                      </button>
                    </div>

                    {/* Shell Environment Tabs */}
                    <div className="flex flex-wrap items-center gap-1.5 border-b border-[#1b3323] pb-2 text-[10px] font-mono">
                      <span className="text-[#5b7a6b] uppercase mr-1">Shell / OS:</span>
                      <button
                        type="button"
                        onClick={() => setShellFormat('powershell')}
                        className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
                          shellFormat === 'powershell' ? 'bg-[#00ff66] text-black font-bold' : 'bg-[#0d1712] text-[#8aa89b] hover:text-white'
                        }`}
                      >
                        PowerShell (Windows)
                      </button>
                      <button
                        type="button"
                        onClick={() => setShellFormat('bash')}
                        className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
                          shellFormat === 'bash' ? 'bg-[#00ff66] text-black font-bold' : 'bg-[#0d1712] text-[#8aa89b] hover:text-white'
                        }`}
                      >
                        Bash (Linux/Jetson)
                      </button>
                      <button
                        type="button"
                        onClick={() => setShellFormat('prompt_ps')}
                        className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
                          shellFormat === 'prompt_ps' ? 'bg-[#00e5ff] text-black font-bold' : 'bg-[#0d1712] text-[#8aa89b] hover:text-white'
                        }`}
                        title="PowerShell command that prompts the operator to enter their token"
                      >
                        Interactive PS (Prompts Token)
                      </button>
                      <button
                        type="button"
                        onClick={() => setShellFormat('prompt_bash')}
                        className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
                          shellFormat === 'prompt_bash' ? 'bg-[#00e5ff] text-black font-bold' : 'bg-[#0d1712] text-[#8aa89b] hover:text-white'
                        }`}
                        title="Bash command that prompts the operator to enter their token"
                      >
                        Interactive Bash (Prompts Token)
                      </button>
                    </div>

                    {/* Command Output Block */}
                    {(() => {
                      const activeCmd =
                        shellFormat === 'powershell' ? (generatedPsCommand || generatedCommand) :
                        shellFormat === 'bash' ? (generatedBashCommand || generatedCommand) :
                        shellFormat === 'prompt_ps' ? (generatedPromptPsCommand || generatedCommand) :
                        shellFormat === 'prompt_bash' ? (generatedPromptBashCommand || generatedCommand) :
                        generatedCommand;

                      return (
                        <div className="relative">
                          <pre className="p-3.5 rounded bg-[#060a08] border border-[#1b3323] text-[#00ff66] font-mono text-[11px] overflow-x-auto whitespace-pre-wrap break-all select-all leading-relaxed">
                            {activeCmd}
                          </pre>
                          <button
                            type="button"
                            onClick={() => {
                              if (activeCmd) {
                                navigator.clipboard.writeText(activeCmd);
                                setCopiedCommand(true);
                                setTimeout(() => setCopiedCommand(false), 2500);
                              }
                            }}
                            className="absolute top-2 right-2 px-3 py-1 rounded bg-[#102419] hover:bg-[#183625] border border-[#00ff66]/40 text-[#00ff66] text-[10px] font-bold transition-all cursor-pointer"
                          >
                            {copiedCommand ? '✓ COPIED!' : '📋 Copy Command'}
                          </button>
                        </div>
                      );
                    })()}

                    <div className="p-3 rounded bg-[#09120d] border border-[#182b20] space-y-1.5 text-[11px] text-[#8aa89b]">
                      <div className="font-bold text-white">Next Steps for Field Engineer:</div>
                      <div>1. Paste and run the command in the target host terminal.</div>
                      <div>2. The node will phone home and appear in the <span className="text-[#ffb000] font-bold">Pending Nodes</span> queue above.</div>
                      <div>3. Review hardware specifications, select the desired LLM model, and click <span className="text-[#00ff66] font-bold">Approve &amp; Stream Deploy</span>.</div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB CONTENT 2: AIR-GAPPED OFFLINE */}
            {enrollTab === 'manual' && (
              <div className="space-y-4 text-xs">
                <div className="p-3.5 rounded-lg bg-[#070d0a] border border-[#18261e] space-y-2">
                  <p className="text-[#a4c2b3] leading-relaxed">
                    For secure air-gapped environments without LAN/WAN access to the C2 server, use the self-contained USB deployment bundle.
                  </p>
                </div>

                <div className="space-y-2">
                  <div className="p-3 rounded bg-[#09120d] border border-[#182b20] space-y-1.5 text-[11px] text-[#8aa89b]">
                    <div className="font-bold text-white">1. Package Bundle on Connected Workstation:</div>
                    <pre className="p-2 rounded bg-[#060a08] border border-[#16291d] text-[#ffb000] font-mono text-[10px] overflow-x-auto">
                      ./scripts/package_offline_node.sh --full
                    </pre>
                    <span className="text-[10px] text-[#5b7a6b]">Creates `dist/krokbot-offline-bundle.tar.gz` containing installer, image, and models.</span>
                  </div>

                  <div className="p-3 rounded bg-[#09120d] border border-[#182b20] space-y-1.5 text-[11px] text-[#8aa89b]">
                    <div className="font-bold text-white">2. Run on Air-Gapped Target:</div>
                    <div className="font-mono text-[10px] text-[#c4d6cc] space-y-1">
                      <div>Linux / Jetson: <span className="text-[#00ff66]">./install.sh</span></div>
                      <div>Windows (PowerShell): <span className="text-[#00ff66]">.\install.ps1</span></div>
                    </div>
                  </div>

                  <div className="p-3 rounded bg-[#09120d] border border-[#182b20] space-y-1 text-[11px] text-[#8aa89b]">
                    <div className="font-bold text-white">3. Verify Deployment:</div>
                    <div>Target dashboard is instantly available at <span className="text-[#00e5ff] font-mono">http://localhost:5150</span></div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB CONTENT 3: DIRECT NETWORK REGISTRATION */}
            {enrollTab === 'direct' && (
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
                    onClick={() => setEnrollModalOpen(false)}
                    className="px-4 py-2 rounded bg-[#141e18] text-[#8aa89b] hover:bg-[#1a2720]"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={registering}
                    className="px-5 py-2 rounded bg-[#00ff66] text-black font-bold hover:bg-[#1aff75] disabled:opacity-50"
                  >
                    {registering ? 'Registering...' : 'Register Existing Node'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* MODAL: LIVE PROCESS INSPECTOR (SYSOPS) */}
      {processModalNode && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0c1310] border border-[#00e5ff]/40 rounded-xl max-w-2xl w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#18261e] pb-3">
              <div className="flex items-center gap-2.5">
                <span className="text-base">⚙️</span>
                <div>
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                    Edge Process Inspector — {processModalNode.name}
                  </h3>
                  <span className="text-[10px] text-[#5b7a6b] font-mono">
                    Host: {processModalNode.ip_address} • Node ID: {processModalNode.id}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => openProcessModal(processModalNode)}
                  disabled={loadingProcesses}
                  className="px-2.5 py-1 rounded bg-[#101a14] hover:bg-[#182920] border border-[#1e3025] text-[#7da895] hover:text-[#00ff66] text-xs font-mono transition-colors"
                >
                  {loadingProcesses ? 'Refreshing...' : 'Refresh ↻'}
                </button>
                <button
                  type="button"
                  onClick={() => setProcessModalNode(null)}
                  className="text-[#5b7a6b] hover:text-white text-lg font-bold px-1"
                >
                  ×
                </button>
              </div>
            </div>

            <div className="space-y-3">
              <div className="text-xs text-[#8aa89b] flex items-center justify-between">
                <span>Active Container &amp; Node Processes ({processList.length})</span>
                <span className="text-[10px] text-[#5b7a6b]">Critical system daemons are protected</span>
              </div>

              <div className="max-h-80 overflow-y-auto border border-[#16231c] rounded-lg bg-[#080d0a]">
                {loadingProcesses ? (
                  <div className="p-8 text-center text-xs text-[#5b7a6b] space-y-2">
                    <div className="inline-block w-5 h-5 border-2 border-[#00e5ff] border-t-transparent rounded-full animate-spin mb-1"></div>
                    <div>SCANNING NODE PROCESS TABLE...</div>
                  </div>
                ) : processList.length === 0 ? (
                  <div className="p-8 text-center text-xs text-[#5b7a6b]">
                    No processes found or node unreachable.
                  </div>
                ) : (
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-[#16231c] bg-[#0d1410] text-[#5b7a6b] text-[10px] uppercase font-mono">
                        <th className="p-2.5">PID</th>
                        <th className="p-2.5">Process Name</th>
                        <th className="p-2.5">Memory (RSS)</th>
                        <th className="p-2.5">CPU %</th>
                        <th className="p-2.5 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#131d17] font-mono text-[11px]">
                      {processList.map((p) => {
                        const isProtected = p.is_protected === true;
                        return (
                          <tr key={p.pid} className="hover:bg-[#101813] transition-colors">
                            <td className="p-2.5 text-[#00ff66]">{p.pid}</td>
                            <td className="p-2.5 text-white font-sans font-medium flex items-center gap-1.5">
                              <span>{p.name}</span>
                              {isProtected && (
                                <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-[#1f2d24] text-[#70d49b] border border-[#2e4738]">
                                  PROTECTED
                                </span>
                              )}
                            </td>
                            <td className="p-2.5 text-[#00e5ff]">{p.memory_rss_mb?.toFixed(1) || '0.0'} MB</td>
                            <td className="p-2.5 text-[#ffb000]">{p.cpu_percent?.toFixed(1) || '0.0'}%</td>
                            <td className="p-2.5 text-right">
                              {isProtected ? (
                                <span className="text-[10px] text-[#4a6356] italic">System Core</span>
                              ) : (
                                <button
                                  type="button"
                                  disabled={killingPid === p.pid}
                                  onClick={() => handleKillProcess(processModalNode.id, p.pid)}
                                  className="px-2 py-0.5 rounded bg-[#241315] hover:bg-[#3d181c] border border-[#ff3344]/40 text-[#ff5566] text-[10px] font-bold transition-colors cursor-pointer disabled:opacity-50"
                                >
                                  {killingPid === p.pid ? 'Killing...' : 'Terminate'}
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            <div className="pt-2 flex justify-between items-center border-t border-[#16231c]">
              <span className="text-[11px] text-[#5b7a6b]">
                PID 1 and parent container supervisor processes cannot be killed.
              </span>
              <button
                type="button"
                onClick={() => setProcessModalNode(null)}
                className="px-4 py-1.5 rounded bg-[#141e18] text-[#8aa89b] hover:bg-[#1a2720] text-xs font-semibold cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: OPERATIONAL SYSTEM CLEANUP RESULT (IN-APP) */}
      {cleanupModalData && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0c1310] border border-[#00ff66]/40 rounded-xl max-w-md w-full p-6 space-y-4 shadow-[0_0_30px_rgba(0,255,102,0.15)]">
            <div className="flex items-center justify-between border-b border-[#18261e] pb-3">
              <div className="flex items-center gap-2.5">
                <span className="text-xl">🧹</span>
                <div>
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                    Node Memory &amp; Storage Cleanup Complete
                  </h3>
                  <span className="text-[10px] text-[#5b7a6b] font-mono">
                    Target: {cleanupModalData.nodeName} • {cleanupModalData.timestamp}
                  </span>
                </div>
              </div>
              <button
                onClick={() => setCleanupModalData(null)}
                className="text-[#5b7a6b] hover:text-white text-lg font-bold px-1 cursor-pointer"
              >
                ×
              </button>
            </div>

            <div className="space-y-3 py-1 text-xs">
              <div className="grid grid-cols-2 gap-2.5 font-mono">
                <div className="p-3 rounded-lg bg-[#080d0a] border border-[#16231c] space-y-1">
                  <span className="text-[10px] text-[#5b7a6b] block">MEMORY RECOVERED</span>
                  <span className="text-base font-bold text-[#00ff66]">
                    +{cleanupModalData.memoryRecoveredMb.toFixed(2)} MB
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-[#080d0a] border border-[#16231c] space-y-1">
                  <span className="text-[10px] text-[#5b7a6b] block">TEMPORARY FILES PRUNED</span>
                  <span className="text-base font-bold text-[#00e5ff]">
                    {cleanupModalData.tempFilesPruned} files
                  </span>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-[#0d1712] border border-[#1b3323] space-y-1.5 font-mono text-[11px]">
                <div className="flex items-center justify-between">
                  <span className="text-[#8aa89b]">Glibc Kernel Heap Trim (`malloc_trim`):</span>
                  <span className="text-[#00ff66] font-bold">
                    {cleanupModalData.mallocTrimmed ? 'ACTIVE / RELEASED' : 'BYPASS'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#8aa89b]">Python Garbage Collection:</span>
                  <span className="text-[#00ff66] font-bold">COMPLETED</span>
                </div>
              </div>

              <p className="text-[11px] text-[#6b8c7c]">
                Fragmented process heap and temporary scratch artifacts have been released back to the operating system kernel.
              </p>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => setCleanupModalData(null)}
                className="px-5 py-2 rounded bg-[#00ff66] text-black font-bold text-xs hover:bg-[#1aff75] transition-all cursor-pointer shadow-[0_0_10px_rgba(0,255,102,0.3)]"
              >
                Acknowledge &amp; Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: RENAME EDGE NODE OR AGENT CONTAINER */}
      {renameModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
          <div className="bg-[#0b120e] border border-[#1b2b21] rounded-xl p-5 sm:p-6 w-full max-w-md shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#15231b] pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <span>✏️</span>
                <span>Rename {renameType === 'node' ? 'Edge Master Node' : 'Agent Container'}</span>
              </h3>
              <button
                type="button"
                onClick={() => setRenameModalOpen(false)}
                className="text-[#5b7a6b] hover:text-white text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-[#7da895] font-mono block uppercase">
                {renameType === 'node' ? 'Node Name' : 'Agent Name'} ({renameTargetId})
              </label>
              <input
                type="text"
                value={renameNameInput}
                onChange={(e) => setRenameNameInput(e.target.value)}
                placeholder="Enter new name..."
                className="w-full bg-[#101b15] border border-[#1d3126] rounded-lg px-3.5 py-2 text-sm text-white font-mono focus:outline-none focus:border-[#00ff66]"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleRenameSubmit();
                }}
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setRenameModalOpen(false)}
                className="px-4 py-2 rounded-lg bg-[#141f19] hover:bg-[#1d2c24] text-xs font-bold text-[#8aa89b] transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={renaming || !renameNameInput.trim()}
                onClick={handleRenameSubmit}
                className="px-4 py-2 rounded-lg bg-[#00ff66] hover:bg-[#00cc52] text-xs font-bold text-[#06120a] transition-all cursor-pointer disabled:opacity-50 flex items-center gap-2"
              >
                {renaming ? <span>Saving...</span> : <span>Save Name</span>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: INSPECT NODE PROCESS TABLE */}
      {processModalNode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
          <div className="bg-[#0b120e] border border-[#1b2b21] rounded-xl p-5 sm:p-6 w-full max-w-2xl shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#15231b] pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <span>⚙️</span>
                <span>Process Inspector: {processModalNode.name}</span>
              </h3>
              <button
                type="button"
                onClick={() => setProcessModalNode(null)}
                className="text-[#5b7a6b] hover:text-white text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <div className="text-xs text-[#8aa89b] flex items-center justify-between">
                <span>Active Container &amp; Node Processes ({processList.length})</span>
                <span className="text-[10px] text-[#5b7a6b]">Critical system daemons are protected</span>
              </div>

              <div className="max-h-80 overflow-y-auto border border-[#16231c] rounded-lg bg-[#080d0a]">
                {loadingProcesses ? (
                  <div className="p-8 text-center text-xs text-[#5b7a6b] space-y-2">
                    <div className="inline-block w-5 h-5 border-2 border-[#00e5ff] border-t-transparent rounded-full animate-spin mb-1"></div>
                    <div>SCANNING NODE PROCESS TABLE...</div>
                  </div>
                ) : processList.length === 0 ? (
                  <div className="p-8 text-center text-xs text-[#5b7a6b]">
                    No processes found or node unreachable.
                  </div>
                ) : (
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-[#16231c] bg-[#0d1410] text-[#5b7a6b] text-[10px] uppercase font-mono">
                        <th className="p-2.5">PID</th>
                        <th className="p-2.5">Process Name</th>
                        <th className="p-2.5">Memory (RSS)</th>
                        <th className="p-2.5">CPU %</th>
                        <th className="p-2.5 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#131d17] font-mono text-[11px]">
                      {processList.map((p) => {
                        const isProtected = p.is_protected === true;
                        return (
                          <tr key={p.pid} className="hover:bg-[#101813] transition-colors">
                            <td className="p-2.5 text-[#00ff66]">{p.pid}</td>
                            <td className="p-2.5 text-white font-sans font-medium flex items-center gap-1.5">
                              <span>{p.name}</span>
                              {isProtected && (
                                <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-[#1f2d24] text-[#70d49b] border border-[#2e4738]">
                                  PROTECTED
                                </span>
                              )}
                            </td>
                            <td className="p-2.5 text-[#00e5ff]">{p.memory_rss_mb?.toFixed(1) || '0.0'} MB</td>
                            <td className="p-2.5 text-[#ffb000]">{p.cpu_percent?.toFixed(1) || '0.0'}%</td>
                            <td className="p-2.5 text-right">
                              {isProtected ? (
                                <span className="text-[10px] text-[#4a6356] italic">System Core</span>
                              ) : (
                                <button
                                  type="button"
                                  disabled={killingPid === p.pid}
                                  onClick={() => handleKillProcess(processModalNode.id, p.pid)}
                                  className="px-2 py-0.5 rounded bg-[#241315] hover:bg-[#3d181c] border border-[#ff3344]/40 text-[#ff5566] text-[10px] font-bold transition-colors cursor-pointer disabled:opacity-50"
                                >
                                  {killingPid === p.pid ? 'Killing...' : 'Terminate'}
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            <div className="pt-2 flex justify-between items-center border-t border-[#16231c]">
              <span className="text-[11px] text-[#5b7a6b]">
                PID 1 and parent container supervisor processes cannot be killed.
              </span>
              <button
                type="button"
                onClick={() => setProcessModalNode(null)}
                className="px-4 py-1.5 rounded bg-[#141e18] text-[#8aa89b] hover:bg-[#1a2720] text-xs font-semibold cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: CUSTOM AGENT & NODE DELETION CONFIRMATION & PROGRESS */}
      {deleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fadeIn font-mono">
          <div className="bg-[#0b120e] border border-[#ff3344]/40 rounded-xl p-5 sm:p-6 w-full max-w-lg shadow-[0_0_30px_rgba(255,51,68,0.2)] space-y-4 font-mono">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-[#241315] pb-3">
              <h3 className="text-base font-bold text-[#ff5566] flex items-center gap-2">
                <span>⚠️</span>
                <span>Confirm {deleteType === 'node' ? 'Edge Node Removal' : 'Agent Container Deletion'}</span>
              </h3>
              {!deleting && (
                <button
                  type="button"
                  onClick={() => setDeleteModalOpen(false)}
                  className="text-[#5b7a6b] hover:text-white text-sm cursor-pointer"
                >
                  ✕
                </button>
              )}
            </div>

            {/* Target Metadata Header */}
            <div className="bg-[#181113] border border-[#381c1f] rounded-lg p-3 space-y-1">
              <div className="text-xs text-[#a37075] uppercase font-bold">Target {deleteType === 'node' ? 'Master Node' : 'Agent Instance'}</div>
              <div className="text-sm font-bold text-white flex items-center justify-between">
                <span>{deleteTargetName}</span>
                <span className="text-xs px-2 py-0.5 rounded bg-[#2c1719] text-[#ff8899] font-mono">{deleteTargetId}</span>
              </div>
            </div>

            {/* Error Banner */}
            {deleteError && (
              <div className="p-3 bg-[#331114] border border-[#ff3344] rounded-lg text-xs text-[#ff99a8] font-mono leading-relaxed">
                <span className="font-bold">Deletion Error:</span> {deleteError}
              </div>
            )}

            {/* Step-by-Step Progress Checklist */}
            <div className="space-y-2 py-1">
              <div className="text-xs font-bold text-[#7da895] uppercase">Execution Progress Checklist</div>
              <div className="space-y-2">
                {deleteSteps.map((st, idx) => (
                  <div key={idx} className="flex items-start gap-2.5 p-2.5 rounded bg-[#0f1a14] border border-[#18291f] text-xs">
                    <span className="mt-0.5">
                      {st.status === 'pending' && <span className="text-[#5b7a6b]">⏳</span>}
                      {st.status === 'running' && <span className="text-[#00ff66] animate-pulse">🔄</span>}
                      {st.status === 'success' && <span className="text-[#00ff66]">✅</span>}
                      {st.status === 'warning' && <span className="text-[#ffaa00]">⚠️</span>}
                      {st.status === 'error' && <span className="text-[#ff3344]">❌</span>}
                    </span>
                    <div className="flex-1 space-y-1">
                      <div className={`font-semibold ${st.status === 'running' ? 'text-[#00ff66]' : st.status === 'error' ? 'text-[#ff5566]' : 'text-[#d0e0d8]'}`}>
                        {st.description}
                      </div>
                      {st.instructions && (
                        <div className="mt-1.5 p-2.5 bg-[#1b120c] border border-[#ffaa00]/40 rounded-md text-[11px] text-[#ffdd88] space-y-1">
                          <div className="font-bold text-[#ffaa00] flex items-center justify-between gap-2">
                            <span>🛠️ Admin Manual Teardown Instruction:</span>
                            <button
                              type="button"
                              onClick={() => {
                                if (st.instructions) {
                                  const cmd = st.instructions.includes(': ') ? st.instructions.split(': ')[1] : st.instructions;
                                  navigator.clipboard.writeText(cmd);
                                  alert('Terminal command copied to clipboard!');
                                }
                              }}
                              className="px-2 py-0.5 rounded bg-[#332211] hover:bg-[#443311] text-[10px] text-[#ffcc00] font-bold cursor-pointer transition-colors"
                            >
                              📋 Copy Command
                            </button>
                          </div>
                          <code className="block p-1.5 bg-[#0d0906] rounded text-[#00ff66] font-mono break-all select-all">
                            {st.instructions}
                          </code>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end gap-3 pt-3 border-t border-[#18291f]">
              {!deleteComplete && !deleting && (
                <>
                  <button
                    type="button"
                    onClick={() => setDeleteModalOpen(false)}
                    className="px-4 py-2 rounded-lg bg-[#141f19] hover:bg-[#1d2c24] text-xs font-bold text-[#8aa89b] transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleExecuteDelete}
                    className="px-4 py-2 rounded-lg bg-[#ff3344] hover:bg-[#dd2233] text-xs font-bold text-white transition-all cursor-pointer shadow-[0_0_15px_rgba(255,51,68,0.4)] flex items-center gap-2"
                  >
                    <span>🗑️ Confirm &amp; Remove Permanently</span>
                  </button>
                </>
              )}

              {deleting && (
                <div className="text-xs text-[#00ff66] font-bold py-2 flex items-center gap-2 animate-pulse">
                  <span>🔄 Processing removal and cleaning host state...</span>
                </div>
              )}

              {deleteComplete && (
                <button
                  type="button"
                  onClick={() => setDeleteModalOpen(false)}
                  className="px-5 py-2 rounded-lg bg-[#00ff66] hover:bg-[#00cc52] text-xs font-bold text-[#06120a] transition-all cursor-pointer shadow-[0_0_12px_rgba(0,255,102,0.4)]"
                >
                  Close &amp; Complete
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
