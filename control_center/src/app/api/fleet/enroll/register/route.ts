import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { id, token, hostname, ip_address, arch, ram_total_gb, ram_free_gb, disk_free_gb, gpu_info } = body;

    if (!id || !token || !hostname) {
      return NextResponse.json(
        { status: 'error', message: 'id, token, and hostname are required' },
        { status: 400 }
      );
    }

    if (!dbService.validateEnrollmentToken(token)) {
      return NextResponse.json(
        { status: 'error', message: 'Invalid or expired enrollment token' },
        { status: 401 }
      );
    }

    dbService.claimEnrollmentToken(token, id);
    dbService.upsertPendingNode({
      id,
      token,
      hostname,
      ip_address: ip_address || '127.0.0.1',
      arch: arch || 'x86_64',
      ram_total_gb: Number(ram_total_gb) || 8.0,
      ram_free_gb: Number(ram_free_gb) || 4.0,
      disk_free_gb: Number(disk_free_gb) || 50.0,
      gpu_info: gpu_info || null
    });

    return NextResponse.json({
      status: 'success',
      message: 'Node successfully registered and awaiting approval',
      id
    });
  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: error.message }, { status: 500 });
  }
}
