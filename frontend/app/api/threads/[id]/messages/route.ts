export const runtime = "nodejs";

import { getThread } from "@/lib/threadStorage";

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const { id: threadId } = params;

  try {
    // Get thread from storage
    const thread = getThread(threadId);

    // If thread exists, return its messages; otherwise return empty array
    const messages = thread?.messages || [];

    return new Response(JSON.stringify(messages), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });

  } catch (error) {
    console.error("Thread messages API error:", error);
    // Return empty array instead of 404 to prevent console spam
    return new Response(JSON.stringify([]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }
}
