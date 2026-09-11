import { DatabaseSync } from 'node:sqlite';
import path from 'node:path';
import fs from 'node:fs';

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
      active_model TEXT NOT NULL DEFAULT 'Qwen3-4B-Q4_K_M.gguf',
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
  `);
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
      node.active_model || 'Qwen3-4B-Q4_K_M.gguf',
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

  deleteAgent(id: string): void {
    const db = getDb();
    const stmt = db.prepare('DELETE FROM agents WHERE id = ?');
    stmt.run(id);
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
  }
};
