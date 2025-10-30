import React, { useState, useEffect, useImperativeHandle, forwardRef } from 'react';
import { Trash2, FileText, Sparkles, RefreshCw } from 'lucide-react';
import { apiService } from '../services/api';

interface RagSource {
  id: number;
  name: string;
  source_type: 'generated' | 'uploaded';
  chunks_count: number;
  created_at: string;
  updated_at: string;
}

interface RagManagementProps {
  onUploadStart?: () => void;
  onUploadComplete?: () => void;
  onGenerateComplete?: () => void;
}

export interface RagManagementRef {
  refresh: () => void;
}

const RagManagement = forwardRef<RagManagementRef, RagManagementProps>(({ 
  onUploadStart,
  onUploadComplete, 
  onGenerateComplete 
}, ref) => {
  const [sources, setSources] = useState<RagSource[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadSources = async () => {
    try {
      setIsLoading(true);
      const response = await apiService.getRagSources();
      setSources(response.sources);
    } catch (error) {
      console.error('Failed to load RAG sources:', error);
      setMessage({ type: 'error', text: 'Failed to load RAG sources' });
    } finally {
      setIsLoading(false);
    }
  };

  const clearAllContent = async () => {
    if (!window.confirm('Are you sure you want to clear all RAG content? This action cannot be undone.')) {
      return;
    }

    try {
      setIsClearing(true);
      await apiService.clearRagContent();
      setSources([]);
      setMessage({ type: 'success', text: 'RAG content cleared successfully' });
    } catch (error) {
      console.error('Failed to clear RAG content:', error);
      setMessage({ type: 'error', text: 'Failed to clear RAG content' });
    } finally {
      setIsClearing(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getSourceIcon = (sourceType: string) => {
    return sourceType === 'generated' ? (
      <Sparkles className="w-4 h-4 text-blue-500" />
    ) : (
      <FileText className="w-4 h-4 text-green-500" />
    );
  };

  const getSourceTypeLabel = (sourceType: string) => {
    return sourceType === 'generated' ? 'AI Generated' : 'Uploaded File';
  };

  useEffect(() => {
    loadSources();
  }, []);

  // Expose refresh function to parent components
  useImperativeHandle(ref, () => ({
    refresh: loadSources
  }));

  return (
    <div className="space-y-6">
      {/* Header with refresh and clear buttons */}
      <div className="flex justify-between items-center">
        <h3 className="text-md font-medium text-gray-800">RAG Content</h3>
        <div className="flex space-x-2">
          <button
            onClick={loadSources}
            disabled={isLoading}
            className="flex items-center space-x-1 px-3 py-1 text-sm text-gray-600 hover:text-gray-800 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          {sources.length > 0 && (
            <button
              onClick={clearAllContent}
              disabled={isClearing}
              className="flex items-center space-x-1 px-3 py-1 text-sm text-red-600 hover:text-red-800 disabled:opacity-50"
            >
              <Trash2 className="w-4 h-4" />
              <span>{isClearing ? 'Clearing...' : 'Clear All'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Message */}
      {message && (
        <div className={`p-3 rounded-lg ${
          message.type === 'success' 
            ? 'bg-green-100 text-green-800 border border-green-200' 
            : 'bg-red-100 text-red-800 border border-red-200'
        }`}>
          {message.text}
        </div>
      )}

      {/* Sources List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600"></div>
          <span className="ml-2 text-gray-600">Loading RAG sources...</span>
        </div>
      ) : sources.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <FileText className="w-12 h-12 mx-auto mb-4 text-gray-300" />
          <p className="text-lg font-medium mb-2">No RAG content yet</p>
          <p className="text-sm">Upload documents or generate AI content to get started.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sources.map((source) => (
            <div
              key={source.id}
              className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-3">
                  {getSourceIcon(source.source_type)}
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <h4 className="font-medium text-gray-900">{source.name}</h4>
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        source.source_type === 'generated'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-green-100 text-green-800'
                      }`}>
                        {getSourceTypeLabel(source.source_type)}
                      </span>
                    </div>
                    <div className="mt-1 text-sm text-gray-500">
                      <span>{source.chunks_count} chunks</span>
                      <span className="mx-2">•</span>
                      <span>Added {formatDate(source.created_at)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Summary */}
      {sources.length > 0 && (
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex justify-between text-sm text-gray-600">
            <span>Total sources: {sources.length}</span>
            <span>
              Total chunks: {sources.reduce((sum, source) => sum + source.chunks_count, 0)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
});

RagManagement.displayName = 'RagManagement';

export default RagManagement;
