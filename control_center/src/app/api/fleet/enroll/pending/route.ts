import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';

export async function GET() {
  try {
    const pendingNodes = dbService.getPendingNodes();
    return NextResponse.json({
      status: 'success',
      pending_nodes: pendingNodes
    });
  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: error.message }, { status: 500 });
  }
}

export async function DELETE(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    let id = searchParams.get('id');
    if (!id) {
      const body = await req.json().catch(() => ({}));
      id = body?.id;
    }

    if (!id) {
      return NextResponse.json({ status: 'error', message: 'Node id is required' }, { status: 400 });
    }

    dbService.deletePendingNode(id);
    return NextResponse.json({ status: 'success', message: 'Pending node rejected/removed' });
  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: error.message }, { status: 500 });
  }
}
