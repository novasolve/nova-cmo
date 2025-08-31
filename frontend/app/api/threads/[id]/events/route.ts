export const runtime = "nodejs";

import { getJobIdForThread } from "@/lib/threadJobMapping";

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const { id: threadId } = params;
  // Optional explicit jobId from query (preferred if provided)
  let urlJobId: string | null = null;
  try {
    const { searchParams } = new URL(request.url);
    urlJobId = searchParams.get("jobId");
  } catch {}

  // Check if backend is available
  if (!process.env.API_URL) {
    console.error(`[ThreadsEventsAPI] Missing API_URL`, { threadId, requestUrl: request.url });
    return new Response("Backend not available", { status: 503 });
  }

  try {
    // Get the current job ID for this thread
    let currentJobId = urlJobId || getJobIdForThread(threadId);
    console.log(`[ThreadsEventsAPI] thread mapped`, { threadId, jobId: currentJobId || 'none', requestUrl: request.url });

    // If no mapping exists, try to find the latest job for this thread
    if (!currentJobId) {
      try {
        const jobsUrl = `${process.env.API_URL}/api/jobs`;
        console.log(`[ThreadsEventsAPI] fetching jobs`, { url: jobsUrl, threadId });
        const jobsResp = await fetch(jobsUrl, {
          method: 'GET',
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
          }
        });

        if (jobsResp.ok) {
          const jobs = await jobsResp.json();
          console.log(`[ThreadsEventsAPI] jobs fetched`, { count: jobs.length, threadId });

          // Debug: Show all job thread IDs
          const jobThreadIds = jobs.map((job: any) => ({
            id: job.job_id || job.id,
            threadId: job.metadata?.threadId,
            goal: job.goal?.substring(0, 50)
          }));
          console.log(`Available job thread IDs:`, jobThreadIds);

          // Try multiple strategies to find the right job
          let threadJob = null;

          // Strategy 1: Exact threadId match in metadata
          threadJob = jobs.find((job: any) => job.metadata?.threadId === threadId);
          console.log(`Strategy 1 (exact match) result:`, threadJob ? `found job ${threadJob.job_id || threadJob.id}` : 'not found');

          // Strategy 2: Recent job created in last 5 minutes (fallback)
          if (!threadJob) {
            console.log(`Strategy 2: Looking for recent jobs as fallback...`);
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
          console.warn(`[ThreadsEventsAPI] jobs fetch failed`, { status: jobsResp.status, statusText: jobsResp.statusText });
          const errorText = await jobsResp.text();
          console.warn(`[ThreadsEventsAPI] jobs error body`, { body: errorText?.slice(0, 500) });
        }
      } catch (error) {
        console.warn(`[ThreadsEventsAPI] jobs fetch threw`, { threadId, error });
      }
    }

    // If we have a job ID, stream its events
    if (currentJobId) {
      try {
        console.log(`Attempting to stream from job ${currentJobId}`);
        // Stream from the real job events endpoint
        // Use a dedicated AbortController so client disconnect doesn't abort upstream prematurely
        const upstreamController = new AbortController();
        const upstreamUrl = `${process.env.API_URL}/api/jobs/${currentJobId}/events`;
        console.log(`[ThreadsEventsAPI] fetching upstream events`, { upstreamUrl });
        const upstream = await fetch(
          upstreamUrl,
          {
            headers: { Accept: "text/event-stream" },
            signal: upstreamController.signal,
          }
        );

        console.log(`[ThreadsEventsAPI] upstream response`, { status: upstream.status, statusText: upstream.statusText });

        if (upstream.ok) {
          // Streaming-safe SSE transform: buffer and split on event boundaries ("\n\n")
          const decoder = new TextDecoder();
          const encoder = new TextEncoder();
          let buffer = "";

          const transformStream = new TransformStream({
            transform(chunk, controller) {
              buffer += decoder.decode(chunk, { stream: true });

              // Process complete SSE event blocks separated by blank line
              let sepIndex = buffer.indexOf("\n\n");
              while (sepIndex !== -1) {
                const block = buffer.slice(0, sepIndex); // without trailing blank line
                buffer = buffer.slice(sepIndex + 2);

                // Parse SSE fields in the block
                const lines = block.split('\n');
                const fields: Record<string, string[]> = {};
                for (const raw of lines) {
                  if (!raw) continue; // preserve empty-only as delimiter; already handled
                  // Comments start with ':' – forward as-is
                  if (raw.startsWith(':')) {
                    controller.enqueue(encoder.encode(raw + '\n\n'));
                    continue;
                  }
                  const idx = raw.indexOf(':');
                  const field = idx === -1 ? raw : raw.slice(0, idx);
                  let value = idx === -1 ? '' : raw.slice(idx + 1);
                  if (value.startsWith(' ')) value = value.slice(1);
                  (fields[field] ||= []).push(value);
                }

                // If we have data, attempt JSON transform; otherwise, pass through
                if (fields['data'] && fields['data'].length > 0) {
                  const dataStr = fields['data'].join('\n');
                  try {
                    const jobEvent = JSON.parse(dataStr);
                    const chatEvent = {
                      kind: 'event',
                      event: {
                        ts: jobEvent.timestamp,
                        node: extractNodeFromEvent(jobEvent),
                        status: extractStatusFromEvent(jobEvent),
                        latencyMs: jobEvent.data?.latency_ms,
                        costUSD: jobEvent.data?.cost_usd,
                        msg: jobEvent.data?.message || jobEvent.event
                      }
                    };
                    controller.enqueue(encoder.encode(`data: ${JSON.stringify(chatEvent)}\n\n`));
                  } catch (error) {
                    console.warn('[ThreadsEventsAPI] transform parse failed, passing through', { error });
                    controller.enqueue(encoder.encode(block + '\n\n'));
                  }
                } else if (fields['retry'] || fields['event'] || fields['id']) {
                  // Pass through control fields unchanged
                  controller.enqueue(encoder.encode(block + '\n\n'));
                } else {
                  // Unknown block – preserve
                  controller.enqueue(encoder.encode(block + '\n\n'));
                }

                sepIndex = buffer.indexOf("\n\n");
              }
            },
            flush(controller) {
              if (buffer.length > 0) {
                controller.enqueue(encoder.encode(buffer));
              }
            }
          });

          // When client disconnects, cancel upstream fetch
          request.signal?.addEventListener('abort', () => {
            try { upstreamController.abort(); } catch {}
          });

          return new Response(upstream.body?.pipeThrough(transformStream), {
            status: upstream.status,
            headers: {
              "Content-Type": "text/event-stream",
              "Cache-Control": "no-cache",
              "Connection": "keep-alive",
              "X-Accel-Buffering": "no",
            },
          });
        } else {
          console.warn(`[ThreadsEventsAPI] upstream events failed`, { status: upstream.status, statusText: upstream.statusText, upstreamUrl });

          // If events endpoint fails (503), create a polling fallback
          if (upstream.status === 503) {
            return createPollingFallback(currentJobId, threadId, request);
          }

          return new Response(`Job events not available: ${upstream.statusText}`, { status: upstream.status });
        }
      } catch (error) {
        console.warn(`[ThreadsEventsAPI] error connecting to upstream`, { threadId, jobId: currentJobId, error });
        return new Response("Error connecting to job events", { status: 500 });
      }
    } else {
      // No active job - return a proper SSE response that won't trigger reconnects
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          // Send a single event indicating no job
          const noJobEvent = {
            kind: "status",
            status: {
              message: "No active job for this thread",
              threadId: threadId,
              timestamp: new Date().toISOString()
            }
          };

          controller.enqueue(encoder.encode(`retry: 30000\n\n`)); // Long retry to prevent hammering
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(noJobEvent)}\n\n`));

          // Close the stream after sending the status
          setTimeout(() => {
            controller.close();
          }, 100);
        },
      });

      return new Response(stream, {
        status: 200, // Return 200 to prevent EventSource retries
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          "Connection": "keep-alive",
        },
      });
    }
  } catch (error) {
    console.error(`[ThreadsEventsAPI] unhandled error`, { threadId, urlJobId, error });
    return new Response("Internal server error", { status: 500 });
  }
}

// Polling fallback when SSE events are unavailable (503 error)
function createPollingFallback(jobId: string, threadId: string, request: Request) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      console.log(`[ThreadsEventsAPI] creating polling fallback`, { threadId, jobId });

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
  // Treat stream end or explicit completion as a completion node so UI can finalize
  if (jobEvent.event?.includes('stream_end') || jobEvent.event?.includes('completed')) return 'completion';
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
