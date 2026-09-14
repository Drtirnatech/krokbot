import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { node_id, selected_model, target_name } = body;

    if (!node_id || !selected_model) {
      return NextResponse.json(
        { status: 'error', message: 'node_id and selected_model are required' },
        { status: 400 }
      );
    }

    const node = dbService.getPendingNode(node_id);
    if (!node) {
      return NextResponse.json(
        { status: 'error', message: 'Pending node not found' },
        { status: 404 }
      );
    }

    dbService.approvePendingNode(node_id, selected_model, target_name);

    return NextResponse.json({
      status: 'success',
      message: 'Node approved for deployment',
      node_id,
      selected_model,
      target_name: target_name || node.hostname
    });
  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: error.message }, { status: 500 });
  }
}
