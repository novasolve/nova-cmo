// SSE health check endpoint for testing
export const runtime = "nodejs";

export async function GET(request: Request) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      console.log("SSE health check started");

      // Send initial message
      const startEvent = {
        timestamp: new Date().toISOString(),
        event: "health.start",
        data: { message: "SSE health check started" }
      };

      controller.enqueue(encoder.encode(`retry: 1500\n\n`));
      controller.enqueue(encoder.encode(`data: ${JSON.stringify(startEvent)}\n\n`));

      let counter = 0;

      // Send test events every 3 seconds
      const testInterval = setInterval(() => {
        try {
          counter++;
          const testEvent = {
            timestamp: new Date().toISOString(),
            event: "health.ping",
            data: {
              message: `Health check ping #${counter}`,
              counter
            }
          };

          controller.enqueue(
            encoder.encode(`data: ${JSON.stringify(testEvent)}\n\n`)
          );

          // Stop after 10 pings
          if (counter >= 10) {
            const endEvent = {
              timestamp: new Date().toISOString(),
              event: "health.complete",
              data: { message: "Health check completed successfully" }
            };

            controller.enqueue(
              encoder.encode(`data: ${JSON.stringify(endEvent)}\n\n`)
            );

            clearInterval(testInterval);
            controller.close();
          }
        } catch (error) {
          clearInterval(testInterval);
          controller.close();
        }
      }, 3000);

      // Clean up on client disconnect
      request.signal?.addEventListener('abort', () => {
        clearInterval(testInterval);
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
