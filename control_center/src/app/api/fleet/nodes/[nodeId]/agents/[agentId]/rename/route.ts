import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';
import { agentClient } from '@/lib/agent-client';

export async function POST(
  req: Request,
  { params }: { params: Promise<{ nodeId: string; agentId: string }> }
) {
  try {
    const { nodeId, agentId } = await params;
    const body = await req.json();
    const newName = body.name || body.newName;

    if (!newName || typeof newName !== 'string' || !newName.trim()) {
      return NextResponse.json({ status: 'error', message: 'New agent name is required' }, { status: 400 });
    }

    const cleanName = newName.trim();
    const node = dbService.getNode(nodeId);
    if (!node) {
      return NextResponse.json({ status: 'error', message: `Node ${nodeId} not found` }, { status: 404 });
    }

    // Try renaming agent on remote container
    try {
      await agentClient.renameAgent(node.ip_address, agentId, cleanName);
    } catch {
      // Best-effort remote rename if node offline
    }

    // Update SQLite agent record
    dbService.renameAgent(agentId, cleanName);

    // Record audit log
    dbService.recordAuditLog({
      node_id: nodeId,
      agent_id: agentId,
      task_name: `Rename Agent [${agentId} -> ${cleanName}]`,
      status: 'SUCCESS',
      exit_code: 0,
      duration_ms: 10
    });

    return NextResponse.json({ status: 'success', name: cleanName });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}
