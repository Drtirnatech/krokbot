import { DatabaseSync } from 'node:sqlite';
import path from 'node:path';
import fs from 'node:fs';
import crypto from 'node:crypto';

const DB_PATH = process.env.C2_DB_PATH || path.join(process.cwd(), 'c2_fleet.db');

let dbInstance: DatabaseSync | null = null;

export function getDb(): DatabaseSync {
  if (!dbInstance) {
    dbInstance = new DatabaseSync(DB_PATH);
    if (DB_PATH !== ':memory:') {
      dbInstance.exec('PRAGMA journal_mode = WAL;');
    }
    initSchema(dbInstance);
  }
  return dbInstance;
}

export function setDb(db: DatabaseSync | null): void {
  dbInstance = db;
}

export function closeDb(): void {
  if (dbInstance) {
    try {
      dbInstance.close();
    } catch {
      // ignore
    }
    dbInstance = null;
  }
}

export function initSchema(db: DatabaseSync) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS nodes (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      ip_address TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'online',
      active_model TEXT NOT NULL DEFAULT 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf',
      hardware_info TEXT,
      last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS agents (
      id TEXT PRIMARY KEY,
      node_id TEXT NOT NULL,
      name TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'running',
      port INTEGER NOT NULL,
      is_primary INTEGER NOT NULL DEFAULT 0,
      tool_policy TEXT,
      workspace TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS telemetry (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      node_id TEXT NOT NULL,
      cpu_percent REAL,
      memory_used_gb REAL,
      memory_percent REAL,
      storage_mb REAL,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      node_id TEXT,
      agent_id TEXT NOT NULL,
      task_name TEXT NOT NULL,
      status TEXT NOT NULL,
      exit_code INTEGER DEFAULT 0,
      duration_ms REAL DEFAULT 0,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS enrollment_tokens (
      token TEXT PRIMARY KEY,
      created_by TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      expires_at DATETIME NOT NULL,
      is_claimed INTEGER NOT NULL DEFAULT 0,
      claimed_at DATETIME,
      claimed_by_node_id TEXT
    );

    CREATE TABLE IF NOT EXISTS pending_nodes (
      id TEXT PRIMARY KEY,
      token TEXT NOT NULL,
      hostname TEXT NOT NULL,
      ip_address TEXT NOT NULL,
      arch TEXT NOT NULL,
      ram_total_gb REAL NOT NULL,
      ram_free_gb REAL NOT NULL,
      disk_free_gb REAL NOT NULL,
      gpu_info TEXT,
      status TEXT NOT NULL DEFAULT 'pending_approval',
      selected_model TEXT,
      target_node_name TEXT,
      progress_percent REAL NOT NULL DEFAULT 0.0,
      progress_status TEXT,
      last_heartbeat DATETIME DEFAULT CURRENT_TIMESTAMP,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
  `);
}

export interface PendingNodeRecord {
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

export interface EnrollmentTokenRecord {
  token: string;
  created_by: string;
  created_at: string;
  expires_at: string;
  is_claimed: number;
  claimed_at?: string | null;
  claimed_by_node_id?: string | null;
}

export interface NodeRecord {
  id: string;
  name: string;
  ip_address: string;
  status: string;
  active_model: string;
  hardware_info: string | null;
  last_seen: string;
  created_at: string;
  agents?: AgentRecord[];
}

export interface AgentRecord {
  id: string;
  node_id: string;
  name: string;
  status: string;
  port: number;
  is_primary: number;
  tool_policy: string | null;
  workspace: string | null;
  created_at: string;
}

export const dbService = {
  getNodes(): NodeRecord[] {
    const db = getDb();
    const query = db.prepare('SELECT * FROM nodes ORDER BY name ASC');
    const nodes = query.all() as unknown as NodeRecord[];
    
    // Attach agents
    for (const node of nodes) {
      const agentQuery = db.prepare('SELECT * FROM agents WHERE node_id = ? ORDER BY is_primary DESC, name ASC');
      node.agents = agentQuery.all(node.id) as unknown as AgentRecord[];
    }
    return nodes;
  },

  listNodes(): NodeRecord[] {
    return this.getNodes();
  },

  getNode(id: string): NodeRecord | null {
    const db = getDb();
    const query = db.prepare('SELECT * FROM nodes WHERE id = ?');
    const node = query.get(id) as unknown as NodeRecord | undefined;
    if (!node) return null;

    const agentQuery = db.prepare('SELECT * FROM agents WHERE node_id = ? ORDER BY is_primary DESC, name ASC');
    node.agents = agentQuery.all(id) as unknown as AgentRecord[];
    return node;
  },

  upsertNode(node: { id: string; name: string; ip_address: string; status?: string; active_model?: string; hardware_info?: string }): void {
    const db = getDb();
    const stmt = db.prepare(`
      INSERT INTO nodes (id, name, ip_address, status, active_model, hardware_info, last_seen)
      VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
      ON CONFLICT(id) DO UPDATE SET
        name = excluded.name,
        ip_address = excluded.ip_address,
        status = excluded.status,
        active_model = excluded.active_model,
        hardware_info = excluded.hardware_info,
        last_seen = CURRENT_TIMESTAMP;
    `);
    stmt.run(
      node.id,
      node.name,
      node.ip_address,
      node.status || 'online',
      node.active_model || 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf',
      node.hardware_info || null
    );
  },

  upsertAgent(agent: { id: string; node_id: string; name: string; status?: string; port: number; is_primary?: number; workspace?: string }): void {
    const db = getDb();
    const stmt = db.prepare(`
      INSERT INTO agents (id, node_id, name, status, port, is_primary, workspace)
      VALUES (?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        name = excluded.name,
        status = excluded.status,
        port = excluded.port,
        is_primary = excluded.is_primary,
        workspace = excluded.workspace;
    `);
    stmt.run(
      agent.id,
      agent.node_id,
      agent.name,
      agent.status || 'running',
      agent.port,
      agent.is_primary ?? 0,
      agent.workspace || null
    );
  },

  getAgents(nodeId: string): AgentRecord[] {
    const db = getDb();
    const query = db.prepare('SELECT * FROM agents WHERE node_id = ? ORDER BY is_primary DESC, name ASC');
    return query.all(nodeId) as unknown as AgentRecord[];
  },

  deleteAgent(id: string): void {
    const db = getDb();
    const stmt = db.prepare('DELETE FROM agents WHERE id = ?');
    stmt.run(id);
  },

  deleteNode(id: string): void {
    const db = getDb();
    db.exec('PRAGMA foreign_keys = ON;');
    const stmt = db.prepare('DELETE FROM nodes WHERE id = ?');
    stmt.run(id);
    // Ensure any cascaded records are purged
    db.prepare('DELETE FROM agents WHERE node_id = ?').run(id);
    db.prepare('DELETE FROM telemetry WHERE node_id = ?').run(id);
  },

  renameNode(id: string, name: string): void {
    const db = getDb();
    const stmt = db.prepare('UPDATE nodes SET name = ? WHERE id = ?');
    stmt.run(name, id);
  },

  renameAgent(id: string, name: string): void {
    const db = getDb();
    const stmt = db.prepare('UPDATE agents SET name = ? WHERE id = ?');
    stmt.run(name, id);
  },

  recordTelemetry(telemetry: { node_id: string; cpu_percent: number; memory_used_gb: number; memory_percent: number; storage_mb: number }): void {
    const db = getDb();
    const stmt = db.prepare(`
      INSERT INTO telemetry (node_id, cpu_percent, memory_used_gb, memory_percent, storage_mb)
      VALUES (?, ?, ?, ?, ?)
    `);
    stmt.run(
      telemetry.node_id,
      telemetry.cpu_percent,
      telemetry.memory_used_gb,
      telemetry.memory_percent,
      telemetry.storage_mb
    );
  },

  getRecentTelemetry(nodeId: string, limit: number = 20) {
    const db = getDb();
    const stmt = db.prepare('SELECT * FROM telemetry WHERE node_id = ? ORDER BY id DESC, timestamp DESC LIMIT ?');
    return stmt.all(nodeId, limit);
  },

  recordAuditLog(log: { node_id?: string; agent_id: string; task_name: string; status: string; exit_code?: number; duration_ms?: number }): void {
    const db = getDb();
    const stmt = db.prepare(`
      INSERT INTO audit_logs (node_id, agent_id, task_name, status, exit_code, duration_ms)
      VALUES (?, ?, ?, ?, ?, ?)
    `);
    stmt.run(
      log.node_id || null,
      log.agent_id,
      log.task_name,
      log.status,
      log.exit_code || 0,
      log.duration_ms || 0
    );
  },

  getRecentAuditLogs(limit: number = 30) {
    const db = getDb();
    const stmt = db.prepare('SELECT * FROM audit_logs ORDER BY id DESC, timestamp DESC LIMIT ?');
    return stmt.all(limit);
  },

  createEnrollmentToken(createdBy: string = 'admin', expiryMinutes: number = 60): string {
    const db = getDb();
    const randomPart = crypto.randomBytes(12).toString('hex');
    const token = `krok-enroll-${randomPart}`;
    const expiresAt = new Date(Date.now() + expiryMinutes * 60 * 1000).toISOString();
    const stmt = db.prepare(`
      INSERT INTO enrollment_tokens (token, created_by, expires_at)
      VALUES (?, ?, ?)
    `);
    stmt.run(token, createdBy, expiresAt);
    return token;
  },

  validateEnrollmentToken(token: string): boolean {
    const db = getDb();
    const stmt = db.prepare(`
      SELECT * FROM enrollment_tokens WHERE token = ?
    `);
    const record = stmt.get(token) as unknown as EnrollmentTokenRecord | undefined;
    if (!record) return false;
    if (record.is_claimed === 1) return false;
    const expiresAtMs = new Date(record.expires_at).getTime();
    if (Date.now() > expiresAtMs) return false;
    return true;
  },

  claimEnrollmentToken(token: string, nodeId?: string): boolean {
    if (!this.validateEnrollmentToken(token)) return false;
    const db = getDb();
    const stmt = db.prepare(`
      UPDATE enrollment_tokens 
      SET is_claimed = 1, claimed_at = CURRENT_TIMESTAMP, claimed_by_node_id = ?
      WHERE token = ? AND is_claimed = 0
    `);
    const result = stmt.run(nodeId || null, token) as { changes?: number };
    return (result?.changes ?? 1) > 0;
  },

  upsertPendingNode(data: {
    id: string;
    token: string;
    hostname: string;
    ip_address: string;
    arch: string;
    ram_total_gb: number;
    ram_free_gb: number;
    disk_free_gb: number;
    gpu_info?: string | null;
  }): void {
    const db = getDb();
    const stmt = db.prepare(`
      INSERT INTO pending_nodes (
        id, token, hostname, ip_address, arch, ram_total_gb, ram_free_gb, disk_free_gb, gpu_info, status, progress_percent, last_heartbeat
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_approval', 0.0, CURRENT_TIMESTAMP)
      ON CONFLICT(id) DO UPDATE SET
        token = excluded.token,
        hostname = excluded.hostname,
        ip_address = excluded.ip_address,
        arch = excluded.arch,
        ram_total_gb = excluded.ram_total_gb,
        ram_free_gb = excluded.ram_free_gb,
        disk_free_gb = excluded.disk_free_gb,
        gpu_info = excluded.gpu_info,
        last_heartbeat = CURRENT_TIMESTAMP;
    `);
    stmt.run(
      data.id,
      data.token,
      data.hostname,
      data.ip_address,
      data.arch,
      data.ram_total_gb,
      data.ram_free_gb,
      data.disk_free_gb,
      data.gpu_info || null
    );
  },

  getPendingNodes(): PendingNodeRecord[] {
    const db = getDb();
    const stmt = db.prepare(`
      SELECT * FROM pending_nodes WHERE status != 'completed' ORDER BY created_at DESC
    `);
    return stmt.all() as unknown as PendingNodeRecord[];
  },

  getPendingNode(id: string): PendingNodeRecord | null {
    const db = getDb();
    const stmt = db.prepare('SELECT * FROM pending_nodes WHERE id = ?');
    const record = stmt.get(id) as unknown as PendingNodeRecord | undefined;
    return record || null;
  },

  approvePendingNode(id: string, model: string, name?: string): void {
    const db = getDb();
    const stmt = db.prepare(`
      UPDATE pending_nodes
      SET status = 'approved', selected_model = ?, target_node_name = ?, last_heartbeat = CURRENT_TIMESTAMP
      WHERE id = ?
    `);
    stmt.run(model, name || null, id);
  },

  updatePendingNodeProgress(id: string, percent: number, status?: string): void {
    const db = getDb();
    const stmt = db.prepare(`
      UPDATE pending_nodes
      SET progress_percent = ?, progress_status = ?, status = 'streaming', last_heartbeat = CURRENT_TIMESTAMP
      WHERE id = ?
    `);
    stmt.run(percent, status || null, id);
  },

  completePendingNode(id: string, endpointUrl?: string): void {
    const db = getDb();
    const pending = this.getPendingNode(id);
    if (pending) {
      const nodeName = pending.target_node_name || pending.hostname;
      const nodeIp = endpointUrl || pending.ip_address;
      const activeModel = pending.selected_model || 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf';
      const hardwareInfo = `${pending.arch.toUpperCase()} | ${pending.ram_total_gb.toFixed(1)} GB RAM | ${pending.disk_free_gb.toFixed(0)} GB Free Disk${pending.gpu_info ? ` | ${pending.gpu_info}` : ''}`;
      
      this.upsertNode({
        id: pending.id,
        name: nodeName,
        ip_address: nodeIp,
        status: 'online',
        active_model: activeModel,
        hardware_info: hardwareInfo
      });

      this.upsertAgent({
        id: `${pending.id}-agent-01`,
        node_id: pending.id,
        name: `${nodeName} Primary Agent`,
        status: 'running',
        port: 5150,
        is_primary: 1
      });

      const stmt = db.prepare(`
        UPDATE pending_nodes
        SET status = 'completed', progress_percent = 100.0, last_heartbeat = CURRENT_TIMESTAMP
        WHERE id = ?
      `);
      stmt.run(id);
    }
  },

  deletePendingNode(id: string): void {
    const db = getDb();
    const stmt = db.prepare('DELETE FROM pending_nodes WHERE id = ?');
    stmt.run(id);
  }
};
