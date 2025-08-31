export const runtime = "nodejs";

import { getJobIdForThread } from "@/lib/threadJobMapping";

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const { id: threadId } = params;

  // Check if backend is available
  if (!process.env.API_URL) {
    return new Response("Backend not available", { status: 503 });
  }

  try {
    // Get the current job ID for this thread
    let currentJobId = getJobIdForThread(threadId);
    console.log(`Thread ${threadId} mapped to job: ${currentJobId || 'none'}`);
    
    // If no mapping exists, try to find the latest job for this thread
    if (!currentJobId) {
      try {
        const jobsResp = await fetch(`${process.env.API_URL}/api/jobs`, {
          method: 'GET',
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
          }
        });
        
        if (jobsResp.ok) {
          const jobs = await jobsResp.json();
          
          // Try multiple strategies to find the right job
          let threadJob = null;
          
          // Strategy 1: Exact threadId match in metadata
          threadJob = jobs.find((job: any) => job.metadata?.threadId === threadId);
          
          // Strategy 2: Recent job created in last 5 minutes (fallback)
          if (!threadJob) {
            const recentJobs = jobs.filter((job: any) => {
              const createdAt = new Date(job.created_at || job.metadata?.created_at);
              const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
              return createdAt > fiveMinutesAgo;
            }).sort((a: any, b: any) => {
              const aTime = new Date(a.created_at || a.metadata?.created_at).getTime();
              const bTime = new Date(b.created_at || b.metadata?.created_at).getTime();
              return bTime - aTime; // Most recent first
            });
            
            threadJob = recentJobs[0];
          }
          
          if (threadJob) {
            currentJobId = threadJob.job_id || threadJob.id; // Handle both field names
            // Store the mapping for future requests
            if (currentJobId) {
              const { storeThreadJobMapping } = await import("@/lib/threadJobMapping");
              storeThreadJobMapping(threadId, currentJobId);
            }
          }
        } else {
          console.warn(`Jobs API failed: ${jobsResp.status} ${jobsResp.statusText}`);
          const errorText = await jobsResp.text();
          console.warn(`Error response: ${errorText}`);
        }
      } catch (error) {
        console.warn("Could not fetch jobs list:", error);
      }
    }
    
    // If we have a job ID, stream its events
    if (currentJobId) {
      try {
        console.log(`Attempting to stream from job ${currentJobId}`);
        // Stream from the real job events endpoint
        const upstream = await fetch(
          `${process.env.API_URL}/api/jobs/${currentJobId}/events`,
          {
            headers: { Accept: "text/event-stream" },
            signal: request.signal,
          }
        );
        
        console.log(`Job events response: ${upstream.status} ${upstream.statusText}`);
        
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
        } else {
          console.warn(`Job events endpoint failed: ${upstream.status} ${upstream.statusText}`);
          
          // If events endpoint fails (503), create a polling fallback
          if (upstream.status === 503) {
            return createPollingFallback(currentJobId, threadId, request);
          }
          
          return new Response(`Job events not available: ${upstream.statusText}`, { status: upstream.status });
        }
      } catch (error) {
        console.warn(`Error connecting to job events: ${error}`);
        return new Response("Error connecting to job events", { status: 500 });
      }
    } else {
      // Don't log repeatedly for threads without jobs - this is normal
      return new Response("No active job for this thread", { status: 404 });
    }
  } catch (error) {
    console.error("Backend SSE error:", error);
    return new Response("Internal server error", { status: 500 });
  }
}

// Polling fallback when SSE events are unavailable (503 error)
function createPollingFallback(jobId: string, threadId: string, request: Request) {
  const encoder = new TextEncoder();
  
  const stream = new ReadableStream({
    start(controller) {
      console.log(`Creating polling fallback for job ${jobId}`);
      
      // Send initial message
      const initialEvent = {
        kind: "message",
        message: {
          id: crypto.randomUUID(),
          threadId,
          role: "system",
          createdAt: new Date().toISOString(),
          text: `⚡ **Live Events Unavailable** - Using polling fallback for job ${jobId}\n\nThe job is running, but live events aren't available. Check the backend logs for progress.`
        }
      };
      
      controller.enqueue(
        encoder.encode(`data: ${JSON.stringify(initialEvent)}\n\n`)
      );

      // Poll job status every 10 seconds
      const pollInterval = setInterval(async () => {
        try {
          const statusResp = await fetch(`${process.env.API_URL}/api/jobs/${jobId}`);
          if (statusResp.ok) {
            const jobStatus = await statusResp.json();
            
            const statusEvent = {
              kind: "event",
              event: {
                ts: new Date().toISOString(),
                node: "job_status_poll",
                status: jobStatus.status === "completed" ? "ok" : "start",
                msg: `Job ${jobId}: ${jobStatus.status}${jobStatus.progress ? ` - ${jobStatus.progress}` : ""}`
              }
            };
            
            controller.enqueue(
              encoder.encode(`data: ${JSON.stringify(statusEvent)}\n\n`)
            );
            
            // If job completed, send final message and close
            if (jobStatus.status === "completed" || jobStatus.status === "failed") {
              const finalEvent = {
                kind: "message",
                message: {
                  id: `completion-${Date.now()}`,
                  threadId,
                  role: "assistant",
                  createdAt: new Date().toISOString(),
                  text: `✅ **Job ${jobId} ${jobStatus.status}**\n\nCheck your exports folder for results!`
                }
              };
              
              controller.enqueue(
                encoder.encode(`data: ${JSON.stringify(finalEvent)}\n\n`)
              );
              
              clearInterval(pollInterval);
              controller.close();
            }
          }
        } catch (error) {
          console.warn("Polling failed:", error);
        }
      }, 10000);

      // Clean up on client disconnect
      request.signal?.addEventListener('abort', () => {
        clearInterval(pollInterval);
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