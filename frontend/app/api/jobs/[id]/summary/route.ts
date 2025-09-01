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
    const upstream = await fetch(`${process.env.API_URL}/api/jobs/${jobId}/summary`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });

    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("Content-Type") || "application/json" },
    });
  } catch (error) {
    console.error(`Summary proxy error for job ${jobId}:`, error);
    return new Response(JSON.stringify({ error: "Summary unavailable" }), { status: 502 });
  }
}
