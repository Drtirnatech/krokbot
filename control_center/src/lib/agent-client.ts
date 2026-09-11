/**
 * Client for interacting with remote KrokBot edge nodes and container instances.
 */

export interface RemoteNodeHealth {
  agentId: string;
  agentName: string;
  dashboardPort: number;
  cpuPercent: number;
  memoryUsedGb: number;
  memoryPercent: number;
  storageMb: number;
  activeModel: string;
  isOnline: boolean;
  agents: Array<{
    id: string;
    name: string;
    port: number;
    pid: number;
    status: string;
    is_primary: boolean;
  }>;
}

export const agentClient = {
  async fetchNodeHealth(endpointUrl: string): Promise<RemoteNodeHealth> {
    const cleanUrl = endpointUrl.replace(/\/+$/, '');
    try {
      // 1. Fetch agent info & identity
      const infoRes = await fetch(`${cleanUrl}/api/agent/info`, { signal: AbortSignal.timeout(3500) });
      const info = infoRes.ok ? await infoRes.json() : {};

      // 2. Fetch resource metrics
      const metricsRes = await fetch(`${cleanUrl}/api/metrics`, { signal: AbortSignal.timeout(3500) });
      const metrics = metricsRes.ok ? await metricsRes.json() : {};
      const c = metrics.container || {};

      // 3. Fetch active model
      let activeModel = 'Qwen3-4B-Q4_K_M.gguf';
      try {
        const modelsRes = await fetch(`${cleanUrl}/api/models`, { signal: AbortSignal.timeout(3500) });
        if (modelsRes.ok) {
          const modelsData = await modelsRes.json();
          activeModel = modelsData.active_model || activeModel;
        }
      } catch (err) {
        // ignore model fetch timeout
      }

      // 4. Fetch co-located agents
      let agentsList: any[] = [];
      try {
        const agentsRes = await fetch(`${cleanUrl}/api/agents`, { signal: AbortSignal.timeout(3500) });
        if (agentsRes.ok) {
          const agentsData = await agentsRes.json();
          agentsList = agentsData.agents || [];
        }
      } catch (err) {
        // ignore
      }

      return {
        agentId: info.id || 'krok-prime-01',
        agentName: info.name || 'KrokBot Prime Sentinel',
        dashboardPort: info.dashboard_port || 5150,
        cpuPercent: c.cpu_percent !== undefined ? c.cpu_percent : (metrics.cpu_percent || 0.0),
        memoryUsedGb: c.memory_used_gb || 0.0,
        memoryPercent: c.memory_percent || 0.0,
        storageMb: c.storage_service_mb || 0.0,
        activeModel,
        isOnline: true,
        agents: agentsList
      };
    } catch (err) {
      return {
        agentId: 'unknown',
        agentName: 'Unreachable Node',
        dashboardPort: 5150,
        cpuPercent: 0,
        memoryUsedGb: 0,
        memoryPercent: 0,
        storageMb: 0,
        activeModel: 'None',
        isOnline: false,
        agents: []
      };
    }
  },

  async deployAgent(endpointUrl: string, agentId: string, agentName: string) {
    const cleanUrl = endpointUrl.replace(/\/+$/, '');
    const res = await fetch(`${cleanUrl}/api/agents/deploy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: agentId, name: agentName })
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Failed to deploy agent: ${err}`);
    }
    return res.json();
  },

  async stopAgent(endpointUrl: string, agentId: string) {
    const cleanUrl = endpointUrl.replace(/\/+$/, '');
    const res = await fetch(`${cleanUrl}/api/agents/${encodeURIComponent(agentId)}/stop`, {
      method: 'POST'
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Failed to stop agent: ${err}`);
    }
    return res.json();
  },

  async removeAgent(endpointUrl: string, agentId: string) {
    const cleanUrl = endpointUrl.replace(/\/+$/, '');
    try {
      const res = await fetch(`${cleanUrl}/api/agents/${encodeURIComponent(agentId)}/remove`, {
        method: 'POST'
      });
      if (res.ok) return res.json();
    } catch {
      // ignore
    }
    const resDel = await fetch(`${cleanUrl}/api/agents/${encodeURIComponent(agentId)}`, {
      method: 'DELETE'
    });
    if (!resDel.ok) {
      const err = await resDel.text();
      throw new Error(`Failed to remove agent: ${err}`);
    }
    return resDel.json();
  },

  async switchModel(endpointUrl: string, filename: string) {
    const cleanUrl = endpointUrl.replace(/\/+$/, '');
    const res = await fetch(`${cleanUrl}/api/models/${encodeURIComponent(filename)}/activate`, {
      method: 'POST'
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Failed to switch model: ${err}`);
    }
    return res.json();
  },

  async sendPrompt(endpointUrl: string, prompt: string, agentPort?: number, agentId?: string, saveMode?: string) {
    const cleanUrl = endpointUrl.replace(/\/+$/, '');

    // 1. If agentId is specified and not primary, route through Gateway /api/agents/{agentId}/chat
    if (agentId && agentId !== 'krok-prime-01') {
      try {
        const bodyPayload: any = { prompt };
        if (saveMode) bodyPayload.save_mode = saveMode;

        const res = await fetch(`${cleanUrl}/api/agents/${encodeURIComponent(agentId)}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(bodyPayload),
          signal: AbortSignal.timeout(35000)
        });
        if (res.ok) {
          const data = await res.json();
          return {
            status: data.status || 'success',
            response: data.reply || data.response || data.raw_reply || '',
            thinking: data.thinking || '',
            metrics: data.metrics || {},
            requires_confirmation: data.requires_confirmation || false,
            question: data.question || null,
            options: data.options || null,
            target_filename: data.target_filename || null,
            original_prompt: prompt,
            exit_code: data.sandbox_output?.exit_code ?? (data.exit_code ?? 0)
          };
        }
      } catch {
        // Fall through to direct port routing
      }
    }

    // 2. Direct port or primary agent routing
    let targetUrl = cleanUrl;
    if (agentPort && agentPort !== 5150) {
      const parsed = new URL(targetUrl);
      parsed.port = String(agentPort);
      targetUrl = parsed.toString().replace(/\/+$/, '');
    }

    const bodyPayload: any = { prompt };
    if (saveMode) bodyPayload.save_mode = saveMode;

    const res = await fetch(`${targetUrl}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bodyPayload),
      signal: AbortSignal.timeout(35000)
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Prompt error: ${err}`);
    }
    const data = await res.json();
    return {
      status: data.status || 'success',
      response: data.reply || data.response || data.raw_reply || '',
      thinking: data.thinking || '',
      metrics: data.metrics || {},
      requires_confirmation: data.requires_confirmation || false,
      question: data.question || null,
      options: data.options || null,
      target_filename: data.target_filename || null,
      original_prompt: prompt,
      exit_code: data.sandbox_output?.exit_code ?? (data.exit_code ?? 0)
    };
  }
};
