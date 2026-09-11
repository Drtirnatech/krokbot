import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';
import { agentClient } from '@/lib/agent-client';

export async function POST(
  req: Request,
  { params }: { params: Promise<{ nodeId: string; agentId: string }> }
) {
  try {
    const { nodeId, agentId } = await params;
    const node = dbService.getNode(nodeId);
    if (!node) {
      return NextResponse.json({ status: 'error', message: `Node ${nodeId} not found` }, { status: 404 });
    }

    // Stop via edge agent API
    await agentClient.stopAgent(node.ip_address, agentId);

    // Delete from SQLite
    dbService.deleteAgent(agentId);

    // Record audit log
    dbService.recordAuditLog({
      node_id: nodeId,
      agent_id: agentId,
      task_name: `Stop In-Container Agent [${agentId}]`,
      status: 'SUCCESS',
      exit_code: 0,
      duration_ms: 45
    });

    return NextResponse.json({ status: 'success', message: `Agent ${agentId} stopped` });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}
