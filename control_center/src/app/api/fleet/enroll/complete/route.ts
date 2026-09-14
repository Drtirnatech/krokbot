import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { node_id, endpoint_url } = body;

    if (!node_id) {
      return NextResponse.json({ status: 'error', message: 'node_id is required' }, { status: 400 });
    }

    const pending = dbService.getPendingNode(node_id);
    if (!pending) {
      return NextResponse.json({ status: 'error', message: 'Pending node not found' }, { status: 404 });
    }

    dbService.completePendingNode(node_id, endpoint_url);

    return NextResponse.json({
      status: 'success',
      message: 'Node successfully deployed and activated in fleet',
      node_id
    });
  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: error.message }, { status: 500 });
  }
}
