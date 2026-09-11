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
    const { prompt, agentId, port, save_mode } = body;
    if (!prompt) {
      return NextResponse.json({ status: 'error', message: 'Prompt is required' }, { status: 400 });
    }

    const start = Date.now();
    const result = await agentClient.sendPrompt(node.ip_address, prompt, port, agentId, save_mode);
    const duration = Date.now() - start;

    // Record audit log
    dbService.recordAuditLog({
      node_id: nodeId,
      agent_id: agentId || 'krok-prime-01',
      task_name: `Command Dispatch: "${prompt.slice(0, 45)}${prompt.length > 45 ? '...' : ''}"`,
      status: 'SUCCESS',
      exit_code: 0,
      duration_ms: duration
    });

    return NextResponse.json({ status: 'success', result });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}
