import { NextResponse } from 'next/server';
import { dbService } from '@/lib/db';

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(() => ({}));
    const expiryMinutes = Number(body?.expiry_minutes) || 60;
    const createdBy = body?.created_by || 'admin';
    const hostHeader = req.headers.get('host') || 'localhost:5200';
    const proto = req.headers.get('x-forwarded-proto') || 'http';
    const c2Url = `${proto}://${hostHeader}`;

    const token = dbService.createEnrollmentToken(createdBy, expiryMinutes);
    const dockerCommand = `docker run -d --name krokbot-bootstrap --restart on-failure -v /var/run/docker.sock:/var/run/docker.sock -v /opt/krokbot:/host_opt_krokbot -e C2_URL="${c2Url}" -e ENROLLMENT_TOKEN="${token}" krokbot-bootstrap:latest`;

    return NextResponse.json({
      status: 'success',
      token,
      c2_url: c2Url,
      docker_command: dockerCommand,
      expires_in_minutes: expiryMinutes
    });
  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: error.message }, { status: 500 });
  }
}
