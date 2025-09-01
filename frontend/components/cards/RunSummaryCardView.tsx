"use client";
import React from 'react';

interface RunSummaryCardViewProps {
  summary: {
    title?: string;
    stats?: any;
    duration?: string;
    data?: any;
  };
}

export function RunSummaryCardView({ summary }: RunSummaryCardViewProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-gray-900">
          {summary.title || 'Run Summary'}
        </h3>
        <span className="text-sm text-gray-500">📊</span>
      </div>
      
      {summary.duration && (
        <p className="text-sm text-gray-600 mb-3">
          Duration: {summary.duration}
        </p>
      )}
      
      {summary.stats && (
        <div className="grid grid-cols-2 gap-4 mb-3">
          {Object.entries(summary.stats).map(([key, value]) => (
            <div key={key} className="bg-green-50 rounded p-2">
              <p className="text-xs text-green-600 uppercase font-medium">{key}</p>
              <p className="text-lg font-semibold text-green-700">
                {typeof value === 'number' ? value.toLocaleString() : String(value)}
              </p>
            </div>
          ))}
        </div>
      )}
      
      {summary.data && (
        <div className="bg-gray-50 rounded p-3">
          <pre className="text-xs text-gray-700 whitespace-pre-wrap">
            {JSON.stringify(summary.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

