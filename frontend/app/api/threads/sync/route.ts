export const runtime = "nodejs";

import { createThread, updateThread, getThread } from "@/lib/threadStorage";

export async function POST(req: Request) {
  try {
    const apiBase = process.env.API_URL || 'http://localhost:8000';

    // Fetch all jobs from backend
    const jobsResp = await fetch(`${apiBase}/api/jobs`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      }
    });

    if (!jobsResp.ok) {
      throw new Error(`Jobs API failed: ${jobsResp.status}`);
    }

    const jobs = await jobsResp.json();
    let syncedCount = 0;

    // Sync each job to thread storage
    for (const job of jobs) {
      const threadId = job.metadata?.threadId;

      if (threadId) {
        // Check if thread already exists
        let thread = getThread(threadId);

        if (!thread) {
          // Create new thread from job
          const threadName = generateThreadNameFromJob(job);
          thread = createThread(threadId, threadName, 'real_campaign');
          syncedCount++;
        }

        // Update thread with latest job info
        updateThread(threadId, {
          currentJobId: job.job_id || job.id,
          lastActivity: job.goal,
          metadata: {
            autonomyLevel: job.metadata?.autonomy_level,
            budget: job.metadata?.budget_per_day,
            totalJobs: (thread.metadata?.totalJobs || 0) + (thread.currentJobId === job.job_id ? 0 : 1)
          }
        });
      }
    }

    return new Response(JSON.stringify({
      success: true,
      syncedCount,
      totalJobs: jobs.length,
      message: `Synced ${syncedCount} threads from backend jobs`,
      timestamp: new Date().toISOString()
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });

  } catch (error) {
    console.error("Thread sync error:", error);
    return new Response(JSON.stringify({
      success: false,
      error: `Sync failed: ${error instanceof Error ? error.message : String(error)}`,
      timestamp: new Date().toISOString()
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}

function generateThreadNameFromJob(job: any): string {
  const goal = job.goal || "";

  // Extract meaningful name from goal
  if (goal.toLowerCase().includes("python")) {
    const match = goal.match(/find (\d+)/i);
    return match ? `Python Leads (${match[1]})` : "Python Maintainers";
  } else if (goal.toLowerCase().includes("javascript") || goal.toLowerCase().includes("js")) {
    return "JavaScript Developers";
  } else if (goal.toLowerCase().includes("react")) {
    return "React Developers";
  } else if (goal.toLowerCase().includes("smoke test")) {
    return "Campaign";
  } else if (goal.toLowerCase().includes("test")) {
    return "🧪 Test Campaign";
  }

  // Fallback: use first few words
  const words = goal.split(' ').slice(0, 3);
  return words.map((word: string) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()).join(' ') || "Campaign";
}
