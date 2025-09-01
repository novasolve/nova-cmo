export const runtime = "nodejs";

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const { id } = params;
  if (!process.env.API_URL) {
    return new Response(JSON.stringify({ error: "Backend not configured" }), { status: 500 });
  }
  try {
    const upstream = await fetch(`${process.env.API_URL}/api/self-test/status/${encodeURIComponent(id)}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    const text = await upstream.text();
    return new Response(text, { status: upstream.status, headers: { "Content-Type": "application/json" } });
  } catch (e) {
    return new Response(JSON.stringify({ error: "Failed to fetch self-test status" }), { status: 500 });
  }
}
