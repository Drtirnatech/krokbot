import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';
import { agentClient } from '@/lib/agent-client';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { prompt, save_mode } = body;

    if (!prompt || typeof prompt !== 'string' || !prompt.trim()) {
      return NextResponse.json({ status: 'error', message: 'Directive prompt is required' }, { status: 400 });
    }

    const nodes = dbService.listNodes();
    if (!nodes || nodes.length === 0) {
      return NextResponse.json({ status: 'error', message: 'No active edge nodes registered in C2 fleet' }, { status: 404 });
    }

    const start = Date.now();
    // Broadcast concurrently to primary sentinels across all registered nodes
    const results = await Promise.allSettled(
      nodes.map(async (node) => {
        const nodeStart = Date.now();
        try {
          const res = await agentClient.sendPrompt(node.ip_address, prompt.trim(), 5150, 'krok-prime-01', save_mode);
          const dur = Date.now() - nodeStart;
          dbService.recordAuditLog({
            node_id: node.id,
            agent_id: 'krok-prime-01',
            task_name: `Fleet Broadcast: "${prompt.trim().slice(0, 40)}"`,
            status: 'SUCCESS',
            exit_code: 0,
            duration_ms: dur
          });
          return { nodeId: node.id, status: 'success', data: res };
        } catch (err: any) {
          const dur = Date.now() - nodeStart;
          dbService.recordAuditLog({
            node_id: node.id,
            agent_id: 'krok-prime-01',
            task_name: `Fleet Broadcast: "${prompt.trim().slice(0, 40)}"`,
            status: 'FAILED',
            exit_code: 1,
            duration_ms: dur
          });
          return { nodeId: node.id, status: 'error', message: err.message };
        }
      })
    );

    const totalDuration = Date.now() - start;

    return NextResponse.json({
      status: 'success',
      total_nodes: nodes.length,
      duration_ms: totalDuration,
      results: results.map((r) => (r.status === 'fulfilled' ? r.value : { status: 'error', reason: r.reason })),
      broadcast_results: results.map((r) => (r.status === 'fulfilled' ? r.value : { status: 'error', reason: r.reason }))
    });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}
