export const runtime = "nodejs";

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const { id } = params;

  try {
    // Try to fetch from backend if available
    if (process.env.API_URL) {
      try {
        const response = await fetch(`${process.env.API_URL}/threads/${id}/messages`);

        if (response.ok) {
          const messages = await response.json();
          return new Response(JSON.stringify(messages), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
      } catch (error) {
        console.warn("Backend not available for thread messages:", error);
      }
    }

    // Return empty array if no backend or thread doesn't exist
    // This allows the frontend to show the welcome message
    return new Response(JSON.stringify([]), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });

  } catch (error) {
    console.error("Thread messages API error:", error);
    return new Response(
      JSON.stringify({ error: "Internal server error" }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}
