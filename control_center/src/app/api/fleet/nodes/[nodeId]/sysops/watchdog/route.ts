import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';
import { agentClient } from '@/lib/agent-client';

export async function GET(
  req: Request,
  { params }: { params: Promise<{ nodeId: string }> }
) {
  try {
    const { nodeId } = await params;
    const node = dbService.getNode(nodeId);
    if (!node) {
      return NextResponse.json({ status: 'error', message: `Node '${nodeId}' not found` }, { status: 404 });
    }

    const data = await agentClient.fetchWatchdogPolicies(node.ip_address);
    return NextResponse.json({ status: 'success', nodeId, ...data });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}

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

    const body = await req.json();
    const { policyId } = body;
    if (!policyId) {
      return NextResponse.json({ status: 'error', message: 'Missing policyId' }, { status: 400 });
    }

    const start = Date.now();
    const data = await agentClient.toggleWatchdogPolicy(node.ip_address, policyId);
    const duration = Date.now() - start;

    dbService.recordAuditLog({
      node_id: nodeId,
      agent_id: 'sysops-watchdog',
      task_name: `Toggle Watchdog Policy [${policyId}]`,
      status: 'SUCCESS',
      exit_code: 0,
      duration_ms: duration
    });

    return NextResponse.json({ status: 'success', ...data });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}
