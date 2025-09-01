export const runtime = "nodejs";

// Simple conversational endpoint for general chat (not job creation)
export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { threadId, text, options } = body;

    // Check if this is a conversational message (not a campaign goal)
    const isConversational = isConversationalMessage(text);

    if (isConversational) {
      // Generate a helpful response about the CMO Agent (no circular API calls)
      const response = generateConversationalResponse(text);

      return new Response(JSON.stringify({
        success: true,
        response,
        type: "conversation",
        threadId,
        timestamp: new Date().toISOString()
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    // Not conversational - redirect to job creation
    return new Response(JSON.stringify({
      success: false,
      error: "Not a conversational message - use /api/chat for job creation",
      redirect: "/api/chat"
    }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });

  } catch (error) {
    console.error("Conversation API error:", error);
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
    /active.*(days?|months?)/i
  ];

  // If it matches campaign patterns, it's probably a job goal
  if (campaignPatterns.some(pattern => pattern.test(text))) {
    return false;
  }

  // If it matches conversational patterns, it's a chat message
  return conversationalPatterns.some(pattern => pattern.test(text));
}

// Generate helpful responses about the CMO Agent
function generateConversationalResponse(text: string): string {
  const lowerText = text.toLowerCase();

  if (lowerText.includes("what's going on") || lowerText.includes("status") || lowerText.includes("update")) {
    return `👋 **Hey there!** I'm your CMO Agent assistant. Here's what's happening:

**Current Status**: Ready to help with outbound campaigns
**Capabilities**: GitHub lead discovery, email personalization, CRM sync
**Last Activity**: Check the Inspector panel → for live job details

**Quick Actions**:
• **🧪 Self‑Test** - Validate the pipeline with 5 Python maintainers
• **"Find 20 Python maintainers"** - Start a real campaign
• **"Brief"** - Generate campaign overview
• **"Preflight"** - Run simulations before execution

What would you like to work on? 🚀`;
  }

  if (lowerText.includes("how are") || lowerText.includes("hello") || lowerText.includes("hey")) {
    return `👋 **Hello!** I'm doing great and ready to help you with outbound campaigns!

I'm your CMO Agent - I can help you:
• **Find leads** from GitHub (Python, JS, React, Go developers)
• **Enrich profiles** with emails and activity data
• **Personalize outreach** with evidence-based messaging
• **Sync to CRM** (Attio, Linear) with full tracking

Try saying something like:
• *"Find 50 Python maintainers active in the last 90 days"*
• *"What can you do?"*
• *"Show me a brief for React developers"*

What campaign would you like to start? 🎯`;
  }

  if (lowerText.includes("what can") || lowerText.includes("capabilities") || lowerText.includes("help")) {
    return `🤖 **I'm your CMO Agent!** Here's what I can do:

**🔍 Lead Discovery**:
• Find developers by language (Python, JS, React, Go, etc.)
• Search GitHub for active maintainers and contributors
• Filter by activity, stars, commit frequency

**📧 Outreach Automation**:
• Extract emails from commits and profiles
• Generate personalized messages with evidence
• Manage sending with deliverability checks

**📊 Campaign Management**:
• Brief generation with ICP and risk analysis
• Preflight simulations with forecasts
• Budget controls and autonomy levels (L0-L4)

**🔗 CRM Integration**:
• Sync leads to Attio or Linear
• Track replies and engagement
• Issue creation for follow-ups

**Ready to start?** Try: *"Find 20 Python maintainers active 60 days"* 🚀`;
  }

  // Default helpful response
  return `💬 **I'm here to help!** I'm your CMO Agent for outbound campaigns.

**Not sure what to ask?** Try:
• *"What's going on?"* - Current status
• *"What can you do?"* - My capabilities
• *"Find 10 Python maintainers"* - Start a campaign
• *"🧪 Self‑Test"* - Quick validation run

**Or just tell me your goal** like:
• "I need React developers for our startup"
• "Find contributors to popular Python packages"
• "Generate a brief for JavaScript framework maintainers"

I'll help you discover leads, personalize outreach, and manage the entire campaign! 🎯`;
}
