"use client";
import React from 'react';

interface SimulationCardViewProps {
  simulation: {
    title?: string;
    description?: string;
    data?: any;
  };
}

export function SimulationCardView({ simulation }: SimulationCardViewProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-gray-900">
          {simulation.title || 'Simulation Results'}
        </h3>
        <span className="text-sm text-gray-500">🎯</span>
      </div>
      
      {simulation.description && (
        <p className="text-gray-600 mb-3 text-sm">
          {simulation.description}
        </p>
      )}
      
      <div className="bg-gray-50 rounded p-3">
        <pre className="text-xs text-gray-700 whitespace-pre-wrap">
          {JSON.stringify(simulation.data, null, 2)}
        </pre>
      </div>
    </div>
  );
}

