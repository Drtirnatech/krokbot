import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';
import { agentClient } from '@/lib/agent-client';

export async function POST(
  req: Request,
  { params }: { params: Promise<{ nodeId: string }> }
) {
  try {
    const { nodeId } = await params;
    const node = dbService.getNode(nodeId);
    if (!node) {
      return NextResponse.json({ status: 'error', message: `Node ${nodeId} not found` }, { status: 404 });
    }

    const body = await req.json();
    const { id, name } = body;
    if (!id || !name) {
      return NextResponse.json({ status: 'error', message: 'Agent id and name are required' }, { status: 400 });
    }

    // Deploy via edge agent API
    const deployRes = await agentClient.deployAgent(node.ip_address, id, name);
    const deployedAgent = deployRes.agent || deployRes;

    // Record in SQLite
    dbService.upsertAgent({
      id: deployedAgent.id,
      node_id: nodeId,
      name: deployedAgent.name,
      port: deployedAgent.port,
      status: deployedAgent.status || 'running',
      is_primary: 0,
      workspace: `/app/workspaces/agent_${deployedAgent.id}`
    });

    // Record audit log
    dbService.recordAuditLog({
      node_id: nodeId,
      agent_id: deployedAgent.id,
      task_name: `Deploy In-Container Agent [${deployedAgent.name}] on port ${deployedAgent.port}`,
      status: 'SUCCESS',
      exit_code: 0,
      duration_ms: 120
    });

    return NextResponse.json({ status: 'success', agent: deployedAgent });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}
