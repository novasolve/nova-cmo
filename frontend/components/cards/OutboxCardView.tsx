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
        <div className="flex items-center gap-2">
          <button
            className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded border"
            onClick={() => {
              try {
                const samples = Array.isArray(outbox.messages) ? outbox.messages : [];
                const emails = samples
                  .map((m: any) => (typeof m === 'object' ? (m.email || m.to) : ''))
                  .filter((e: string) => typeof e === 'string' && e.includes('@'))
                  .join(', ');
                if (emails) navigator.clipboard.writeText(emails);
              } catch {}
            }}
            title="Copy all emails"
          >
            Copy All Emails
          </button>
          <span className="text-sm text-gray-500">📤</span>
        </div>
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

