export const runtime = "nodejs";

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const { id: jobId } = params;

  if (!process.env.API_URL) {
    return new Response("Backend not configured", { status: 500 });
  }

  try {
    const upstream = await fetch(`${process.env.API_URL}/api/jobs/${jobId}/artifacts`, {
      headers: { Accept: "application/json" },
      signal: request.signal,
      cache: "no-store",
    });
    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: String(error) }), {
      status: 502,
      headers: { "Content-Type": "application/json" },
    });
  }
}


