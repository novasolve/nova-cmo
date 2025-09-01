// Direct SSE proxy to backend - no JSON parsing, no buffering
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
    const upstream = await fetch(`${process.env.API_URL}/api/jobs/${jobId}/events`, {
      headers: { Accept: "text/event-stream" },
      signal: request.signal,
    });

    // Always return the response, even if not 200
    // This ensures SSE connection stays open and handles 503 gracefully
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });

  } catch (error) {
    console.error(`SSE proxy error for job ${jobId}:`, error);

    // Return a minimal SSE stream with error info
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        const errorEvent = {
          job_id: jobId,
          timestamp: new Date().toISOString(),
          event: "job.proxy_error",
          data: { error: error instanceof Error ? error.message : String(error) }
        };

        controller.enqueue(encoder.encode(`retry: 1500\n\n`));
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(errorEvent)}\n\n`));

        // Keep connection alive
        const keepAlive = setInterval(() => {
          try {
            controller.enqueue(encoder.encode(`: keep-alive\n\n`));
          } catch {
            clearInterval(keepAlive);
          }
        }, 15000);

        request.signal?.addEventListener('abort', () => {
          clearInterval(keepAlive);
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
}
