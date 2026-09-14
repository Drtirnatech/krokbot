import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { dbService, setDb, closeDb, initSchema } from '../src/lib/db.ts';

describe('Enrollment & Pending Nodes Database Service', () => {
  let testDb: DatabaseSync;

  beforeEach(() => {
    testDb = new DatabaseSync(':memory:');
    initSchema(testDb);
    setDb(testDb);
  });

  afterEach(() => {
    closeDb();
  });

  it('should create and validate an enrollment token', () => {
    const token = dbService.createEnrollmentToken('admin', 60);
    assert.ok(token, 'Token should be returned');
    assert.equal(typeof token, 'string');
    assert.ok(token.length >= 16);

    const valid = dbService.validateEnrollmentToken(token);
    assert.equal(valid, true);

    const claimed = dbService.claimEnrollmentToken(token);
    assert.equal(claimed, true);

    // Cannot claim twice
    const secondClaim = dbService.claimEnrollmentToken(token);
    assert.equal(secondClaim, false);
  });

  it('should register, approve, and complete a pending node lifecycle', () => {
    const token = dbService.createEnrollmentToken('admin', 60);
    dbService.upsertPendingNode({
      id: 'node-jetson-pending-01',
      token,
      hostname: 'jetson-orin-01',
      ip_address: '192.168.1.120',
      arch: 'aarch64',
      ram_total_gb: 31.2,
      ram_free_gb: 27.5,
      disk_free_gb: 840.0,
      gpu_info: 'NVIDIA Orin (Ampere, 1024 CUDA cores)'
    });

    const pending = dbService.getPendingNodes();
    assert.equal(pending.length, 1);
    assert.equal(pending[0].hostname, 'jetson-orin-01');
    assert.equal(pending[0].status, 'pending_approval');

    // Approve node
    dbService.approvePendingNode('node-jetson-pending-01', 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf', 'Field Sentinel Alpha');
    const node = dbService.getPendingNode('node-jetson-pending-01');
    assert.equal(node?.status, 'approved');
    assert.equal(node?.selected_model, 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf');
    assert.equal(node?.target_node_name, 'Field Sentinel Alpha');

    // Update progress
    dbService.updatePendingNodeProgress('node-jetson-pending-01', 75.0, 'LOADING_DOCKER_IMAGE');
    const inProgress = dbService.getPendingNode('node-jetson-pending-01');
    assert.equal(inProgress?.progress_percent, 75.0);

    // Complete deployment
    dbService.completePendingNode('node-jetson-pending-01', 'http://192.168.1.120:5150');
    assert.equal(dbService.getPendingNodes().length, 0);

    const activeNode = dbService.getNode('node-jetson-pending-01');
    assert.ok(activeNode);
    assert.equal(activeNode?.name, 'Field Sentinel Alpha');
    assert.equal(activeNode?.ip_address, 'http://192.168.1.120:5150');
  });
});
