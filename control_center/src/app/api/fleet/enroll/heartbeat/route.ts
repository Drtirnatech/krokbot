import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const nodeId = searchParams.get('node_id');

    if (!nodeId) {
      return NextResponse.json({ status: 'error', message: 'node_id is required' }, { status: 400 });
    }

    const node = dbService.getPendingNode(nodeId);
    if (!node) {
      return NextResponse.json({ status: 'error', message: 'Pending node not found' }, { status: 404 });
    }

    if (node.status === 'pending_approval') {
      return NextResponse.json({
        status: 'success',
        action: 'WAIT',
        message: 'Awaiting operator approval',
        progress_percent: node.progress_percent
      });
    }

    if (node.status === 'approved' || node.status === 'streaming') {
      return NextResponse.json({
        status: 'success',
        action: 'DEPLOY',
        selected_model: node.selected_model,
        target_name: node.target_node_name,
        image_stream_url: '/api/fleet/dist/image',
        model_stream_url: `/api/fleet/dist/models/${node.selected_model || 'qwen2.5-coder-1.5b-instruct-q4_k_m.gguf'}`,
        progress_percent: node.progress_percent,
        progress_status: node.progress_status
      });
    }

    return NextResponse.json({
      status: 'success',
      action: node.status.toUpperCase(),
      progress_percent: node.progress_percent
    });
  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: error.message }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { node_id, progress_percent, progress_status } = body;

    if (!node_id) {
      return NextResponse.json({ status: 'error', message: 'node_id is required' }, { status: 400 });
    }

    dbService.updatePendingNodeProgress(
      node_id,
      Number(progress_percent) || 0.0,
      progress_status || 'DOWNLOADING'
    );

    return NextResponse.json({
      status: 'success',
      message: 'Progress updated successfully'
    });
  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: error.message }, { status: 500 });
  }
}
