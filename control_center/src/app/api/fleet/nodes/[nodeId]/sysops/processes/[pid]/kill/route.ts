import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';
import { agentClient } from '@/lib/agent-client';

export async function POST(
  req: Request,
  { params }: { params: Promise<{ nodeId: string; pid: string }> }
) {
  try {
    const { nodeId, pid } = await params;
    const node = dbService.getNode(nodeId);
    if (!node) {
      return NextResponse.json({ status: 'error', message: `Node '${nodeId}' not found` }, { status: 404 });
    }

    const pidNum = parseInt(pid, 10);
    if (isNaN(pidNum)) {
      return NextResponse.json({ status: 'error', message: `Invalid PID: '${pid}'` }, { status: 400 });
    }

    const start = Date.now();
    const data = await agentClient.killSysopsProcess(node.ip_address, pidNum, false);
    const duration = Date.now() - start;

    dbService.recordAuditLog({
      node_id: nodeId,
      agent_id: 'sysops-process-manager',
      task_name: `Terminate Process [PID ${pidNum}]`,
      status: 'SUCCESS',
      exit_code: 0,
      duration_ms: duration
    });

    return NextResponse.json({ status: 'success', ...data });
  } catch (err: any) {
    const statusCode = err.status || (err.message?.includes('protected') ? 403 : 500);
    return NextResponse.json({ status: 'error', message: err.message }, { status: statusCode });
  }
}
