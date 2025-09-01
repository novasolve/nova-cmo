export const runtime = "nodejs";

export async function GET(
  request: Request,
  { params }: { params: { id: string; name: string } }
) {
  const { id: jobId, name } = params;

  if (!process.env.API_URL) {
    return new Response("Backend not configured", { status: 500 });
  }

  try {
    const upstream = await fetch(`${process.env.API_URL}/api/jobs/${jobId}/artifacts/${encodeURIComponent(name)}`,
      { signal: request.signal }
    );
    // Proxy status and headers; stream body
    const headers = new Headers(upstream.headers);
    return new Response(upstream.body, {
      status: upstream.status,
      headers,
    });
  } catch (error) {
    return new Response("Failed to fetch artifact", { status: 502 });
  }
}


