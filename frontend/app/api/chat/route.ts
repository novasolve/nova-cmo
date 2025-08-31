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
    
    // Convert autonomy level to numeric autopilot for backend compatibility
    const autopilot = options?.autonomy ? autonomyToAutopilot(options.autonomy) : 0;

    // Create a job in the CMO Agent backend
    if (process.env.API_URL) {
      try {
        // Detect if this is a smoke test
        const isSmokeTest = messageText.toLowerCase().includes('smoke test');
        
        const jobPayload = {
          goal: messageText,
          dryRun: autopilot === 0, // L0 = dry run, L1+ = real execution
          config_path: isSmokeTest ? "cmo_agent/config/smoke.yaml" : null,
          metadata: {
            threadId,
            autopilot_level: autopilot,
            autonomy_level: options?.autonomy || "L0",
            budget_per_day: options?.budget || 50,
            created_by: "chat_console",
            test_type: isSmokeTest ? "smoke_test" : "regular",
            created_at: new Date().toISOString()
          }
        };

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
