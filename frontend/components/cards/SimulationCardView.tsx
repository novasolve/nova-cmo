"use client";
import { SimulationCard } from "@/types";
import { ActionButton } from "./ActionButton";

export function SimulationCardView({ card }: { card: SimulationCard }) {
  return (
    <div className="border border-green-200 rounded-lg p-4 bg-green-50">
      <h3 className="font-semibold text-green-900 mb-3">Simulation Pack</h3>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div className="bg-white rounded p-3 border border-green-100">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Reply Rate</div>
          <div className="text-lg font-semibold text-gray-900">
            {(card.forecast.replyRate.mean * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500">
            {(card.forecast.replyRate.low * 100).toFixed(1)}% - {(card.forecast.replyRate.high * 100).toFixed(1)}%
          </div>
        </div>

        <div className="bg-white rounded p-3 border border-green-100">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Deliverability</div>
          <div className="text-lg font-semibold text-gray-900">
            {(card.forecast.deliverability.mean * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500">
            {(card.forecast.deliverability.low * 100).toFixed(1)}% - {(card.forecast.deliverability.high * 100).toFixed(1)}%
          </div>
        </div>

        <div className="bg-white rounded p-3 border border-green-100">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Daily Cost</div>
          <div className="text-lg font-semibold text-gray-900">
            ${card.forecast.dailyCostUSD.toFixed(2)}
          </div>
          <div className="text-xs text-gray-500">per day</div>
        </div>
      </div>

      {card.assumptions.length > 0 && (
        <div className="mb-3">
          <div className="text-sm font-medium text-gray-700 mb-1">Assumptions:</div>
          <ul className="text-sm text-gray-600 list-disc list-inside space-y-1">
            {card.assumptions.map((assumption, idx) => (
              <li key={idx}>{assumption}</li>
            ))}
          </ul>
        </div>
      )}

      {card.warnings.length > 0 && (
        <div className="mb-3">
          <div className="text-sm font-medium text-yellow-700 mb-1">⚠️ Warnings:</div>
          <ul className="text-sm text-yellow-600 list-disc list-inside space-y-1">
            {card.warnings.map((warning, idx) => (
              <li key={idx}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {card.actions.length > 0 && (
        <div className="flex gap-2 pt-3 border-t border-green-200">
          {card.actions.map((action) => (
            <ActionButton key={action.id} action={action} threadId="current" />
          ))}
        </div>
      )}
    </div>
  );
}
