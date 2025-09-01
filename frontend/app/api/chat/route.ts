export const runtime = "nodejs";
// prevent any ISR-style caching on this API route
export const revalidate = 0;

import { storeThreadJobMapping } from "@/lib/threadJobMapping";
import { autonomyToAutopilot, type AutonomyLevel } from "@/lib/autonomy";

// Detect if a message is conversational vs a campaign goal using LLM
async function isConversationalMessage(text: string): Promise<boolean> {
  // Quick fallback for obvious cases to avoid LLM calls
  const quickCampaignPatterns = [
    /find \d+/i,
    /(python|javascript|react|go|rust) (maintainers|developers|contributors)/i,
    /(export|csv|leads|campaign|sequence)/i,
  ];
  
  if (quickCampaignPatterns.some(pattern => pattern.test(text))) {
    return false;
  }
  
  try {
    // Use OpenAI to classify the message
    const response = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages: [
          {
            role: 'system',
            content: `You are a classifier that determines if a user message is:
1. CONVERSATIONAL: General chat, questions about the system, greetings, thanks, status inquiries
2. CAMPAIGN: Instructions to find leads, create campaigns, export data, or perform specific business tasks

Respond with exactly "CONVERSATIONAL" or "CAMPAIGN" - nothing else.`
          },
          {
            role: 'user',
            content: text
          }
        ],
        max_tokens: 10,
        temperature: 0,
      }),
    });

    if (!response.ok) {
      // Fallback to simple heuristics if LLM fails
      return text.includes('?') || /^(hi|hello|hey|what's|how|tell me|explain)/i.test(text);
    }

    const result = await response.json();
    const classification = result.choices?.[0]?.message?.content?.trim().toUpperCase();
    
    return classification === 'CONVERSATIONAL';
  } catch (error) {
    console.error('LLM classification failed, using fallback:', error);
    // Fallback to simple heuristics
    return text.includes('?') || /^(hi|hello|hey|what's|how|tell me|explain)/i.test(text);
  }
}
import { getThread, createThread, updateThread, generateThreadName } from "@/lib/threadStorage";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const threadId = url.searchParams.get("threadId");

  const headers = {
    "Content-Type": "application/json",
    // ensure browsers & frameworks don't cache this endpoint
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
  } as const;

  if (!threadId) {
    // Success with empty history stops SWR/React-Query from retrying.
    return new Response(JSON.stringify({
      success: true,
      threadId: null,
      messages: [],
    }), { status: 200, headers });
  }

  const thread = getThread(threadId);
  const messages = (thread as any)?.messages ?? [];

  return new Response(JSON.stringify({
    success: true,
    threadId,
    messages,
    lastActivity: thread?.lastActivity ?? null,
    updatedAt: (thread as any)?.updatedAt ?? null,
  }), { status: 200, headers });
}

export async function POST(req: Request) {
  try {
    const url = new URL(req.url); // used to construct absolute URLs for internal fetches
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
    if (await isConversationalMessage(messageText)) {
      // Route to conversation endpoint
      const convResp = await fetch(`${url.origin}/api/chat-conversation`, {
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

    // Normalize autonomy input to L0-L3 levels expected by AUTONOMY map
    const normalizeAutonomy = (val: any): AutonomyLevel => {
      if (!val || typeof val !== 'string') return 'L0';
      const v = val.trim().toUpperCase();
      if (/^L[0-3]$/.test(v)) {
        return v as AutonomyLevel;
      }
      // Convert old names to new format
      if (v === 'MINIMAL') return 'L0';
      if (v === 'BALANCED') return 'L1';
      if (v === 'HIGH') return 'L2';
      if (v === 'MAXIMUM') return 'L3';
      return 'L0';
    };

    const autonomyLevel: AutonomyLevel = normalizeAutonomy(options?.autonomy);

    // Convert autonomy level to numeric autopilot for backend compatibility
    const autopilot = autonomyToAutopilot(autonomyLevel);

    // Always go through proxy; it handles API_URL presence and returns helpful errors
    const jobPayload = {
      goal: messageText,
      dryRun: false, // Always real execution
      config_path: null,
      metadata: {
        threadId,
        autopilot_level: autopilot,
        autonomy_level: autonomyLevel,
        budget_per_day: options?.budget || 50,
        created_by: "chat_console",
        created_at: new Date().toISOString()
      }
    };

    console.log(`Creating job for thread: ${threadId}`);
    // Redact sensitive information from job payload before logging
    const redactedPayload = {
      ...jobPayload,
      goal: jobPayload.goal.length > 50 ? jobPayload.goal.substring(0, 50) + "..." : jobPayload.goal,
      metadata: {
        ...jobPayload.metadata,
        threadId: "[REDACTED]", // Don't log thread IDs
        created_by: "[REDACTED]", // Don't log user info
      }
    };
    console.log(`Job payload:`, JSON.stringify(redactedPayload, null, 2));

    const resp = await fetch(`${url.origin}/api/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(jobPayload),
    });

    const textResp = await resp.text();

    if (resp.ok) {
      const jobResult = JSON.parse(textResp || '{}');

      // Store the mapping so the events endpoint knows which job to stream
      const actualJobId = jobResult.job_id || jobResult.id;
      console.log(`Job result:`, jobResult);
      console.log(`Storing thread mapping: ${threadId} -> ${actualJobId}`);
      if (actualJobId) {
        storeThreadJobMapping(threadId, actualJobId);
      }

      return new Response(JSON.stringify({
        success: true,
        jobId: actualJobId,
        threadId,
        message: jobResult.status ? `Job ${actualJobId} ${jobResult.status}. Streaming events...` : 'Job created.',
        timestamp: new Date().toISOString()
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    // Not OK - bubble up a helpful error but avoid scary network text
    return new Response(JSON.stringify({
      success: false,
      error: jobErrorMessage(textResp),
      threadId,
      timestamp: new Date().toISOString()
    }), { status: resp.status || 502, headers: { "Content-Type": "application/json" } });

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

function jobErrorMessage(text: string) {
  try {
    const obj = JSON.parse(text);
    if (obj?.error) return obj.error;
  } catch {}
  if (!process.env.API_URL) {
    return "Backend not configured. Start backend or set API_URL in .env.local.";
  }
  return text || "Backend error";
}
