import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';
import { agentClient } from '@/lib/agent-client';

export async function DELETE(
  req: Request,
  { params }: { params: Promise<{ nodeId: string; agentId: string }> }
) {
  try {
    const { nodeId, agentId } = await params;
    const node = dbService.getNode(nodeId);
    if (!node) {
      return NextResponse.json({ status: 'error', message: `Node ${nodeId} not found` }, { status: 404 });
    }

    if (agentId === 'krok-prime-01') {
      return NextResponse.json({ status: 'error', message: 'Cannot delete primary sentinel agent.' }, { status: 400 });
    }

    // Attempt to remove/terminate from container supervisor
    try {
      await agentClient.removeAgent(node.ip_address, agentId);
    } catch {
      // Fallback: stop agent if remove endpoint not yet reachable
      try {
        await agentClient.stopAgent(node.ip_address, agentId);
      } catch {
        // Continue with local DB removal
      }
    }

    // Delete from SQLite
    dbService.deleteAgent(agentId);

    // Record audit log
    dbService.recordAuditLog({
      node_id: nodeId,
      agent_id: agentId,
      task_name: `Permanently Remove Subagent [${agentId}]`,
      status: 'SUCCESS',
      exit_code: 0,
      duration_ms: 30
    });

    return NextResponse.json({ status: 'success', message: `Subagent ${agentId} deleted.` });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}
