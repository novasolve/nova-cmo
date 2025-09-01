export const runtime = "nodejs";

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(() => ({}));
    const mode = typeof body?.mode === "string" ? body.mode : "mock";

    if (!process.env.API_URL) {
      return new Response(JSON.stringify({ error: "Backend not configured" }), { status: 500 });
    }

    const upstream = await fetch(`${process.env.API_URL}/api/self-test/start?mode=${encodeURIComponent(mode)}`, {
      method: "POST",
      headers: { Accept: "application/json" },
    });

    const text = await upstream.text();
    return new Response(text, { status: upstream.status, headers: { "Content-Type": "application/json" } });
  } catch (e) {
    return new Response(JSON.stringify({ error: "Failed to start self-test" }), { status: 500 });
  }
}
