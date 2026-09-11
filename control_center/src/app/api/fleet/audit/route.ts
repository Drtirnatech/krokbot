import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';

export async function GET() {
  try {
    const logs = dbService.getRecentAuditLogs(50);
    return NextResponse.json({ status: 'success', logs });
  } catch (err: any) {
    return NextResponse.json({ status: 'error', message: err.message }, { status: 500 });
  }
}
