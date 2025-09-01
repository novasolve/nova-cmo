export const runtime = "nodejs";

import { storeThreadJobMapping } from "@/lib/threadJobMapping";
import { autonomyToAutopilot, type AutonomyLevel } from "@/lib/autonomy";

// Detect if a message is conversational vs a campaign goal
function isConversationalMessage(text: string): boolean {
  const conversationalPatterns = [
    /^(hi|hello|hey|what's|how are|how's|what are|tell me|explain|why|can you|could you|would you)/i,
    /\?$/,  // Questions
    /^(thanks|thank you|ok|okay|cool|nice|great)/i,
    /(going on|what's up|status|update|progress)/i
  ];

  const campaignPatterns = [
    /find \d+/i,
    /(python|javascript|react|go|rust) (maintainers|developers|contributors)/i,
    /(export|csv|leads|campaign|sequence)/i,
    /active.*(days?|months?)/i,
    /(smoke test|self.test)/i
  ];

  // If it matches campaign patterns, it's probably a job goal
  if (campaignPatterns.some(pattern => pattern.test(text))) {
    return false;
  }

  // If it matches conversational patterns, it's a chat message
  return conversationalPatterns.some(pattern => pattern.test(text));
}
import { getThread, createThread, updateThread, generateThreadName } from "@/lib/threadStorage";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { threadId, text, message, options } = body;
    const messageText = text || message; // Support both 'text' and 'message' parameters

    // Validate required parameters
    if (!threadId || !messageText) {
      return new Response(JSON.stringify({
        success: false,
        error: "Missing required parameters: threadId and text/message",
        timestamp: new Date().toISOString()
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }

    // Check if this is a conversational message first
    if (isConversationalMessage(messageText)) {
      // Route to conversation endpoint
      const convResp = await fetch(`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:3000'}/api/chat-conversation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const convResult = await convResp.json();

      if (convResp.ok && convResult.success) {
        return new Response(JSON.stringify({
          success: true,
          message: convResult.response,
          type: "conversation",
          threadId,
          timestamp: new Date().toISOString()
        }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
    }

    // Ensure thread exists in storage
    let thread = getThread(threadId);
    if (!thread) {
      const threadName = generateThreadName(messageText);
      thread = createThread(threadId, threadName);
      console.log(`Created new thread: ${threadId} - ${threadName}`);
    }

    // Update thread with latest message
    updateThread(threadId, {
      lastActivity: messageText.length > 50 ? messageText.substring(0, 50) + "..." : messageText
    });

    // Normalize autonomy input to 'L0'..'L3' levels
    const normalizeAutonomy = (val: any): AutonomyLevel => {
      if (!val || typeof val !== 'string') return 'L0';
      const v = val.trim();
      if (/^L[0-3]$/i.test(v)) return v.toUpperCase() as AutonomyLevel;
      const map: Record<string, AutonomyLevel> = {
        minimal: 'L0',
        balanced: 'L1',
        high: 'L2',
        maximum: 'L3'
      };
      const key = v.toLowerCase();
      return map[key] || 'L0';
    };

    const autonomyLevel: AutonomyLevel = normalizeAutonomy(options?.autonomy);

    // Convert autonomy level to numeric autopilot for backend compatibility
    const autopilot = autonomyToAutopilot(autonomyLevel);

    // Create a job in the CMO Agent backend
    if (process.env.API_URL) {
      try {
        // Detect smoke test and, if so, build a pretty goal from YAML so chat matches CLI
        let finalGoal = messageText;
        const isSmokeTest = messageText.toLowerCase().includes('smoke test');
        if (isSmokeTest) {
          try {
            const url = `${process.env.API_URL}/static/config/smoke_prompt.yaml`;
            const resp = await fetch(url, { cache: "no-store" });
            if (resp.ok) {
              const textYaml = await resp.text();
              const { load } = await import('js-yaml');
              const doc: any = load(textYaml) || {};
              const params = doc?.params || {};
              const language = params.language || "Python";
              const stars = params.stars_range || "300..2000";
              const activity = Number(params.activity_days || 90);
              let pushedSince = doc?.pushed_since;
              if (!pushedSince) {
                const d = new Date();
                d.setDate(d.getDate() - activity);
                pushedSince = d.toISOString().slice(0, 10);
              }
              const tpl = (doc?.goal_template as string) ||
                "Find maintainers of {{language}} repos stars:{{stars_range}} pushed:>={{pushed_since}}; prioritize active {{activity_days}} days; export CSV.";
              finalGoal = tpl
                .replace(/{{language}}/g, language)
                .replace(/{{stars_range}}/g, stars)
                .replace(/{{pushed_since}}/g, pushedSince)
                .replace(/{{activity_days}}/g, String(activity))
                .replace(/\s+/g, ' ')
                .trim();
            }
          } catch {}
        }

        const jobPayload = {
          goal: finalGoal,
          dryRun: false, // Always run real execution - autonomy level controls behavior, not dry run
          // Route smoke-test to canonical YAML so backend runs identical config
          config_path: isSmokeTest ? "cmo_agent/config/smoke_prompt.yaml" : null,
          metadata: {
            threadId,
            autopilot_level: autopilot,
            autonomy_level: autonomyLevel,
            budget_per_day: options?.budget || 50,
            created_by: "chat_console",
            // Removed test_type to ensure all jobs run full pipeline consistently
            created_at: new Date().toISOString()
          }
        };

        console.log(`Creating job for thread: ${threadId}`);
        console.log(`Job payload:`, JSON.stringify(jobPayload, null, 2));

        const resp = await fetch(`${process.env.API_URL}/api/jobs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(jobPayload),
        });

        if (resp.ok) {
          const jobResult = await resp.json();

          // Store the mapping so the events endpoint knows which job to stream
          const actualJobId = jobResult.job_id || jobResult.id;
          console.log(`Job result:`, jobResult);
          console.log(`Storing thread mapping: ${threadId} -> ${actualJobId}`);
          storeThreadJobMapping(threadId, actualJobId);

          // Update thread with job status
          updateThread(threadId, {
            lastActivity: `🚀 Job started: ${jobResult.id}`
          });

          return new Response(JSON.stringify({
            success: true,
            jobId: actualJobId,
            threadId,
            message: `Job ${actualJobId} created and ${jobResult.status}. Streaming events...`,
            goal: finalGoal,
            timestamp: new Date().toISOString()
          }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        } else {
          const errorText = await resp.text();
          throw new Error(`Backend error: ${errorText}`);
        }
      } catch (error) {
        console.error("Backend connection failed:", error);

        // Return error response
        return new Response(JSON.stringify({
          success: false,
          error: `Backend unavailable: ${error instanceof Error ? error.message : String(error)}`,
          threadId,
          timestamp: new Date().toISOString()
        }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        });
      }
    }

    // No backend configured
    return new Response(JSON.stringify({
      success: false,
      error: "No backend configured. Set API_URL environment variable.",
      threadId,
      timestamp: new Date().toISOString()
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });

  } catch (error) {
    console.error("Chat API error:", error);
    return new Response(
      JSON.stringify({
        success: false,
        error: "Internal server error",
        timestamp: new Date().toISOString()
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}
