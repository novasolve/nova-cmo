// Thread storage and management
export interface Thread {
  id: string;
  name: string;
  currentJobId?: string;
  lastActivity?: string;
  campaignType?: 'smoke_test' | 'real_campaign';
  metadata?: {
    autonomyLevel?: string;
    budget?: number;
    totalJobs?: number;
  };
}

// In-memory storage (in production, use localStorage or backend)
const threads = new Map<string, Thread>();

export function createThread(id: string, name: string, campaignType?: Thread['campaignType']): Thread {
  const thread: Thread = {
    id,
    name,
    campaignType: campaignType || 'real_campaign',
    lastActivity: new Date().toISOString(),
    metadata: {
      totalJobs: 0
    }
  };

  threads.set(id, thread);
  return thread;
}

export function getThread(id: string): Thread | null {
  return threads.get(id) || null;
}

export function updateThread(id: string, updates: Partial<Thread>): Thread | null {
  const thread = threads.get(id);
  if (!thread) return null;

  const updatedThread = {
    ...thread,
    ...updates,
    lastActivity: new Date().toISOString()
  };

  threads.set(id, updatedThread);
  return updatedThread;
}

export function setThreadJobId(threadId: string, jobId: string): void {
  const thread = getThread(threadId);
  if (thread) {
    updateThread(threadId, {
      currentJobId: jobId,
      metadata: {
        ...thread.metadata,
        totalJobs: (thread.metadata?.totalJobs || 0) + 1
      }
    });
  }
}

export function getAllThreads(): Thread[] {
  return Array.from(threads.values()).sort((a, b) =>
    new Date(b.lastActivity || 0).getTime() - new Date(a.lastActivity || 0).getTime()
  );
}

export function getAllCampaigns(): Thread[] {
  // Alias for getAllThreads - campaigns are represented as threads
  return getAllThreads();
}

export function deleteThread(id: string): boolean {
  return threads.delete(id);
}

export function clearTestThreads(): void {
  // Remove any threads that look like test threads
  const threadsToDelete: string[] = [];

    for (const [id, thread] of Array.from(threads.entries())) {
    if (id.includes('test') || 
        thread.name.toLowerCase().includes('test')) {
      threadsToDelete.push(id);
    }
  }

  threadsToDelete.forEach(id => threads.delete(id));
  console.log(`Cleared ${threadsToDelete.length} test threads:`, threadsToDelete);
}

// Helper function to generate a friendly thread name from the goal
export function generateThreadName(goal: string): string {
  if (!goal || goal.trim().length === 0) return "New Thread";

  // Extract key information from the goal
  if (goal.toLowerCase().includes("python")) {
    return "Python Maintainers";
  } else if (goal.toLowerCase().includes("javascript") || goal.toLowerCase().includes("js")) {
    return "JS Framework Leads";
  } else if (goal.toLowerCase().includes("react")) {
    return "React Developers";
  } else if (goal.toLowerCase().includes("smoke test")) {
    return "Smoke Test";
  }

  // Fallback: use first few words
  const words = goal.split(' ').slice(0, 3);
  return words.map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()).join(' ');
}

// Initialize with a single default thread and clear any test threads
if (threads.size === 0) {
  createThread("default", "General Chat");
} else {
  // Clear any existing test threads on startup
  clearTestThreads();
}
