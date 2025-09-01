export const runtime = "nodejs";
// Disable any ISR-style caching for this API route
export const revalidate = 0;

// Proxy for jobs list (GET) and job creation (POST)
export async function GET() {
  try {
    const apiBase = process.env.API_URL;
    if (!apiBase) {
      // Return empty list to avoid frontend 404/console spam
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    const resp = await fetch(`${apiBase}/api/jobs`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });

    if (!resp.ok) {
      const text = await resp.text();
      return new Response(text || "Upstream error", { status: resp.status });
    }

    const data = await resp.json();
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        // prevent browsers/frameworks from caching this proxy
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
      },
    });
  } catch (error) {
    return new Response(JSON.stringify({
      success: false,
      error: `Jobs proxy failed: ${error instanceof Error ? error.message : String(error)}`,
    }), { status: 502, headers: { "Content-Type": "application/json" } });
  }
}

export async function POST(req: Request) {
  try {
    const apiBase = process.env.API_URL;
    const body = await req.text();

    if (!apiBase) {
      // No backend configured: return a clear message but avoid network failures
      return new Response(JSON.stringify({
        success: false,
        error: "Backend not configured. Set API_URL or start backend on port 8000.",
      }), { status: 503, headers: { "Content-Type": "application/json" } });
    }

    const resp = await fetch(`${apiBase}/api/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body,
    });

    const text = await resp.text();
    // Pass through upstream status and body
    return new Response(text, {
      status: resp.status,
      headers: { "Content-Type": resp.headers.get("content-type") || "application/json" },
    });
  } catch (error) {
    return new Response(JSON.stringify({
      success: false,
      error: `Job creation proxy failed: ${error instanceof Error ? error.message : String(error)}`,
    }), { status: 502, headers: { "Content-Type": "application/json" } });
  }
}
