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

    const cleanUrl = node.ip_address.replace(/\/+$/, '');
    const res = await fetch(`${cleanUrl}/api/models`, { signal: AbortSignal.timeout(4000) });
    if (!res.ok) {
      return NextResponse.json({ status: 'error', message: 'Failed to fetch models from node' }, { status: 502 });
    }
    const data = await res.json();
    return NextResponse.json({
      status: 'success',
      active_model: data.active_config?.name || data.active_model || 'Unknown',
      models: data.available || data.models || [],
      available: data.available || [],
      catalog: data.catalog || []
    });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}
