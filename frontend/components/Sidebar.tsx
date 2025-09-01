"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getAllThreads, getAllCampaigns, createThread, generateThreadName, type Thread } from "@/lib/threadStorage";

export function Sidebar() {
  const [activeTab, setActiveTab] = useState<"campaigns" | "threads">("threads");
  const [threads, setThreads] = useState<Thread[]>([]);
  const [campaigns, setCampaigns] = useState<Thread[]>([]);
  const router = useRouter();

  // Load threads and campaigns on mount
  useEffect(() => {
    setThreads(getAllThreads());
    setCampaigns(getAllCampaigns());
  }, []);

  // Refresh threads periodically and sync with backend with exponential backoff
  useEffect(() => {
    let syncInterval = 3000; // Start with 3 seconds
    let consecutiveErrors = 0;
    let timeoutId: NodeJS.Timeout;

    const syncWithBackend = async () => {
      try {
        // Sync backend jobs to thread storage
        const response = await fetch('/api/threads/sync', { method: 'POST' });

        if (response.ok) {
          // Success - reset backoff
          consecutiveErrors = 0;
          syncInterval = 3000;
        } else {
          // Non-200 response - increase backoff
          consecutiveErrors++;
          syncInterval = Math.min(syncInterval * 1.5, 30000); // Max 30 seconds
        }

        // Refresh local state
        setThreads(getAllThreads());
        setCampaigns(getAllCampaigns());
      } catch (error) {
        console.warn('Failed to sync with backend:', error);
        // Network error - increase backoff
        consecutiveErrors++;
        syncInterval = Math.min(syncInterval * 1.5, 30000); // Max 30 seconds

        // Still refresh local state
        setThreads(getAllThreads());
        setCampaigns(getAllCampaigns());
      }

      // Schedule next sync with current interval
      timeoutId = setTimeout(syncWithBackend, syncInterval);
    };

    // Initial sync
    syncWithBackend();

    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, []);

  const handleNewThread = () => {
    // Generate a unique thread ID
    const newThreadId = `thread-${Date.now()}`;

    // Create the thread in storage
    const newThread = createThread(newThreadId, "New Thread");

    // Update local state immediately
    setThreads(getAllThreads());

    // Navigate to the new thread
    router.push(`/threads/${newThreadId}`);
  };

  const handleNewCampaign = () => {
    // Generate a unique campaign ID
    const newCampaignId = `campaign-${Date.now()}`;

    // Create the campaign thread in storage
    const newThread = createThread(newCampaignId, "New Campaign");

    // Update local state immediately
    setThreads(getAllThreads());

    // Navigate to the new campaign thread
    router.push(`/threads/${newCampaignId}`);
  };

  return (
    <div className="h-full flex flex-col">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">CMO Agent</h2>

        <div className="flex bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => setActiveTab("threads")}
            className={`flex-1 text-sm px-3 py-1.5 rounded ${
              activeTab === "threads"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            Threads
          </button>
          <button
            onClick={() => setActiveTab("campaigns")}
            className={`flex-1 text-sm px-3 py-1.5 rounded ${
              activeTab === "campaigns"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            Campaigns
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {activeTab === "threads" && (
          <div className="space-y-2">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-700">Chat Threads</h3>
              <button
                onClick={handleNewThread}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                + New
              </button>
            </div>
            {threads.map((thread) => (
              <a
                key={thread.id}
                href={`/threads/${thread.id}`}
                className="block p-3 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors"
              >
                <div className="font-medium text-sm text-gray-900 mb-1">
                  {thread.name}
                </div>
                <div className="text-xs text-gray-500 line-clamp-2 mb-1">
                  {thread.lastActivity || "No recent activity"}
                </div>
                <div className="text-xs text-gray-400">
                  {thread.lastActivity ? "Recent" : "Idle"}
                </div>
              </a>
            ))}
          </div>
        )}

        {activeTab === "campaigns" && (
          <div className="space-y-2">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-700">Campaigns</h3>
              <button
                onClick={handleNewCampaign}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                + New
              </button>
            </div>
            {campaigns.map((campaign) => (
              <div
                key={campaign.id}
                className="p-3 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors cursor-pointer"
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="font-medium text-sm text-gray-900">
                    {campaign.name}
                  </div>
                  <span
                    className={`text-xs px-2 py-1 rounded ${
                      campaign.currentJobId
                        ? "bg-green-100 text-green-800"
                        : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {campaign.currentJobId ? "Active" : "Idle"}
                  </span>
                </div>
                <div className="text-xs text-gray-500">
                  {campaign.lastActivity || "No recent activity"}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
