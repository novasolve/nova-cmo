"use client";
import { CampaignBriefCard } from "@/types";
import { ActionButton } from "./ActionButton";
import { useState } from "react";

export function BriefCardView({ card }: { card: CampaignBriefCard }) {
  const [showYaml, setShowYaml] = useState(false);

  return (
    <div className="border border-blue-200 rounded-lg p-4 bg-blue-50">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-blue-900">Campaign Brief</h3>
        <button
          onClick={() => setShowYaml(!showYaml)}
          className="text-xs text-blue-600 hover:text-blue-800"
        >
          {showYaml ? "Hide" : "Show"} YAML
        </button>
      </div>

      <div className="space-y-3 text-sm">
        <div>
          <span className="font-medium text-gray-700">Goal:</span>
          <div className="mt-1 text-gray-600">{card.goal}</div>
        </div>

        <div>
          <span className="font-medium text-gray-700">Limits:</span>
          <div className="mt-1 text-gray-600">
            Max Steps: {card.limits.maxSteps} • Max Repos: {card.limits.maxRepos} • Max People: {card.limits.maxPeople}
          </div>
        </div>

        {card.risks.length > 0 && (
          <div>
            <span className="font-medium text-gray-700">Risks:</span>
            <ul className="mt-1 text-gray-600 list-disc list-inside space-y-1">
              {card.risks.map((risk, idx) => (
                <li key={idx}>{risk}</li>
              ))}
            </ul>
          </div>
        )}

        {showYaml && (
          <div>
            <span className="font-medium text-gray-700">Configuration:</span>
            <pre className="mt-1 p-2 bg-white border rounded text-xs font-mono overflow-x-auto">
              {card.yaml}
            </pre>
          </div>
        )}
      </div>

      {card.actions.length > 0 && (
        <div className="flex gap-2 mt-4 pt-3 border-t border-blue-200">
          {card.actions.map((action) => (
            <ActionButton key={action.id} action={action} threadId="current" />
          ))}
        </div>
      )}
    </div>
  );
}
