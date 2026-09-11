import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

const BASE_URL = process.env.C2_TEST_URL || 'http://localhost:5200';

describe('C2 Fleet API Endpoints & Multi-Agent Operations', () => {
  const testWorkerId = `krok-test-worker-${Date.now()}`;
  let allocatedPort: number;

  describe('Fleet Nodes & Registration', () => {
    it('GET /api/fleet/nodes should return fleet nodes with live health and agents', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/nodes`);
      assert.equal(res.status, 200);

      const data = await res.json();
      assert.equal(data.status, 'success');
      assert.ok(Array.isArray(data.nodes), 'nodes should be an array');
      assert.ok(data.nodes.length > 0, 'should have at least one node');

      const primaryNode = data.nodes.find((n: any) => n.id === 'node-jetson-primary') || data.nodes[0];
      assert.ok(primaryNode, 'Primary node must exist in fleet');
      assert.ok(primaryNode.id, 'Node must have an id');
      assert.ok(primaryNode.name, 'Node must have a name');
      assert.ok(primaryNode.ip_address, 'Node must have an ip_address');
      assert.ok(Array.isArray(primaryNode.agents), 'Node must have an agents array');

      // Verify primary agent is present
      const primaryAgent = primaryNode.agents.find((a: any) => a.is_primary === 1 || a.is_primary === true);
      assert.ok(primaryAgent, 'Primary agent must exist on the node');
      assert.equal(primaryAgent.port, 5150);
    });

    it('POST /api/fleet/nodes should reject request if required fields are missing', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/nodes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: 'incomplete-node' }) // Missing name and ip_address
      });
      assert.equal(res.status, 400);
      const data = await res.json();
      assert.equal(data.status, 'error');
      assert.match(data.message, /Missing required node parameters/);
    });

    it('POST /api/fleet/nodes should successfully register and then delete a new edge node', async () => {
      const edgeNodeId = `node-edge-test-${Date.now()}`;
      const res = await fetch(`${BASE_URL}/api/fleet/nodes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: edgeNodeId,
          name: 'Remote Jetson Edge Worker',
          ip_address: 'http://192.168.1.120:5150'
        })
      });
      assert.equal(res.status, 200);
      const data = await res.json();
      assert.equal(data.status, 'success');
      assert.equal(data.node.id, edgeNodeId);
      assert.equal(data.node.name, 'Remote Jetson Edge Worker');
      assert.equal(data.node.ip_address, 'http://192.168.1.120:5150');

      // Test DELETE node endpoint to ensure test node does not linger in DB
      const delRes = await fetch(`${BASE_URL}/api/fleet/nodes/${edgeNodeId}`, {
        method: 'DELETE'
      });
      assert.equal(delRes.status, 200);
      const delData = await delRes.json();
      assert.equal(delData.status, 'success');
    });
  });

  describe('Telemetry & Historical Auditing', () => {
    it('GET /api/fleet/telemetry should return recent hardware telemetry samples', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/telemetry?nodeId=node-jetson-primary`);
      assert.equal(res.status, 200);

      const data = await res.json();
      assert.equal(data.status, 'success');
      assert.ok(Array.isArray(data.samples));
      if (data.samples.length > 0) {
        const sample = data.samples[0];
        assert.ok('cpu_percent' in sample);
        assert.ok('memory_used_gb' in sample);
        assert.ok('memory_percent' in sample);
        assert.ok('storage_mb' in sample);
      }
    });

    it('GET /api/fleet/audit should return audit history with execution durations', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/audit`);
      assert.equal(res.status, 200);

      const data = await res.json();
      assert.equal(data.status, 'success');
      assert.ok(Array.isArray(data.logs));
      if (data.logs.length > 0) {
        const log = data.logs[0];
        assert.ok('agent_id' in log);
        assert.ok('task_name' in log);
        assert.ok('status' in log);
        assert.ok('duration_ms' in log);
      }
    });
  });

  describe('Model Management Endpoint', () => {
    it('GET /api/fleet/nodes/[nodeId]/models should retrieve available models from edge node', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/nodes/node-jetson-primary/models`);
      assert.equal(res.status, 200);

      const data = await res.json();
      assert.equal(data.status, 'success');
      assert.ok(Array.isArray(data.models));
      assert.ok(data.models.length > 0);
      assert.ok(data.active_model, 'Should report active model filename');
    });
  });

  describe('Command Dispatch & Multi-Agent Execution', () => {
    it('POST /api/fleet/nodes/[nodeId]/command should validate prompt requirement', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/nodes/node-jetson-primary/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: '' }) // Empty prompt
      });
      assert.equal(res.status, 400);
      const data = await res.json();
      assert.equal(data.status, 'error');
      assert.match(data.message, /Prompt is required/);
    });

    it('POST /api/fleet/nodes/[nodeId]/command should dispatch command to primary agent (port 5150)', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/nodes/node-jetson-primary/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: 'Echo primary sentinel online verification',
          agentId: 'krok-prime-01',
          port: 5150
        })
      });
      assert.equal(res.status, 200);
      const data = await res.json();
      assert.equal(data.status, 'success');
      assert.ok(data.result);
      assert.equal(data.result.status, 'success');
      assert.ok(data.result.response || data.result.reply !== undefined);
    });

    it('POST /api/fleet/nodes/[nodeId]/deploy-agent should deploy a new uniform worker agent', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/nodes/node-jetson-primary/deploy-agent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: testWorkerId,
          name: 'Automated Test Subagent Worker'
        })
      });
      assert.equal(res.status, 200);
      const data = await res.json();
      assert.equal(data.status, 'success');
      assert.equal(data.agent.id, testWorkerId);
      assert.equal(data.agent.name, 'Automated Test Subagent Worker');
      assert.ok(data.agent.port >= 5152, 'Worker agent should be assigned internal port >= 5152');
      allocatedPort = data.agent.port;
    });

    it('POST /api/fleet/nodes/[nodeId]/command should dispatch command directly to the deployed worker agent', async () => {
      assert.ok(allocatedPort, 'Worker agent must have an allocated port from previous step');

      const res = await fetch(`${BASE_URL}/api/fleet/nodes/node-jetson-primary/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: 'Worker agent diagnostic test',
          agentId: testWorkerId,
          port: allocatedPort
        })
      });
      assert.equal(res.status, 200);
      const data = await res.json();
      assert.equal(data.status, 'success');
      assert.ok(data.result);
      assert.equal(data.result.status, 'success');
    });

    it('POST /api/fleet/nodes/[nodeId]/agents/[agentId]/stop should stop worker agent and update fleet', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/nodes/node-jetson-primary/agents/${testWorkerId}/stop`, {
        method: 'POST'
      });
      assert.equal(res.status, 200);
      const data = await res.json();
      assert.equal(data.status, 'success');
      assert.match(data.message, new RegExp(testWorkerId));
    });

    it('POST /api/fleet/nodes/[nodeId]/agents/[agentId]/stop should protect primary agent from being stopped', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/nodes/node-jetson-primary/agents/krok-prime-01/stop`, {
        method: 'POST'
      });
      assert.ok(res.status === 400 || res.status === 500, 'Attempting to stop primary agent must fail');
      const data = await res.json();
      assert.equal(data.status, 'error');
    });
  });
});
