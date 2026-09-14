import { NextResponse } from 'next/server';
import fs from 'node:fs';
import path from 'node:path';
import { Readable } from 'node:stream';

interface RouteParams {
  params: Promise<{ filename: string }>;
}

export async function GET(req: Request, { params }: RouteParams) {
  try {
    const { filename } = await params;
    const safeFilename = path.basename(filename);

    const candidates = [
      path.join(process.cwd(), 'models', safeFilename),
      path.join(process.cwd(), '..', 'models', safeFilename)
    ];

    let foundPath: string | null = null;
    for (const c of candidates) {
      if (fs.existsSync(c)) {
        foundPath = c;
        break;
      }
    }

    if (!foundPath) {
      return NextResponse.json(
        { status: 'error', message: `Model file ${safeFilename} not found in depot` },
        { status: 404 }
      );
    }

    const stat = fs.statSync(foundPath);
    const fileSize = stat.size;
    const rangeHeader = req.headers.get('range');

    if (rangeHeader && rangeHeader.startsWith('bytes=')) {
      const parts = rangeHeader.replace(/bytes=/, '').split('-');
      const start = parseInt(parts[0], 10);
      const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;

      if (start >= fileSize || end >= fileSize) {
        return new NextResponse(null, {
          status: 416,
          headers: { 'Content-Range': `bytes */${fileSize}` }
        });
      }

      const chunkSize = (end - start) + 1;
      const fileStream = fs.createReadStream(foundPath, { start, end });
      const webStream = Readable.toWeb(fileStream) as ReadableStream;

      return new NextResponse(webStream, {
        status: 206,
        headers: {
          'Content-Range': `bytes ${start}-${end}/${fileSize}`,
          'Accept-Ranges': 'bytes',
          'Content-Length': chunkSize.toString(),
          'Content-Type': 'application/octet-stream',
          'Content-Disposition': `attachment; filename="${safeFilename}"`
        }
      });
    }

    const fileStream = fs.createReadStream(foundPath);
    const webStream = Readable.toWeb(fileStream) as ReadableStream;

    return new NextResponse(webStream, {
      status: 200,
      headers: {
        'Content-Length': fileSize.toString(),
        'Accept-Ranges': 'bytes',
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': `attachment; filename="${safeFilename}"`
      }
    });
  } catch (error: any) {
    return NextResponse.json({ status: 'error', message: error.message }, { status: 500 });
  }
}
