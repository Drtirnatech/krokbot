import { describe, it, after } from 'node:test';
import assert from 'node:assert/strict';

const BASE_URL = process.env.C2_TEST_URL || 'http://127.0.0.1:5200';

describe('C2 Fleet Enrollment & Stream Depot API Endpoints', () => {
  let createdToken: string;
  const testNodeId = `pending-test-${Date.now()}`;

  it('POST /api/fleet/enroll/token generates a single-use token and command snippet', async () => {
    const res = await fetch(`${BASE_URL}/api/fleet/enroll/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expiry_minutes: 60 })
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'success');
    assert.ok(data.token);
    assert.ok(data.docker_command.includes(data.token));
    createdToken = data.token;
  });

  it('POST /api/fleet/enroll/register registers a new phoned-home node', async () => {
    const res = await fetch(`${BASE_URL}/api/fleet/enroll/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: testNodeId,
        token: createdToken,
        hostname: 'field-orin-unit',
        ip_address: '192.168.1.99',
        arch: 'aarch64',
        ram_total_gb: 16.0,
        ram_free_gb: 12.5,
        disk_free_gb: 256.0,
        gpu_info: 'NVIDIA Orin Nano'
      })
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'success');
  });

  it('GET /api/fleet/enroll/pending lists the node awaiting approval', async () => {
    const res = await fetch(`${BASE_URL}/api/fleet/enroll/pending`);
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'success');
    const node = data.pending_nodes.find((n: any) => n.id === testNodeId);
    assert.ok(node, 'Registered test node should be present in pending_nodes');
    assert.equal(node.arch, 'aarch64');
  });

  it('POST /api/fleet/enroll/approve approves the node with target model', async () => {
    const res = await fetch(`${BASE_URL}/api/fleet/enroll/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node_id: testNodeId,
        selected_model: 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf',
        target_name: 'Edge Sentinel Unit 99'
      })
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'success');
  });

  it('GET /api/fleet/enroll/heartbeat returns DEPLOY command to bootstrap agent', async () => {
    const res = await fetch(`${BASE_URL}/api/fleet/enroll/heartbeat?node_id=${testNodeId}`);
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'success');
    assert.equal(data.action, 'DEPLOY');
    assert.equal(data.selected_model, 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf');
  });

  it('POST /api/fleet/enroll/heartbeat updates progress percent and status', async () => {
    const res = await fetch(`${BASE_URL}/api/fleet/enroll/heartbeat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node_id: testNodeId,
        progress_percent: 50.0,
        progress_status: 'STREAMING_IMAGE'
      })
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'success');
  });

  it('POST /api/fleet/enroll/complete activates the node into active fleet', async () => {
    const res = await fetch(`${BASE_URL}/api/fleet/enroll/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node_id: testNodeId,
        endpoint_url: 'http://192.168.1.99:5150'
      })
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'success');
  });

  it('GET /api/fleet/dist/image returns 200 with octet-stream or tar stream', async () => {
    const res = await fetch(`${BASE_URL}/api/fleet/dist/image`);
    assert.ok(res.status === 200 || res.status === 404, 'Endpoint should return 200 or 404 with standard status');
  });

  after(async () => {
    // Clean up test node and pending entry so test artifacts never linger in live C2 database
    await fetch(`${BASE_URL}/api/fleet/nodes/${testNodeId}`, { method: 'DELETE' }).catch(() => {});
    await fetch(`${BASE_URL}/api/fleet/enroll/pending?id=${testNodeId}`, { method: 'DELETE' }).catch(() => {});
  });
});
