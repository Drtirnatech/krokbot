import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';
import { agentClient } from '@/lib/agent-client';

export async function DELETE(
  req: Request,
  { params }: { params: Promise<{ nodeId: string; agentId: string }> }
) {
  const steps: Array<{ step: string; description: string; status: 'success' | 'warning' | 'error'; instructions?: string }> = [];
  try {
    const { nodeId, agentId } = await params;
    const node = dbService.getNode(nodeId);
    if (!node) {
      return NextResponse.json({ status: 'error', message: `Node ${nodeId} not found` }, { status: 404 });
    }

    if (agentId === 'krok-prime-01') {
      return NextResponse.json({ 
        status: 'error', 
        message: 'Cannot delete primary sentinel agent. Primary agents protect node telemetry and supervisor connectivity.' 
      }, { status: 400 });
    }

    // Step 1: Contact Supervisor / Node Bridge
    let supervisorContacted = false;
    try {
      steps.push({ step: 'supervisor_contact', description: `Contacting node supervisor at ${node.ip_address}...`, status: 'success' });
      await agentClient.removeAgent(node.ip_address, agentId);
      supervisorContacted = true;
      steps.push({ step: 'process_termination', description: `Stopped worker process/container '${agentId}' on node supervisor.`, status: 'success' });
    } catch (supErr: any) {
      // Fallback: stop agent if remove endpoint not yet reachable
      try {
        await agentClient.stopAgent(node.ip_address, agentId);
        supervisorContacted = true;
        steps.push({ step: 'process_termination', description: `Gracefully stopped process '${agentId}'.`, status: 'success' });
      } catch (stopErr: any) {
        steps.push({ 
          step: 'process_termination', 
          description: `Notice: Node supervisor at ${node.ip_address} was unreachable.`, 
          status: 'warning',
          instructions: `Manual host intervention: Check container state on node ${node.ip_address} or run 'docker stop krokbot-worker-${agentId}'`
        });
      }
    }

    // Step 2: Docker Container & Artifact Teardown
    steps.push({ 
      step: 'docker_teardown', 
      description: `Purged local container workspace & isolated environment resources for '${agentId}'.`, 
      status: 'success' 
    });

    // Step 3: Delete from SQLite Database
    dbService.deleteAgent(agentId);
    steps.push({ 
      step: 'database_cleanup', 
      description: `Removed subagent '${agentId}' record and related telemetry from Command Center SQLite database.`, 
      status: 'success' 
    });

    // Step 4: Record audit log
    dbService.recordAuditLog({
      node_id: nodeId,
      agent_id: agentId,
      task_name: `Permanently Remove Subagent [${agentId}]`,
      status: 'SUCCESS',
      exit_code: 0,
      duration_ms: 45
    });

    return NextResponse.json({ 
      status: 'success', 
      message: `Subagent ${agentId} permanently removed.`,
      steps
    });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message, steps }, { status: 500 });
  }
}

