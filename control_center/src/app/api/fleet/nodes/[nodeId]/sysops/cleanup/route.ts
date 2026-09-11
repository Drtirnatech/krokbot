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
      return NextResponse.json({ status: 'error', message: `Node '${nodeId}' not found` }, { status: 404 });
    }

    const start = Date.now();
    const data = await agentClient.runSysopsCleanup(node.ip_address);
    const duration = Date.now() - start;

    dbService.recordAuditLog({
      node_id: nodeId,
      agent_id: 'sysops-cleanup-engine',
      task_name: 'Edge System Memory & Storage Cleanup',
      status: 'SUCCESS',
      exit_code: 0,
      duration_ms: duration
    });

    return NextResponse.json({ status: 'success', ...data });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}
