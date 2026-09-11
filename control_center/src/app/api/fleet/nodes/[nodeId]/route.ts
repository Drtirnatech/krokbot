import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';

export async function GET(
  req: Request,
  { params }: { params: Promise<{ nodeId: string }> }
) {
  try {
    const { nodeId } = await params;
    const node = dbService.getNode(nodeId);
    if (!node) {
      return NextResponse.json({ status: 'error', message: `Node ${nodeId} not found` }, { status: 404 });
    }
    return NextResponse.json({ status: 'success', node });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}

export async function DELETE(
  req: Request,
  { params }: { params: Promise<{ nodeId: string }> }
) {
  try {
    const { nodeId } = await params;
    const node = dbService.getNode(nodeId);
    if (!node) {
      return NextResponse.json({ status: 'error', message: `Node ${nodeId} not found` }, { status: 404 });
    }

    // Delete node and cascaded agents & telemetry from database
    dbService.deleteNode(nodeId);

    // Record audit log
    dbService.recordAuditLog({
      node_id: nodeId,
      agent_id: 'c2-admin',
      task_name: `Remove Fleet Node [${node.name || nodeId}]`,
      status: 'SUCCESS',
      exit_code: 0,
      duration_ms: 10
    });

    return NextResponse.json({
      status: 'success',
      message: `Node ${nodeId} removed from fleet.`
    });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}
