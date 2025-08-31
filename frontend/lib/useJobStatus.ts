import { useState, useEffect } from 'react';

export interface JobStatus {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'paused';
  goal: string;
  progress?: {
    stage: string;
    current_item: string;
    steps_completed: number;
    total_steps: number;
  };
  metadata?: {
    autonomy_level: string;
    budget_per_day: number;
    created_by: string;
    created_at: string;
  };
  artifacts?: Array<{
    name: string;
    size: number;
    created_at: string;
  }>;
}

export function useJobStatus(jobId: string | null) {
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId || !process.env.NEXT_PUBLIC_API_BASE) {
      setJobStatus(null);
      return;
    }

    const fetchJobStatus = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // Try to get job status from backend
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE}/api/jobs/${jobId}/status`);
        
        if (response.ok) {
          const status = await response.json();
          setJobStatus(status);
        } else {
          // If status endpoint doesn't exist, create a minimal status object
          setJobStatus({
            id: jobId,
            status: 'running',
            goal: 'Job in progress...',
            progress: {
              stage: 'processing',
              current_item: 'Executing tools...',
              steps_completed: 0,
              total_steps: 10
            },
            metadata: {
              autonomy_level: 'L0',
              budget_per_day: 50,
              created_by: 'chat_console',
              created_at: new Date().toISOString()
            }
          });
        }
      } catch (error) {
        console.warn('Failed to fetch job status:', error);
        setError(error instanceof Error ? error.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchJobStatus();
    
    // Poll for updates every 5 seconds
    const interval = setInterval(fetchJobStatus, 5000);
    
    return () => clearInterval(interval);
  }, [jobId]);

  return { jobStatus, loading, error };
}
