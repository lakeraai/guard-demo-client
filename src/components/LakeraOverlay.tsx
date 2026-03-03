import React, { useState, useEffect } from 'react';
import { X, Shield, AlertTriangle, CheckCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { apiService } from '../services/api';
import { LakeraResult, DETECTOR_LABELS } from '../types';

interface LakeraOverlayProps {
  isOpen: boolean;
  onClose: () => void;
}

const LakeraOverlay: React.FC<LakeraOverlayProps> = ({ isOpen, onClose }) => {
  const [lakeraResult, setLakeraResult] = useState<LakeraResult | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchLakeraResult();
    }
  }, [isOpen]);

  const fetchLakeraResult = async () => {
    setIsLoading(true);
    try {
      const result = await apiService.getLastLakeraResult();
      setLakeraResult(result);
    } catch (error) {
      console.error('Failed to fetch Lakera result:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  const getStatusIcon = () => {
    if (!lakeraResult) return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
    
    // Check if any guardrails were triggered
    const hasViolations = lakeraResult.flagged || lakeraResult.breakdown?.some(detector => detector.detected);
    
    return hasViolations 
      ? <AlertTriangle className="w-5 h-5 text-red-500" />
      : <CheckCircle className="w-5 h-5 text-green-500" />;
  };

  const getStatusText = () => {
    if (!lakeraResult) return 'No result available';
    
    const hasViolations = lakeraResult.flagged || lakeraResult.breakdown?.some(detector => detector.detected);
    
    return hasViolations ? 'Guardrails triggered' : 'All clear';
  };

  const getStatusColor = () => {
    if (!lakeraResult) return 'bg-yellow-100 text-yellow-800';
    
    const hasViolations = lakeraResult.flagged || lakeraResult.breakdown?.some(detector => detector.detected);
    
    return hasViolations ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800';
  };

  const getViolationSummary = () => {
    if (!lakeraResult || !lakeraResult.breakdown) return null;
    
    // Count violations by type and message
    const violations: { [key: string]: { user: number; assistant: number } } = {};
    
    lakeraResult.breakdown.forEach((detector: any) => {
      if (detector.detected) {
        const type = detector.detector_type || 'unknown';
        const messageType = detector.message_id === 0 ? 'user' : detector.message_id === 1 ? 'assistant' : 'unknown';
        
        if (!violations[type]) {
          violations[type] = { user: 0, assistant: 0 };
        }
        if (messageType === 'user' || messageType === 'assistant') {
          violations[type][messageType]++;
        }
      }
    });
    
    // Also check payload for additional context
    const payloadViolations: { [key: string]: number } = {};
    if (lakeraResult.payload && Array.isArray(lakeraResult.payload)) {
      lakeraResult.payload.forEach((item: any) => {
        const type = item.detector_type || 'unknown';
        payloadViolations[type] = (payloadViolations[type] || 0) + 1;
      });
    }
    
    return { violations, payloadViolations };
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[80vh] overflow-hidden">
        {/* Header */}
        <div className="bg-primary-600 text-white p-4 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Shield className="w-5 h-5" />
            <span className="font-semibold">Lakera Guard Results</span>
          </div>
          <button
            onClick={onClose}
            className="text-white hover:text-gray-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          {isLoading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
              <p className="mt-2 text-gray-600">Loading guardrail results...</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Status Summary */}
              <div className={`p-4 rounded-lg ${getStatusColor()}`}>
                <div className="flex items-center space-x-2">
                  {getStatusIcon()}
                  <span className="font-medium">{getStatusText()}</span>
                </div>
                {lakeraResult && lakeraResult.metadata?.request_uuid && (
                  <p className="text-sm mt-1 opacity-75">
                    Request ID: {lakeraResult.metadata.request_uuid}
                  </p>
                )}
              </div>

              {/* TL;DR Summary */}
              {(() => {
                const summary = getViolationSummary();
                if (!summary || Object.keys(summary.violations).length === 0) return null;
                
                return (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <h3 className="font-semibold text-blue-800 mb-2 flex items-center">
                      <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Violation Summary
                    </h3>
                    <div className="space-y-1 text-sm text-blue-700">
                      {Object.entries(summary.violations).map(([type, counts]) => {
                        const label = DETECTOR_LABELS[type] || type;
                        const payloadCount = summary.payloadViolations[type] || 0;
                        
                        return (
                          <div key={type} className="flex items-center justify-between">
                            <span className="font-medium">{label}</span>
                            <div className="flex items-center space-x-2">
                              {counts.user > 0 && (
                                <span className="bg-red-100 text-red-700 px-2 py-1 rounded text-xs">
                                  User: {counts.user}
                                </span>
                              )}
                              {counts.assistant > 0 && (
                                <span className="bg-orange-100 text-orange-700 px-2 py-1 rounded text-xs">
                                  Assistant: {counts.assistant}
                                </span>
                              )}
                              {payloadCount > 0 && (
                                <span className="bg-purple-100 text-purple-700 px-2 py-1 rounded text-xs">
                                  {payloadCount} instance{payloadCount > 1 ? 's' : ''}
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}

              {/* Guardrail Results */}
              {lakeraResult && lakeraResult.breakdown && (
                <div className="space-y-3">
                  <h3 className="font-semibold text-gray-800">Guardrail Details</h3>
                  {lakeraResult.breakdown.map((detector: any, index: number) => (
                    <div key={index} className="border border-gray-200 rounded-lg p-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-gray-800">
                            {DETECTOR_LABELS[detector.detector_type || ''] || detector.detector_type || `Detector ${index + 1}`}
                          </p>
                          <p className="text-sm text-gray-600">{detector.detector_id || 'No ID'}</p>
                        </div>
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          detector.detected 
                            ? 'bg-red-100 text-red-800'
                            : 'bg-green-100 text-green-800'
                        }`}>
                          {detector.message_id === 0 ? 'User: ' : detector.message_id === 1 ? 'Assistant: ' : ''}
                          {detector.detected ? 'Detected' : 'Clear'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Raw JSON */}
              <div className="border-t pt-4">
                <button
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="flex items-center space-x-2 text-gray-600 hover:text-gray-800"
                >
                  {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  <span className="font-medium">Raw JSON</span>
                </button>
                
                {isExpanded && lakeraResult && (
                  <div className="mt-2">
                    <pre className="bg-gray-100 p-3 rounded text-xs overflow-x-auto">
                      {JSON.stringify(lakeraResult, null, 2)}
                    </pre>
                  </div>
                )}
              </div>

              {/* Error Display */}
              {lakeraResult && lakeraResult.flagged && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <h3 className="font-medium text-red-800 mb-2">Content Flagged</h3>
                  <p className="text-sm text-red-600">This content has been flagged by Lakera Guard.</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-6 py-3 border-t">
          <div className="flex justify-end space-x-2">
            <button
              onClick={fetchLakeraResult}
              className="px-4 py-2 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
            >
              Refresh
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm bg-primary-600 text-white rounded hover:bg-primary-700"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LakeraOverlay;

