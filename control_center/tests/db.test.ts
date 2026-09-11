import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { dbService, setDb, closeDb, initSchema, getDb } from '../src/lib/db.ts';

describe('C2 Fleet Database Service (dbService)', () => {
  let testDb: DatabaseSync;

  beforeEach(() => {
    // Isolated in-memory database for each test
    testDb = new DatabaseSync(':memory:');
    initSchema(testDb);
    setDb(testDb);
  });

  afterEach(() => {
    closeDb();
  });

  describe('Node Management', () => {
    it('should upsert and retrieve a new edge node', () => {
      dbService.upsertNode({
        id: 'node-jetson-01',
        name: 'Jetson Orin Edge Node',
        ip_address: 'http://192.168.1.50:5150',
        status: 'online',
        active_model: 'Qwen3-4B-Q4_K_M.gguf',
        hardware_info: JSON.stringify({ arch: 'aarch64', vram_gb: 8 })
      });

      const node = dbService.getNode('node-jetson-01');
      assert.ok(node, 'Node should exist');
      assert.equal(node.id, 'node-jetson-01');
      assert.equal(node.name, 'Jetson Orin Edge Node');
      assert.equal(node.ip_address, 'http://192.168.1.50:5150');
      assert.equal(node.status, 'online');
      assert.equal(node.active_model, 'Qwen3-4B-Q4_K_M.gguf');
      assert.deepEqual(JSON.parse(node.hardware_info || '{}'), { arch: 'aarch64', vram_gb: 8 });
    });

    it('should update existing node on conflict', () => {
      dbService.upsertNode({
        id: 'node-alpha',
        name: 'Alpha Node',
        ip_address: 'http://localhost:5150',
        status: 'online'
      });

      // Update status and active model
      dbService.upsertNode({
        id: 'node-alpha',
        name: 'Alpha Node Renamed',
        ip_address: 'http://localhost:5150',
        status: 'offline',
        active_model: 'DeepSeek-R1-Distill-7B.gguf'
      });

      const node = dbService.getNode('node-alpha');
      assert.ok(node);
      assert.equal(node.name, 'Alpha Node Renamed');
      assert.equal(node.status, 'offline');
      assert.equal(node.active_model, 'DeepSeek-R1-Distill-7B.gguf');
    });

    it('should return null when node does not exist', () => {
      const node = dbService.getNode('non-existent-node');
      assert.equal(node, null);
    });

    it('should list all nodes sorted by name', () => {
      dbService.upsertNode({ id: 'node-b', name: 'Bravo Node', ip_address: 'http://10.0.0.2:5150' });
      dbService.upsertNode({ id: 'node-a', name: 'Alpha Node', ip_address: 'http://10.0.0.1:5150' });

      const nodes = dbService.getNodes();
      assert.equal(nodes.length, 2);
      assert.equal(nodes[0].name, 'Alpha Node');
      assert.equal(nodes[1].name, 'Bravo Node');
    });

    it('should delete a node and its attached agents', () => {
      dbService.upsertNode({ id: 'node-delete-test', name: 'Delete Node Test', ip_address: 'http://10.0.0.9:5150' });
      dbService.upsertAgent({ id: 'agent-child-1', node_id: 'node-delete-test', name: 'Child Agent', port: 5160 });

      assert.ok(dbService.getNode('node-delete-test'));
      dbService.deleteNode('node-delete-test');
      assert.equal(dbService.getNode('node-delete-test'), null);
    });
  });

  describe('Agent Management & Multi-Agent Segregation', () => {
    beforeEach(() => {
      dbService.upsertNode({
        id: 'node-master',
        name: 'Master Workstation Node',
        ip_address: 'http://localhost:5150'
      });
    });

    it('should upsert primary agent and secondary worker agents', () => {
      // Primary Sentinel
      dbService.upsertAgent({
        id: 'krok-prime-01',
        node_id: 'node-master',
        name: 'KrokBot Prime Sentinel',
        status: 'running',
        port: 5150,
        is_primary: 1,
        workspace: '/app'
      });

      // Secondary Worker
      dbService.upsertAgent({
        id: 'krok-recon-02',
        node_id: 'node-master',
        name: 'KrokBot Recon Subprocess',
        status: 'running',
        port: 5152,
        is_primary: 0,
        workspace: '/app/workspaces/agent_krok-recon-02'
      });

      // Third Scout Worker
      dbService.upsertAgent({
        id: 'krok-scout-03',
        node_id: 'node-master',
        name: 'KrokBot Scout Worker',
        status: 'stopped',
        port: 5153,
        is_primary: 0,
        workspace: '/app/workspaces/agent_krok-scout-03'
      });

      const node = dbService.getNode('node-master');
      assert.ok(node);
      assert.ok(node.agents);
      assert.equal(node.agents.length, 3);

      // Primary agent should be ordered first (ORDER BY is_primary DESC, name ASC)
      assert.equal(node.agents[0].id, 'krok-prime-01');
      assert.equal(node.agents[0].is_primary, 1);
      assert.equal(node.agents[0].port, 5150);

      // Other workers attached properly
      const recon = node.agents.find(a => a.id === 'krok-recon-02');
      assert.ok(recon);
      assert.equal(recon.port, 5152);
      assert.equal(recon.workspace, '/app/workspaces/agent_krok-recon-02');

      const scout = node.agents.find(a => a.id === 'krok-scout-03');
      assert.ok(scout);
      assert.equal(scout.status, 'stopped');
      assert.equal(scout.port, 5153);
    });

    it('should update agent state without altering other agents', () => {
      dbService.upsertAgent({
        id: 'krok-agent-x',
        node_id: 'node-master',
        name: 'Agent X',
        status: 'running',
        port: 5155
      });

      dbService.upsertAgent({
        id: 'krok-agent-x',
        node_id: 'node-master',
        name: 'Agent X (Updated)',
        status: 'stopped',
        port: 5155
      });

      const node = dbService.getNode('node-master');
      assert.ok(node);
      const agent = node.agents?.find(a => a.id === 'krok-agent-x');
      assert.ok(agent);
      assert.equal(agent.name, 'Agent X (Updated)');
      assert.equal(agent.status, 'stopped');
    });

    it('should delete a worker agent cleanly', () => {
      dbService.upsertAgent({
        id: 'krok-temp-worker',
        node_id: 'node-master',
        name: 'Temporary Worker',
        port: 5159
      });

      let node = dbService.getNode('node-master');
      assert.equal(node?.agents?.some(a => a.id === 'krok-temp-worker'), true);

      dbService.deleteAgent('krok-temp-worker');

      node = dbService.getNode('node-master');
      assert.equal(node?.agents?.some(a => a.id === 'krok-temp-worker'), false);
    });
  });

  describe('Telemetry & Historical Metrics', () => {
    beforeEach(() => {
      dbService.upsertNode({
        id: 'node-telemetry',
        name: 'Telemetry Node',
        ip_address: 'http://127.0.0.1:5150'
      });
    });

    it('should record and retrieve time-series telemetry samples', () => {
      dbService.recordTelemetry({
        node_id: 'node-telemetry',
        cpu_percent: 14.5,
        memory_used_gb: 3.2,
        memory_percent: 42.1,
        storage_mb: 850.0
      });

      dbService.recordTelemetry({
        node_id: 'node-telemetry',
        cpu_percent: 22.8,
        memory_used_gb: 3.5,
        memory_percent: 46.0,
        storage_mb: 855.0
      });

      const history = dbService.getRecentTelemetry('node-telemetry', 10) as any[];
      assert.equal(history.length, 2);
      // Most recent first
      assert.equal(history[0].cpu_percent, 22.8);
      assert.equal(history[1].cpu_percent, 14.5);
    });

    it('should respect the limit parameter for telemetry history', () => {
      for (let i = 1; i <= 5; i++) {
        dbService.recordTelemetry({
          node_id: 'node-telemetry',
          cpu_percent: i * 5,
          memory_used_gb: 2.0,
          memory_percent: 30.0,
          storage_mb: 500.0
        });
      }

      const history = dbService.getRecentTelemetry('node-telemetry', 3);
      assert.equal(history.length, 3);
    });
  });

  describe('Audit Logging & Activity Tracking', () => {
    it('should record and fetch audit logs for agent operations', () => {
      dbService.recordAuditLog({
        node_id: 'node-jetson',
        agent_id: 'krok-prime-01',
        task_name: 'Spawn In-Container Agent [krok-recon-02]',
        status: 'SUCCESS',
        exit_code: 0,
        duration_ms: 125.4
      });

      dbService.recordAuditLog({
        node_id: 'node-jetson',
        agent_id: 'krok-recon-02',
        task_name: 'Execute Diagnostics Script bench.py',
        status: 'SUCCESS',
        exit_code: 0,
        duration_ms: 840.2
      });

      const logs = dbService.getRecentAuditLogs(20) as any[];
      assert.ok(logs.length >= 2);
      assert.equal(logs[0].agent_id, 'krok-recon-02');
      assert.equal(logs[0].status, 'SUCCESS');
      assert.equal(logs[1].agent_id, 'krok-prime-01');
    });
  });
});
