export const runtime = "nodejs";

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const { id } = params;

  // Check if backend is available
  if (process.env.API_URL) {
    try {
      const upstream = await fetch(
        `${process.env.API_URL}/threads/${id}/events`,
        {
          headers: { Accept: "text/event-stream" },
        }
      );
      
      if (upstream.ok) {
        return new Response(upstream.body, {
          status: upstream.status,
          headers: {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
          },
        });
      }
    } catch (error) {
      console.warn("Backend SSE not available, using mock stream:", error);
    }
  }

  // Mock SSE stream for development
  const encoder = new TextEncoder();
  
  const stream = new ReadableStream({
    start(controller) {
      // Send initial connection message
      const welcomeEvent = {
        kind: "message",
        message: {
          id: crypto.randomUUID(),
          threadId: id,
          role: "assistant",
          createdAt: new Date().toISOString(),
          text: "Connected to mock SSE stream. Backend integration needed for live events."
        }
      };
      
      controller.enqueue(
        encoder.encode(`data: ${JSON.stringify(welcomeEvent)}\n\n`)
      );

      // Send periodic mock events
      const interval = setInterval(() => {
        const mockEvent = {
          kind: "event",
          event: {
            ts: new Date().toISOString(),
            node: ["enrich_github_user", "validate_email", "fetch_profile"][Math.floor(Math.random() * 3)],
            status: ["start", "ok", "retry"][Math.floor(Math.random() * 3)],
            latencyMs: Math.floor(Math.random() * 1000) + 100,
            costUSD: Math.random() * 0.01,
            msg: "Mock event for development"
          }
        };

        try {
          controller.enqueue(
            encoder.encode(`data: ${JSON.stringify(mockEvent)}\n\n`)
          );
        } catch (error) {
          clearInterval(interval);
          controller.close();
        }
      }, 5000); // Send event every 5 seconds

      // Clean up on close
      request.signal?.addEventListener('abort', () => {
        clearInterval(interval);
        controller.close();
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
    },
  });
}
