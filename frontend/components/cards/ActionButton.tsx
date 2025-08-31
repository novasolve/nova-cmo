"use client";
import { useState } from "react";
import { ActionButton as ActionButtonType } from "@/types";

export function ActionButton({
  action,
  threadId,
}: {
  action: ActionButtonType;
  threadId: string;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const click = async () => {
    if (loading) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/actions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          threadId,
          actionId: action.id,
          payload: action.payload,
        }),
      });

      if (!res.ok) {
        const errorText = await res.text();
        setError(errorText || "Action failed");
        console.error("Action failed:", errorText);
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "Network error";
      setError(errorMsg);
      console.error("Action error:", error);
    } finally {
      setLoading(false);
    }
  };

  const getButtonStyles = () => {
    const baseStyles = "text-xs px-3 py-1.5 rounded border font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";

    if (error) {
      return `${baseStyles} bg-red-50 text-red-700 border-red-200`;
    }

    switch (action.style) {
      case "primary":
        return `${baseStyles} bg-black text-white hover:bg-gray-800 border-black disabled:bg-gray-400`;
      case "danger":
        return `${baseStyles} bg-red-600 text-white hover:bg-red-700 border-red-600 disabled:bg-red-400`;
      case "secondary":
      default:
        return `${baseStyles} bg-white text-gray-700 hover:bg-gray-50 border-gray-300`;
    }
  };

  return (
    <div className="flex flex-col">
      <button
        onClick={click}
        disabled={loading}
        className={getButtonStyles()}
        title={error || action.label}
        aria-label={loading ? `${action.label} (loading)` : action.label}
      >
        {loading ? (
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
            <span>Loading...</span>
          </div>
        ) : error ? (
          <span>⚠️ Retry</span>
        ) : (
          action.label
        )}
      </button>
      {error && (
        <div className="text-xs text-red-600 mt-1 max-w-32 truncate" title={error}>
          {error}
        </div>
      )}
    </div>
  );
}
