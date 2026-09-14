import { NextResponse } from 'next/server';
import fs from 'node:fs';
import path from 'node:path';
import { Readable } from 'node:stream';

export async function GET(req: Request) {
  try {
    const searchCandidates = [
      path.join(process.cwd(), 'images', 'krokbot_agent.tar.gz'),
      path.join(process.cwd(), 'images', 'krokbot_agent.tar'),
      path.join(process.cwd(), '..', 'images', 'krokbot_agent.tar.gz'),
      path.join(process.cwd(), '..', 'images', 'krokbot_agent.tar'),
    ];

    let foundPath: string | null = null;
    for (const cand of searchCandidates) {
      if (fs.existsSync(cand)) {
        foundPath = cand;
        break;
      }
    }

    if (!foundPath) {
      return NextResponse.json({
        status: 'warning',
        message: 'No pre-packaged image tarball found at images/krokbot_agent.tar.gz'
      }, { status: 200 });
    }

    const stat = fs.statSync(foundPath);
    const nodeStream = fs.createReadStream(foundPath);
    const webStream = Readable.toWeb(nodeStream) as ReadableStream;

    const isGzip = foundPath.endsWith('.gz');
    return new NextResponse(webStream, {
      status: 200,
      headers: {
        'Content-Type': isGzip ? 'application/gzip' : 'application/x-tar',
        'Content-Length': stat.size.toString(),
        'Content-Disposition': `attachment; filename="${path.basename(foundPath)}"`
      }
    });
  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: error.message }, { status: 500 });
  }
}
