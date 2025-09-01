// In-memory thread -> job mapping
// In production, this should be stored in Redis or a database
const threadJobMap = new Map<string, string>();

export function storeThreadJobMapping(threadId: string, jobId: string): void {
  threadJobMap.set(threadId, jobId);
}

export function getJobIdForThread(threadId: string): string | undefined {
  return threadJobMap.get(threadId);
}

export function removeThreadJobMapping(threadId: string): void {
  threadJobMap.delete(threadId);
}

export function getAllMappings(): Map<string, string> {
  return new Map(threadJobMap);
}
