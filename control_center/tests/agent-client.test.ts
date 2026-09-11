import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { agentClient } from '../src/lib/agent-client.ts';

describe('C2 Agent Remote Client (agentClient)', () => {
  let mockServer: http.Server;
  let serverPort: number;
  let serverUrl: string;
  let requestedUrls: string[] = [];
  let requestBodies: any[] = [];
  let mockResponses: Record<string, { status?: number; body: any }> = {};

  beforeEach(async () => {
    requestedUrls = [];
    requestBodies = [];
    mockResponses = {};

    mockServer = http.createServer((req, res) => {
      const url = req.url || '/';
      requestedUrls.push(url);

      let rawBody = '';
      req.on('data', chunk => { rawBody += chunk; });
      req.on('end', () => {
        if (rawBody) {
          try { requestBodies.push(JSON.parse(rawBody)); } catch { requestBodies.push(rawBody); }
        }

        const match = mockResponses[url];
        if (match) {
          res.writeHead(match.status || 200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(match.body));
        } else {
          // Default fallback mock
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'success' }));
        }
      });
    });

    await new Promise<void>((resolve) => {
      mockServer.listen(0, '127.0.0.1', () => {
        const addr = mockServer.address() as any;
        serverPort = addr.port;
        serverUrl = `http://127.0.0.1:${serverPort}`;
        resolve();
      });
    });
  });

  afterEach(async () => {
    await new Promise<void>((resolve) => {
      mockServer.close(() => resolve());
    });
  });

  describe('fetchNodeHealth()', () => {
    it('should aggregate agent info, metrics, models, and sub-agents from healthy node', async () => {
      mockResponses['/api/agent/info'] = {
        status: 200,
        body: { id: 'krok-prime-01', name: 'Primary Sentinel', dashboard_port: 5150 }
      };
      mockResponses['/api/metrics'] = {
        status: 200,
        body: {
          container: { cpu_percent: 4.8, memory_used_gb: 1.2, memory_percent: 15.0, storage_service_mb: 250.0 }
        }
      };
      mockResponses['/api/models'] = {
        status: 200,
        body: { active_model: 'DeepSeek-R1-Distill-7B.gguf' }
      };
      mockResponses['/api/agents'] = {
        status: 200,
        body: {
          agents: [
            { id: 'krok-prime-01', name: 'Primary Sentinel', port: 5150, pid: 101, status: 'running', is_primary: true },
            { id: 'krok-worker-02', name: 'Recon Worker', port: 5152, pid: 202, status: 'running', is_primary: false }
          ]
        }
      };

      const health = await agentClient.fetchNodeHealth(serverUrl);

      assert.equal(health.isOnline, true);
      assert.equal(health.agentId, 'krok-prime-01');
      assert.equal(health.agentName, 'Primary Sentinel');
      assert.equal(health.activeModel, 'DeepSeek-R1-Distill-7B.gguf');
      assert.equal(health.cpuPercent, 4.8);
      assert.equal(health.memoryUsedGb, 1.2);
      assert.equal(health.agents.length, 2);
      assert.equal(health.agents[1].id, 'krok-worker-02');
      assert.equal(health.agents[1].port, 5152);
    });

    it('should return offline payload without throwing when node is unreachable', async () => {
      // Point to an unused local port
      const offlineUrl = 'http://127.0.0.1:59999';
      const health = await agentClient.fetchNodeHealth(offlineUrl);

      assert.equal(health.isOnline, false);
      assert.equal(health.agentId, 'unknown');
      assert.equal(health.agentName, 'Unreachable Node');
      assert.equal(health.cpuPercent, 0);
      assert.deepEqual(health.agents, []);
    });
  });

  describe('deployAgent()', () => {
    it('should POST agent credentials to /api/agents/deploy', async () => {
      mockResponses['/api/agents/deploy'] = {
        status: 200,
        body: { id: 'krok-recon-02', name: 'Recon Unit', port: 5152, status: 'running' }
      };

      const result = await agentClient.deployAgent(serverUrl, 'krok-recon-02', 'Recon Unit');

      assert.equal(result.id, 'krok-recon-02');
      assert.equal(result.port, 5152);
      assert.ok(requestedUrls.includes('/api/agents/deploy'));
      assert.deepEqual(requestBodies[0], { id: 'krok-recon-02', name: 'Recon Unit' });
    });

    it('should throw error when deployment fails on node', async () => {
      mockResponses['/api/agents/deploy'] = {
        status: 400,
        body: { detail: 'Agent already running.' }
      };

      await assert.rejects(
        async () => {
          await agentClient.deployAgent(serverUrl, 'krok-recon-02', 'Recon Unit');
        },
        /Failed to deploy agent/
      );
    });
  });

  describe('stopAgent()', () => {
    it('should POST to /api/agents/{agentId}/stop with URL encoding', async () => {
      mockResponses['/api/agents/krok-worker%20special/stop'] = {
        status: 200,
        body: { status: 'success', message: 'Agent stopped.' }
      };

      const result = await agentClient.stopAgent(serverUrl, 'krok-worker special');
      assert.equal(result.status, 'success');
      assert.ok(requestedUrls.includes('/api/agents/krok-worker%20special/stop'));
    });

    it('should throw error when stopping protected or missing agent', async () => {
      mockResponses['/api/agents/krok-prime-01/stop'] = {
        status: 400,
        body: { detail: 'Cannot stop primary sentinel agent.' }
      };

      await assert.rejects(
        async () => {
          await agentClient.stopAgent(serverUrl, 'krok-prime-01');
        },
        /Failed to stop agent/
      );
    });
  });

  describe('switchModel()', () => {
    it('should POST to /api/models/{filename}/activate', async () => {
      mockResponses['/api/models/Qwen2.5-Coder-7B.gguf/activate'] = {
        status: 200,
        body: { status: 'success', active_model: 'Qwen2.5-Coder-7B.gguf' }
      };

      const result = await agentClient.switchModel(serverUrl, 'Qwen2.5-Coder-7B.gguf');
      assert.equal(result.active_model, 'Qwen2.5-Coder-7B.gguf');
    });
  });

  describe('sendPrompt() across primary and worker agents', () => {
    it('should route prompt to primary agent at default port', async () => {
      mockResponses['/api/chat'] = {
        status: 200,
        body: { reply: 'Primary agent ready.', thinking: 'Processing request', metrics: { latency_ms: 120 } }
      };

      const res = await agentClient.sendPrompt(serverUrl, 'System health check', 5150);

      assert.equal(res.status, 'success');
      assert.equal(res.response, 'Primary agent ready.');
      assert.equal(res.thinking, 'Processing request');
      assert.equal(res.metrics.latency_ms, 120);
      assert.deepEqual(requestBodies[0], { prompt: 'System health check' });
    });

    it('should rewrite port when routing prompt directly to sub-agent worker port', async () => {
      // We create a second mock server on the worker port to verify the port redirect
      let workerReceived = false;
      const workerServer = http.createServer((req, res) => {
        if (req.url === '/api/chat') {
          workerReceived = true;
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'success', reply: 'Worker agent response from sub-port.' }));
        }
      });

      const workerPort = await new Promise<number>((resolve) => {
        workerServer.listen(0, '127.0.0.1', () => {
          const a = workerServer.address() as any;
          resolve(a.port);
        });
      });

      try {
        const res = await agentClient.sendPrompt(serverUrl, 'Execute task in sandbox', workerPort);
        assert.equal(workerReceived, true, 'Subagent worker should have received the request on its dedicated port');
        assert.equal(res.response, 'Worker agent response from sub-port.');
      } finally {
        await new Promise<void>(r => workerServer.close(() => r()));
      }
    });

    it('should handle API errors when sending prompt', async () => {
      mockResponses['/api/chat'] = {
        status: 500,
        body: { error: 'Llama.cpp inference connection refused' }
      };

      await assert.rejects(
        async () => {
          await agentClient.sendPrompt(serverUrl, 'Ping');
        },
        /Prompt error/
      );
    });
  });
});
