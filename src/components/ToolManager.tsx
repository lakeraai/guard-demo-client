import React, { useState, useEffect } from 'react';
import { Plus, Settings, Play, Trash2, Search } from 'lucide-react';
import { Tool, ToolCreate } from '../types';
import { apiService } from '../services/api';

const ToolManager: React.FC = () => {
  const [tools, setTools] = useState<Tool[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingTool, setEditingTool] = useState<Tool | null>(null);
  const [testResults, setTestResults] = useState<Record<number, any>>({});

  const [newTool, setNewTool] = useState<ToolCreate>({
    name: '',
    description: '',
    endpoint: '',
    type: 'mcp',
    enabled: true,
    config_json: {},
  });

  useEffect(() => {
    loadTools();
  }, []);

  const loadTools = async () => {
    setIsLoading(true);
    try {
      const toolsData = await apiService.getTools();
      setTools(toolsData);
    } catch (error) {
      console.error('Failed to load tools:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddTool = async () => {
    try {
      await apiService.createTool(newTool);
      setNewTool({
        name: '',
        description: '',
        endpoint: '',
        type: 'mcp',
        enabled: true,
        config_json: {},
      });
      setShowAddForm(false);
      await loadTools();
    } catch (error) {
      console.error('Failed to add tool:', error);
    }
  };

  const handleUpdateTool = async (tool: Tool) => {
    try {
      await apiService.updateTool(tool.id, {
        name: tool.name,
        description: tool.description,
        endpoint: tool.endpoint,
        type: tool.type,
        enabled: tool.enabled,
        config_json: tool.config_json,
      });
      setEditingTool(null);
      await loadTools();
    } catch (error) {
      console.error('Failed to update tool:', error);
    }
  };

  const handleDeleteTool = async (toolId: number) => {
    if (!confirm('Are you sure you want to delete this tool?')) return;
    
    try {
      await apiService.deleteTool(toolId);
      await loadTools();
    } catch (error) {
      console.error('Failed to delete tool:', error);
    }
  };

  const handleTestTool = async (toolId: number) => {
    try {
      const result = await apiService.testTool(toolId, { test: true });
      setTestResults(prev => ({ ...prev, [toolId]: result }));
    } catch (error) {
      console.error('Failed to test tool:', error);
      setTestResults(prev => ({ ...prev, [toolId]: { error: 'Test failed' } }));
    }
  };

  const filteredTools = tools.filter(tool =>
    tool.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    tool.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Search and Add */}
      <div className="flex justify-between items-center">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <input
            type="text"
            placeholder="Search tools..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="flex items-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700"
        >
          <Plus className="w-4 h-4" />
          <span>Add Tool</span>
        </button>
      </div>

      {/* Add Tool Form */}
      {showAddForm && (
        <div className="bg-gray-50 p-6 rounded-lg border">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Add New Tool</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Name</label>
              <input
                type="text"
                value={newTool.name}
                onChange={(e) => setNewTool({ ...newTool, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Type</label>
              <select
                value={newTool.type}
                onChange={(e) => setNewTool({ ...newTool, type: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="mcp">MCP (SSE Endpoint)</option>
                <option value="http">HTTP (MCP Endpoint)</option>
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
              <textarea
                value={newTool.description}
                onChange={(e) => setNewTool({ ...newTool, description: e.target.value })}
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">Endpoint</label>
              <input
                type="text"
                value={newTool.endpoint}
                onChange={(e) => setNewTool({ ...newTool, endpoint: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>
          <div className="flex justify-end space-x-2 mt-4">
            <button
              onClick={() => setShowAddForm(false)}
              className="px-4 py-2 text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300"
            >
              Cancel
            </button>
            <button
              onClick={handleAddTool}
              disabled={!newTool.name}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              Add Tool
            </button>
          </div>
        </div>
      )}

      {/* Tools List */}
      {isLoading ? (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
          <p className="mt-2 text-gray-600">Loading tools...</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredTools.map((tool) => (
            <div key={tool.id} className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3">
                    <h3 className="text-lg font-medium text-gray-900">{tool.name}</h3>
                    <span className={`px-2 py-1 text-xs rounded-full ${
                      tool.enabled 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-gray-100 text-gray-800'
                    }`}>
                      {tool.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                    <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full">
                      {tool.type.toUpperCase()}
                    </span>
                  </div>
                  {tool.description && (
                    <p className="text-sm text-gray-600 mt-1">{tool.description}</p>
                  )}
                  {tool.endpoint && (
                    <p className="text-xs text-gray-500 mt-1">{tool.endpoint}</p>
                  )}
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handleTestTool(tool.id)}
                    className="p-2 text-gray-400 hover:text-gray-600"
                    title="Test Tool"
                  >
                    <Play className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setEditingTool(editingTool?.id === tool.id ? null : tool)}
                    className="p-2 text-gray-400 hover:text-gray-600"
                    title="Edit Tool"
                  >
                    <Settings className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDeleteTool(tool.id)}
                    className="p-2 text-red-400 hover:text-red-600"
                    title="Delete Tool"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Edit Form */}
              {editingTool?.id === tool.id && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Name</label>
                      <input
                        type="text"
                        value={editingTool.name}
                        onChange={(e) => setEditingTool({ ...editingTool, name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Type</label>
                      <select
                        value={editingTool.type}
                        onChange={(e) => setEditingTool({ ...editingTool, type: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                      >
                        <option value="mcp">MCP (SSE Endpoint)</option>
                        <option value="http">HTTP (MCP Endpoint)</option>
                      </select>
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
                      <textarea
                        value={editingTool.description || ''}
                        onChange={(e) => setEditingTool({ ...editingTool, description: e.target.value })}
                        rows={2}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-2">Endpoint</label>
                      <input
                        type="text"
                        value={editingTool.endpoint || ''}
                        onChange={(e) => setEditingTool({ ...editingTool, endpoint: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                    <div className="flex items-center space-x-3">
                      <input
                        type="checkbox"
                        id={`enabled-${tool.id}`}
                        checked={editingTool.enabled}
                        onChange={(e) => setEditingTool({ ...editingTool, enabled: e.target.checked })}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                      />
                      <label htmlFor={`enabled-${tool.id}`} className="text-sm font-medium text-gray-700">
                        Enabled
                      </label>
                    </div>
                  </div>
                  <div className="flex justify-end space-x-2 mt-4">
                    <button
                      onClick={() => setEditingTool(null)}
                      className="px-4 py-2 text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleUpdateTool(editingTool)}
                      className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
                    >
                      Save Changes
                    </button>
                  </div>
                </div>
              )}

              {/* Test Result */}
              {testResults[tool.id] && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <h4 className="text-sm font-medium text-gray-900 mb-2">Test Result</h4>
                  <pre className="bg-gray-100 p-3 rounded text-xs overflow-x-auto">
                    {JSON.stringify(testResults[tool.id], null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {filteredTools.length === 0 && !isLoading && (
        <div className="text-center py-8">
          <p className="text-gray-500">No tools found</p>
        </div>
      )}
    </div>
  );
};

export default ToolManager;

