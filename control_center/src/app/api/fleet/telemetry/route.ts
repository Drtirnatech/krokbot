import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const nodeId = searchParams.get('nodeId') || 'node-jetson-primary';
    const samples = dbService.getRecentTelemetry(nodeId, 25);
    return NextResponse.json({ status: 'success', nodeId, samples });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}
