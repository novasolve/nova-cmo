export const runtime = "nodejs";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { threadId, actionId, payload } = body;

    // For now, return a mock response since we don't have the backend yet
    // In production, this would proxy to your FastAPI backend
    const mockResponse = {
      message: "Action executed",
      threadId,
      actionId,
      payload,
      timestamp: new Date().toISOString()
    };

    // Simulate API call to backend
    if (process.env.API_URL) {
      try {
        const resp = await fetch(`${process.env.API_URL}/actions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        
        if (resp.ok) {
          return new Response(await resp.text(), { status: resp.status });
        }
      } catch (error) {
        console.warn("Backend not available, using mock response:", error);
      }
    }

    return new Response(JSON.stringify(mockResponse), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Actions API error:", error);
    return new Response(
      JSON.stringify({ error: "Internal server error" }),
      { 
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}
