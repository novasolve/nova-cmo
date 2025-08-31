export const runtime = "nodejs";

import { getJobIdForThread } from "@/lib/threadJobMapping";

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const { id: threadId } = params;

  // Check if backend is available
  if (process.env.API_URL) {
    try {
      // Get the current job ID for this thread
      let currentJobId = getJobIdForThread(threadId);
      
      // If no mapping exists, try to find the latest job for this thread
      if (!currentJobId) {
        try {
          const jobsResp = await fetch(`${process.env.API_URL}/api/jobs`);
          if (jobsResp.ok) {
            const jobs = await jobsResp.json();
            // Find the most recent job for this thread
            const threadJob = jobs.find((job: any) => 
              job.metadata?.threadId === threadId || 
              job.goal?.includes(threadId) ||
              job.id === threadId
            );
            if (threadJob) {
              currentJobId = threadJob.id;
              // Store the mapping for future requests
              const { storeThreadJobMapping } = await import("@/lib/threadJobMapping");
              storeThreadJobMapping(threadId, currentJobId);
            }
          }
        } catch (error) {
          console.warn("Could not fetch jobs list:", error);
        }
      }
      
      if (currentJobId) {
        // Stream from the real job events endpoint
        const upstream = await fetch(
          `${process.env.API_URL}/api/jobs/${currentJobId}/events`,
          {
            headers: { Accept: "text/event-stream" },
            signal: request.signal,
          }
        );
        
        if (upstream.ok) {
          // Transform job events to chat events
          const transformStream = new TransformStream({
            transform(chunk, controller) {
              const decoder = new TextDecoder();
              const text = decoder.decode(chunk);
              
              // Parse SSE format: "data: {...}\n\n"
              const lines = text.split('\n');
              for (const line of lines) {
                if (line.startsWith('data: ')) {
                  try {
                    const jobEvent = JSON.parse(line.slice(6));
                    
                    // Transform job event to chat event format
                    const chatEvent = {
                      kind: "event",
                      event: {
                        ts: jobEvent.timestamp,
                        node: extractNodeFromEvent(jobEvent),
                        status: extractStatusFromEvent(jobEvent),
                        latencyMs: jobEvent.data?.latency_ms,
                        costUSD: jobEvent.data?.cost_usd,
                        msg: jobEvent.data?.message || jobEvent.event
                      }
                    };
                    
                    const transformed = `data: ${JSON.stringify(chatEvent)}\n\n`;
                    controller.enqueue(new TextEncoder().encode(transformed));
                  } catch (error) {
                    // Pass through malformed events
                    controller.enqueue(chunk);
                  }
                } else if (line.trim()) {
                  // Pass through non-data lines (comments, etc.)
                  controller.enqueue(new TextEncoder().encode(line + '\n'));
                }
              }
            }
          });
          
          return new Response(upstream.body?.pipeThrough(transformStream), {
            status: upstream.status,
            headers: {
              "Content-Type": "text/event-stream",
              "Cache-Control": "no-cache",
              "Connection": "keep-alive",
            },
          });
        }
      }
    } catch (error) {
      console.warn("Backend SSE not available:", error);
    }
  }

  // Fallback: return empty stream if no job or backend unavailable
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      const welcomeEvent = {
        kind: "message",
        message: {
          id: crypto.randomUUID(),
          threadId,
          role: "assistant",
          createdAt: new Date().toISOString(),
          text: "No active job for this thread. Send a message to start a campaign."
        }
      };
      
      controller.enqueue(
        encoder.encode(`data: ${JSON.stringify(welcomeEvent)}\n\n`)
      );
      
      // Keep connection alive
      const keepAlive = setInterval(() => {
        try {
          controller.enqueue(encoder.encode(`: keep-alive\n\n`));
        } catch {
          clearInterval(keepAlive);
        }
      }, 30000);

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

// Helper functions to extract info from job events
function extractNodeFromEvent(jobEvent: any): string {
  if (jobEvent.data?.node) return jobEvent.data.node;
  if (jobEvent.data?.current_tool) return jobEvent.data.current_tool;
  if (jobEvent.event?.includes('github')) return 'github_enrichment';
  if (jobEvent.event?.includes('email')) return 'email_processing';
  if (jobEvent.event?.includes('crm')) return 'crm_sync';
  return jobEvent.event || 'unknown';
}

function extractStatusFromEvent(jobEvent: any): string {
  if (jobEvent.event?.includes('start') || jobEvent.event?.includes('begin')) return 'start';
  if (jobEvent.event?.includes('completed') || jobEvent.event?.includes('finished')) return 'ok';
  if (jobEvent.event?.includes('error') || jobEvent.event?.includes('failed')) return 'error';
  if (jobEvent.event?.includes('retry')) return 'retry';
  return 'ok';
}

// Helper functions to extract info from job events
