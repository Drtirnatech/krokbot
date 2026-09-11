import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

const BASE_URL = process.env.C2_TEST_URL || 'http://localhost:5200';
const NODE_ID = 'node-jetson-primary';

describe('C2 Fleet Edge Compute SysOps & Watchdog API Operations', () => {
  describe('Edge Compute Telemetry & Thermals', () => {
    it('GET /api/fleet/nodes/{nodeId}/sysops/telemetry returns hardware thermals and storage', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/nodes/${NODE_ID}/sysops/telemetry`);
      assert.equal(res.status, 200);

      const data = await res.json();
      assert.equal(data.status, 'success');
      assert.ok(data.diagnostics, 'diagnostics must be defined');
      assert.ok(data.diagnostics.thermals, 'thermals must be present');
      assert.ok(typeof data.diagnostics.thermals.max_temp_c === 'number', 'max_temp_c must be numeric');
      assert.ok(Array.isArray(data.diagnostics.storage), 'storage partitions must be an array');
      assert.ok(data.diagnostics.cpu, 'cpu metrics must be defined');
    });
  });

  describe('Process Supervisor & Safety Protection', () => {
    it('GET /api/fleet/nodes/{nodeId}/sysops/processes lists processes with protected flags', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/nodes/${NODE_ID}/sysops/processes`);
      assert.equal(res.status, 200);

      const data = await res.json();
      assert.equal(data.status, 'success');
      assert.ok(Array.isArray(data.processes), 'processes must be an array');
      assert.ok(data.processes.length > 0, 'should return at least one process');

      const pid1 = data.processes.find((p: any) => p.pid === 1);
      if (pid1) {
        assert.equal(pid1.is_protected, true, 'PID 1 must be marked as protected');
      }
    });

    it('POST /api/fleet/nodes/{nodeId}/sysops/processes/1/kill refuses termination of protected PID 1', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/nodes/${NODE_ID}/sysops/processes/1/kill`, {
        method: 'POST'
      });
      assert.equal(res.status, 403, 'Attempt to kill PID 1 must return 403 Forbidden');

      const data = await res.json();
      assert.equal(data.status, 'error');
      assert.match(data.message, /protected by edge safety policy/);
    });
  });

  describe('Edge Memory Trimming & Storage Cleanup', () => {
    it('POST /api/fleet/nodes/{nodeId}/sysops/cleanup runs malloc_trim and temporary cache pruning', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/nodes/${NODE_ID}/sysops/cleanup`, {
        method: 'POST'
      });
      assert.equal(res.status, 200);

      const data = await res.json();
      assert.equal(data.status, 'success');
      assert.ok(data.result, 'result object must be returned');
      assert.ok(typeof data.result.gc_objects_collected === 'number', 'gc_objects_collected must be numeric');
      assert.ok('malloc_trimmed' in data.result, 'malloc_trimmed boolean must be present');
    });
  });

  describe('Self-Healing Watchdog Engine Policies', () => {
    it('GET /api/fleet/nodes/{nodeId}/sysops/watchdog returns operational watchdog policies', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/nodes/${NODE_ID}/sysops/watchdog`);
      assert.equal(res.status, 200);

      const data = await res.json();
      assert.equal(data.status, 'success');
      assert.ok(Array.isArray(data.policies), 'policies must be an array');
      assert.ok(data.policies.length >= 3, 'should have at least storage, thermal, and memory policies');
    });

    it('POST /api/fleet/nodes/{nodeId}/sysops/watchdog toggles policy state', async () => {
      const toggleRes = await fetch(`${BASE_URL}/api/fleet/nodes/${NODE_ID}/sysops/watchdog`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ policyId: 'policy_storage_pressure' })
      });
      assert.equal(toggleRes.status, 200);

      const toggleData = await toggleRes.json();
      assert.equal(toggleData.status, 'success');
      assert.ok('policy' in toggleData, 'updated policy must be returned');
    });
  });

  describe('Fleet-Wide Parallel Command Broadcast', () => {
    it('POST /api/fleet/broadcast executes prompt concurrently across fleet nodes', async () => {
      const res = await fetch(`${BASE_URL}/api/fleet/broadcast`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: 'Quick edge compute heartbeat check' })
      });
      assert.equal(res.status, 200);

      const data = await res.json();
      assert.equal(data.status, 'success');
      assert.ok(data.total_nodes >= 1, 'must have targeted at least 1 node');
      assert.ok(Array.isArray(data.results), 'results must be an array');
      assert.equal(data.results.length, data.total_nodes);

      const primaryResult = data.results.find((r: any) => r.nodeId === NODE_ID);
      assert.ok(primaryResult, 'Primary node execution result must be present in broadcast response');
    });
  });
});
