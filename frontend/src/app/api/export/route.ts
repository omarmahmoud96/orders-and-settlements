import { type NextRequest, NextResponse } from 'next/server';

import { apiFetch, queryString } from '@/lib/api';

/**
 * Proxy the CSV export. The response body is piped straight through rather
 * than buffered, so a large export does not have to fit in this process's
 * memory.
 */
export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;

  const upstream = await apiFetch(
    `/api/orders/export/${queryString({
      status: params.getAll('status'),
      from: params.get('from'),
      to: params.get('to'),
    })}`
  );

  if (!upstream.ok || !upstream.body) {
    return NextResponse.json(
      {
        error: {
          code: 'EXPORT_FAILED',
          message: 'The export could not be generated.',
        },
      },
      { status: upstream.status || 502 }
    );
  }

  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition':
        upstream.headers.get('Content-Disposition') ??
        'attachment; filename="orders.csv"',
      'Cache-Control': 'no-store',
    },
  });
}
