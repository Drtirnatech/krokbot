import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';
import { agentClient } from '@/lib/agent-client';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { prompt, save_mode, include_subagents } = body;

    if (!prompt || typeof prompt !== 'string' || !prompt.trim()) {
      return NextResponse.json({ status: 'error', message: 'Directive prompt is required' }, { status: 400 });
    }

    const nodes = dbService.listNodes();
    if (!nodes || nodes.length === 0) {
      return NextResponse.json({ status: 'error', message: 'No active edge nodes registered in C2 fleet' }, { status: 404 });
    }

    // Build target list: Primary Sentinels Only OR Swarm Mode (Primary + All Workers)
    const targets: Array<{
      node: typeof nodes[0];
      agent: { id: string; name: string; port: number; is_primary: number };
    }> = [];

    for (const node of nodes) {
      const nodeAgents = node.agents || [];
      if (include_subagents && nodeAgents.length > 0) {
        for (const ag of nodeAgents) {
          targets.push({
            node,
            agent: {
              id: ag.id,
              name: ag.name,
              port: ag.port,
              is_primary: ag.is_primary ? 1 : 0
            }
          });
        }
      } else {
        const primaryAg = nodeAgents.find(a => a.is_primary === 1) || {
          id: 'krok-prime-01',
          name: 'Primary Sentinel',
          port: 5150,
          is_primary: 1
        };
        targets.push({
          node,
          agent: primaryAg
        });
      }
    }

    const start = Date.now();
    // Broadcast concurrently across all resolved targets
    const results = await Promise.allSettled(
      targets.map(async ({ node, agent }) => {
        const targetStart = Date.now();
        try {
          const res = await agentClient.sendPrompt(node.ip_address, prompt.trim(), agent.port, agent.id, save_mode);
          const dur = Date.now() - targetStart;
          dbService.recordAuditLog({
            node_id: node.id,
            agent_id: agent.id,
            task_name: `Fleet Broadcast: "${prompt.trim().slice(0, 40)}"`,
            status: 'SUCCESS',
            exit_code: 0,
            duration_ms: dur
          });
          return {
            nodeId: node.id,
            agentId: agent.id,
            agentName: agent.name,
            isPrimary: agent.is_primary === 1,
            status: 'success',
            data: res
          };
        } catch (err: any) {
          const dur = Date.now() - targetStart;
          dbService.recordAuditLog({
            node_id: node.id,
            agent_id: agent.id,
            task_name: `Fleet Broadcast: "${prompt.trim().slice(0, 40)}"`,
            status: 'FAILED',
            exit_code: 1,
            duration_ms: dur
          });
          return {
            nodeId: node.id,
            agentId: agent.id,
            agentName: agent.name,
            isPrimary: agent.is_primary === 1,
            status: 'error',
            message: err.message
          };
        }
      })
    );

    const totalDuration = Date.now() - start;

    return NextResponse.json({
      status: 'success',
      total_nodes: nodes.length,
      total_targets: targets.length,
      include_subagents: !!include_subagents,
      duration_ms: totalDuration,
      results: results.map((r) => (r.status === 'fulfilled' ? r.value : { status: 'error', reason: r.reason })),
      broadcast_results: results.map((r) => (r.status === 'fulfilled' ? r.value : { status: 'error', reason: r.reason }))
    });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}
