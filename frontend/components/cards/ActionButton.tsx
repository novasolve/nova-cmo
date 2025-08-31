"use client";
import { ActionButton as ActionButtonType } from "@/types";

export function ActionButton({
  action,
  threadId,
}: {
  action: ActionButtonType;
  threadId: string;
}) {
  const click = async () => {
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
        console.error("Action failed:", await res.text());
      }
    } catch (error) {
      console.error("Action error:", error);
    }
  };

  const getButtonStyles = () => {
    const baseStyles = "text-xs px-3 py-1.5 rounded border font-medium transition-colors";
    
    switch (action.style) {
      case "primary":
        return `${baseStyles} bg-black text-white hover:bg-gray-800 border-black`;
      case "danger":
        return `${baseStyles} bg-red-600 text-white hover:bg-red-700 border-red-600`;
      case "secondary":
      default:
        return `${baseStyles} bg-white text-gray-700 hover:bg-gray-50 border-gray-300`;
    }
  };

  return (
    <button onClick={click} className={getButtonStyles()}>
      {action.label}
    </button>
  );
}
