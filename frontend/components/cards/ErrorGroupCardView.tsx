"use client";
import React from 'react';

interface ErrorGroupCardViewProps {
  errors: {
    title?: string;
    count?: number;
    items?: any[];
    data?: any;
  };
}

export function ErrorGroupCardView({ errors }: ErrorGroupCardViewProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-red-200 p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-red-900">
          {errors.title || 'Errors'}
        </h3>
        <div className="flex items-center space-x-2">
          {errors.count && (
            <span className="bg-red-100 text-red-700 px-2 py-1 rounded text-sm font-medium">
              {errors.count}
            </span>
          )}
          <span className="text-sm text-red-500">⚠️</span>
        </div>
      </div>
      
      {errors.items && errors.items.length > 0 && (
        <div className="space-y-2">
          {errors.items.map((error, index) => (
            <div key={index} className="bg-red-50 rounded p-3 border-l-4 border-red-400">
              <p className="text-sm text-red-700">
                {typeof error === 'string' ? error : JSON.stringify(error)}
              </p>
            </div>
          ))}
        </div>
      )}
      
      {errors.data && (
        <div className="bg-red-50 rounded p-3 mt-3">
          <pre className="text-xs text-red-700 whitespace-pre-wrap">
            {JSON.stringify(errors.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

