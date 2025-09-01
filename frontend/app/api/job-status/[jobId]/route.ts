export const runtime = "nodejs";

export async function GET(
  request: Request,
  { params }: { params: { jobId: string } }
) {
  const { jobId } = params;

  try {
    if (process.env.API_URL) {
      // Try to get job status directly from backend
      const response = await fetch(`${process.env.API_URL}/api/jobs/${jobId}`, {
        headers: { Accept: "application/json" },
      });

      if (response.ok) {
        const jobData = await response.json();
        return new Response(JSON.stringify(jobData), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      } else {
        console.warn(`Job status failed: ${response.status} ${response.statusText}`);
      }
    }

    // Fallback response
    return new Response(JSON.stringify({
      job_id: jobId,
      status: "unknown",
      message: "Job status unavailable",
      timestamp: new Date().toISOString()
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });

  } catch (error) {
    console.error("Job status API error:", error);
    return new Response(
      JSON.stringify({
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
