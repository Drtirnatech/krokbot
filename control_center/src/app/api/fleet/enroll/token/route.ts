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

    const bashCommand = `docker run -d \\\n  --name krokbot-bootstrap \\\n  --restart on-failure \\\n  -v /var/run/docker.sock:/var/run/docker.sock \\\n  -v /opt/krokbot:/host_opt_krokbot \\\n  -e C2_URL="${c2Url}" \\\n  -e ENROLLMENT_TOKEN="${token}" \\\n  krokbot-bootstrap:latest`;

    const powershellCommand = `docker run -d \`\n  --name krokbot-bootstrap \`\n  --restart on-failure \`\n  -v /var/run/docker.sock:/var/run/docker.sock \`\n  -v /opt/krokbot:/host_opt_krokbot \`\n  -e C2_URL="${c2Url}" \`\n  -e ENROLLMENT_TOKEN="${token}" \`\n  krokbot-bootstrap:latest`;

    const promptBashCommand = `read -p "Enter Enrollment Token: " TOKEN; docker run -d \\\n  --name krokbot-bootstrap \\\n  --restart on-failure \\\n  -v /var/run/docker.sock:/var/run/docker.sock \\\n  -v /opt/krokbot:/host_opt_krokbot \\\n  -e C2_URL="${c2Url}" \\\n  -e ENROLLMENT_TOKEN="$TOKEN" \\\n  krokbot-bootstrap:latest`;

    const promptPowershellCommand = `$Token = Read-Host -Prompt "Enter Enrollment Token"; docker run -d \`\n  --name krokbot-bootstrap \`\n  --restart on-failure \`\n  -v /var/run/docker.sock:/var/run/docker.sock \`\n  -v /opt/krokbot:/host_opt_krokbot \`\n  -e C2_URL="${c2Url}" \`\n  -e ENROLLMENT_TOKEN="$Token" \`\n  krokbot-bootstrap:latest`;

    return NextResponse.json({
      status: 'success',
      token,
      c2_url: c2Url,
      docker_command: dockerCommand,
      bash_command: bashCommand,
      powershell_command: powershellCommand,
      prompt_bash_command: promptBashCommand,
      prompt_powershell_command: promptPowershellCommand,
      expires_in_minutes: expiryMinutes
    });
  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: error.message }, { status: 500 });
  }
}
