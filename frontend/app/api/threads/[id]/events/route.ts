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
            // Find the most recent job that might match this thread
            const recentJob = jobs.find((job: any) => 
              job.goal && (
                job.goal.includes(threadId.slice(-8)) || // partial thread ID match
                job.created_at > new Date(Date.now() - 5 * 60 * 1000).toISOString() // within last 5 minutes
              )
            ) || jobs[0]; // fallback to latest job
            
            if (recentJob) {
              currentJobId = recentJob.job_id;
              console.log(`Auto-discovered job ID: ${currentJobId} for thread ${threadId}`);
            }
          }
        } catch (error) {
          console.warn(`Failed to auto-discover job ID: ${error}`);
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

        if (upstream.ok && upstream.body) {
          // Transform the backend events to frontend format
          const transformStream = new TransformStream({
            transform(chunk, controller) {
              const text = new TextDecoder().decode(chunk);
              const lines = text.split('\n');
              
              for (const line of lines) {
                if (line.startsWith('data: ')) {
                  try {
                    const eventData = JSON.parse(line.slice(6));
                    
                    // Transform to frontend event format
                    const frontendEvent = {
                      id: Date.now().toString(),
                      timestamp: new Date().toISOString(),
                      type: 'job_event',
                      node: extractNodeFromEvent(eventData),
                      status: extractStatusFromEvent(eventData),
                      message: eventData.message || eventData.event || 'Processing...',
                      data: eventData
                    };
                    
                    const transformedLine = `data: ${JSON.stringify(frontendEvent)}\n\n`;
                    controller.enqueue(new TextEncoder().encode(transformedLine));
                  } catch (error) {
                    // Pass through malformed events as-is
                    controller.enqueue(chunk);
                  }
                } else {
                  // Pass through non-data lines (like event: types)
                  controller.enqueue(chunk);
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
          }
        } catch (error) {
          console.warn(`Error connecting to job events: ${error}`);
        }
      } else {
        console.log(`No job ID found for thread ${threadId}`);
      }
    } catch (error) {
      console.warn("Backend SSE not available:", error);
    }
  }

  // Fallback: return mock stream if no job or backend unavailable
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      // Send a connection status message
      const statusEvent = {
        id: Date.now().toString(),
        timestamp: new Date().toISOString(),
        type: 'connection',
        node: 'system',
        status: 'info',
        message: 'Connected to event stream (fallback mode)',
        data: { threadId, fallback: true }
      };
      
      controller.enqueue(encoder.encode(`data: ${JSON.stringify(statusEvent)}\n\n`));
      
      // Send periodic status updates
      const statusInterval = setInterval(() => {
        try {
          const updateEvent = {
            id: Date.now().toString(),
            timestamp: new Date().toISOString(),
            type: 'status',
            node: 'system',
            status: 'info',
            message: 'Checking for updates...',
            data: { threadId, mode: 'polling' }
          };
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(updateEvent)}\n\n`));
        } catch {
          clearInterval(statusInterval);
        }
      }, 8000); // Every 8 seconds
      
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
        clearInterval(statusInterval);
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