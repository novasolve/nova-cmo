"use client";
import React from 'react';

interface BriefCardViewProps {
  brief: {
    title?: string;
    content?: string;
    summary?: string;
    data?: any;
  };
}

export function BriefCardView({ brief }: BriefCardViewProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-gray-900">
          {brief.title || 'Campaign Brief'}
        </h3>
        <span className="text-sm text-gray-500">📋</span>
      </div>
      
      {brief.summary && (
        <div className="mb-3">
          <p className="text-gray-600 text-sm font-medium mb-2">Summary:</p>
          <p className="text-gray-700 text-sm">{brief.summary}</p>
        </div>
      )}
      
      {brief.content && (
        <div className="mb-3">
          <p className="text-gray-600 text-sm font-medium mb-2">Details:</p>
          <div className="bg-gray-50 rounded p-3">
            <p className="text-sm text-gray-700 whitespace-pre-wrap">
              {brief.content}
            </p>
          </div>
        </div>
      )}
      
      {brief.data && (
        <div className="bg-blue-50 rounded p-3">
          <pre className="text-xs text-blue-700 whitespace-pre-wrap">
            {JSON.stringify(brief.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
