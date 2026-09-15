import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';
import { agentClient } from '@/lib/agent-client';

export async function GET() {
  try {
    let nodes = dbService.getNodes();

    // Auto-seed local node ONLY once on initial system deployment
    if (nodes.length === 0 && !dbService.isFleetSeeded()) {
      dbService.upsertNode({
        id: 'node-jetson-primary',
        name: 'Workstation / Jetson Master Node',
        ip_address: 'http://localhost:5150',
        status: 'online',
        active_model: 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf',
        hardware_info: JSON.stringify({ device: 'Local KrokBot Container', arch: 'x86_64/ARM64' })
      });
      dbService.setFleetSeeded();
      nodes = dbService.getNodes();
    }

    // Refresh live health metrics for each node
    const refreshedNodes = await Promise.all(
      nodes.map(async (node) => {
        const health = await agentClient.fetchNodeHealth(node.ip_address);
        
        // Update SQLite with live state
        dbService.upsertNode({
          id: node.id,
          name: node.name,
          ip_address: node.ip_address,
          status: health.isOnline ? 'online' : 'offline',
          active_model: health.activeModel,
          hardware_info: node.hardware_info || undefined
        });

        if (health.isOnline) {
          // Record telemetry sample
          dbService.recordTelemetry({
            node_id: node.id,
            cpu_percent: health.cpuPercent,
            memory_used_gb: health.memoryUsedGb,
            memory_percent: health.memoryPercent,
            storage_mb: health.storageMb
          });

          // Reconcile and sync co-located agents into SQLite
          if (health.agents && health.agents.length > 0) {
            const liveAgentIds = new Set(health.agents.map((a: any) => a.id));
            const currentDbAgents = dbService.getAgents(node.id) || [];
            for (const existing of currentDbAgents) {
              if (existing.is_primary !== 1 && !liveAgentIds.has(existing.id)) {
                dbService.deleteAgent(existing.id);
              }
            }

            for (const a of health.agents) {
              dbService.upsertAgent({
                id: a.id,
                node_id: node.id,
                name: a.name,
                port: a.port,
                status: a.status,
                is_primary: a.is_primary ? 1 : 0
              });
            }
          }
        }

        const updatedNode = dbService.getNode(node.id);

        return {
          ...(updatedNode || node),
          status: health.isOnline ? 'online' : 'offline',
          active_model: health.activeModel,
          liveHealth: health
        };
      })
    );

    return NextResponse.json({
      status: 'success',
      nodes: refreshedNodes,
      timestamp: new Date().toISOString()
    });
  } catch (err: any) {
    return NextResponse.json(
      { status: 'error', message: err.message },
      { status: 500 }
    );
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { id, name, ip_address } = body;

    if (!id || !name || !ip_address) {
      return NextResponse.json(
        { status: 'error', message: 'Missing required node parameters: id, name, ip_address' },
        { status: 400 }
      );
    }

    dbService.upsertNode({
      id,
      name,
      ip_address: ip_address.replace(/\/+$/, '')
    });

    const node = dbService.getNode(id);
    return NextResponse.json({ status: 'success', node });
  } catch (err: any) {
    return NextResponse.json(
      { status: 'error', message: err.message },
      { status: 500 }
    );
  }
}
