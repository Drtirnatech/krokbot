import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';
import { agentClient } from '@/lib/agent-client';

export async function POST(
  req: Request,
  { params }: { params: Promise<{ nodeId: string; modelName: string }> }
) {
  try {
    const { nodeId, modelName } = await params;
    const node = dbService.getNode(nodeId);
    if (!node) {
      return NextResponse.json({ status: 'error', message: `Node ${nodeId} not found` }, { status: 404 });
    }

    const decodedModelName = decodeURIComponent(modelName);
    const start = Date.now();
    const res = await agentClient.switchModel(node.ip_address, decodedModelName);
    const duration = Date.now() - start;

    // Update node active_model in SQLite
    dbService.upsertNode({
      id: node.id,
      name: node.name,
      ip_address: node.ip_address,
      active_model: decodedModelName,
      status: 'online'
    });

    // Record audit log
    dbService.recordAuditLog({
      node_id: nodeId,
      agent_id: 'shared-inference-arbiter',
      task_name: `Activate Model [${decodedModelName}]`,
      status: 'SUCCESS',
      exit_code: 0,
      duration_ms: duration
    });

    return NextResponse.json({ status: 'success', result: res });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}
