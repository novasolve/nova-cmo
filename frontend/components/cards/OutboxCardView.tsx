"use client";
import React from 'react';

interface OutboxCardViewProps {
  outbox: {
    title?: string;
    messages?: any[];
    data?: any;
  };
}

export function OutboxCardView({ outbox }: OutboxCardViewProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-gray-900">
          {outbox.title || 'Outreach Messages'}
        </h3>
        <span className="text-sm text-gray-500">📤</span>
      </div>
      
      {outbox.messages && outbox.messages.length > 0 && (
        <div className="space-y-2">
          {outbox.messages.map((message, index) => (
            <div key={index} className="bg-blue-50 rounded p-3">
              <p className="text-sm text-blue-700">
                {typeof message === 'string' ? message : JSON.stringify(message)}
              </p>
            </div>
          ))}
        </div>
      )}
      
      {outbox.data && (
        <div className="bg-gray-50 rounded p-3 mt-3">
          <pre className="text-xs text-gray-700 whitespace-pre-wrap">
            {JSON.stringify(outbox.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
