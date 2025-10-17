import React, { useState, useEffect } from 'react';
import { Plus, Edit, Trash2, Search, Tag, Shield, ShieldAlert } from 'lucide-react';
import { DemoPrompt, DemoPromptCreate, DemoPromptUpdate } from '../types';
import { apiService } from '../services/api';

const DemoPromptManager: React.FC = () => {
  const [prompts, setPrompts] = useState<DemoPrompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<DemoPrompt | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const categories = ['general', 'security', 'tools', 'rag', 'malicious'];

  useEffect(() => {
    loadPrompts();
  }, [selectedCategory]);

  const loadPrompts = async () => {
    try {
      setLoading(true);
      const data = await apiService.getDemoPrompts(selectedCategory || undefined);
      setPrompts(data);
    } catch (error) {
      console.error('Failed to load prompts:', error);
      setMessage({ type: 'error', text: 'Failed to load demo prompts' });
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (promptData: DemoPromptCreate) => {
    try {
      await apiService.createDemoPrompt(promptData);
      await loadPrompts();
      setIsCreating(false);
      setMessage({ type: 'success', text: 'Demo prompt created successfully' });
    } catch (error) {
      console.error('Failed to create prompt:', error);
      setMessage({ type: 'error', text: 'Failed to create demo prompt' });
    }
  };

  const handleUpdate = async (id: number, promptData: DemoPromptUpdate) => {
    try {
      await apiService.updateDemoPrompt(id, promptData);
      await loadPrompts();
      setEditingPrompt(null);
      setMessage({ type: 'success', text: 'Demo prompt updated successfully' });
    } catch (error) {
      console.error('Failed to update prompt:', error);
      setMessage({ type: 'error', text: 'Failed to update demo prompt' });
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this demo prompt?')) return;
    
    try {
      await apiService.deleteDemoPrompt(id);
      await loadPrompts();
      setMessage({ type: 'success', text: 'Demo prompt deleted successfully' });
    } catch (error) {
      console.error('Failed to delete prompt:', error);
      setMessage({ type: 'error', text: 'Failed to delete demo prompt' });
    }
  };

  const filteredPrompts = prompts.filter(prompt => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      prompt.title.toLowerCase().includes(query) ||
      prompt.content.toLowerCase().includes(query) ||
      prompt.tags.some(tag => tag.toLowerCase().includes(query))
    );
  });

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold text-gray-900">Demo Prompt Management</h2>
        <button
          onClick={() => setIsCreating(true)}
          className="flex items-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700"
        >
          <Plus className="w-4 h-4" />
          <span>Add Prompt</span>
        </button>
      </div>

      {/* Message */}
      {message && (
        <div className={`p-4 rounded-lg ${
          message.type === 'success' 
            ? 'bg-green-100 text-green-800 border border-green-200' 
            : 'bg-red-100 text-red-800 border border-red-200'
        }`}>
          {message.text}
        </div>
      )}

      {/* Filters */}
      <div className="flex space-x-4">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              type="text"
              placeholder="Search prompts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>
        <select
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          <option value="">All Categories</option>
          {categories.map(category => (
            <option key={category} value={category}>
              {category.charAt(0).toUpperCase() + category.slice(1)}
            </option>
          ))}
        </select>
      </div>

      {/* Prompts List */}
      {loading ? (
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredPrompts.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              {searchQuery ? 'No prompts match your search.' : 'No demo prompts found.'}
            </div>
          ) : (
            filteredPrompts.map((prompt) => (
              <div key={prompt.id} className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-2">
                      <h3 className="font-medium text-gray-900">{prompt.title}</h3>
                      {prompt.is_malicious && (
                        <ShieldAlert className="w-4 h-4 text-red-500" title="Malicious prompt" />
                      )}
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        prompt.category === 'security' ? 'bg-red-100 text-red-800' :
                        prompt.category === 'malicious' ? 'bg-red-100 text-red-800' :
                        prompt.category === 'tools' ? 'bg-blue-100 text-blue-800' :
                        prompt.category === 'rag' ? 'bg-green-100 text-green-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {prompt.category}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mb-2 line-clamp-2">{prompt.content}</p>
                    <div className="flex items-center space-x-4 text-xs text-gray-500">
                      <span>Used {prompt.usage_count} times</span>
                      {prompt.tags.length > 0 && (
                        <div className="flex items-center space-x-1">
                          <Tag className="w-3 h-3" />
                          <span>{prompt.tags.join(', ')}</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex space-x-2 ml-4">
                    <button
                      onClick={() => setEditingPrompt(prompt)}
                      className="p-2 text-gray-400 hover:text-gray-600"
                    >
                      <Edit className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(prompt.id)}
                      className="p-2 text-gray-400 hover:text-red-600"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Create/Edit Modal */}
      {(isCreating || editingPrompt) && (
        <PromptForm
          prompt={editingPrompt}
          onSave={editingPrompt ? (data) => handleUpdate(editingPrompt.id, data) : handleCreate}
          onCancel={() => {
            setIsCreating(false);
            setEditingPrompt(null);
          }}
        />
      )}
    </div>
  );
};

interface PromptFormProps {
  prompt?: DemoPrompt | null;
  onSave: (data: DemoPromptCreate) => void;
  onCancel: () => void;
}

const PromptForm: React.FC<PromptFormProps> = ({ prompt, onSave, onCancel }) => {
  const [formData, setFormData] = useState<DemoPromptCreate>({
    title: prompt?.title || '',
    content: prompt?.content || '',
    category: prompt?.category || 'general',
    tags: prompt?.tags || [],
    is_malicious: prompt?.is_malicious || false,
  });

  const [tagInput, setTagInput] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title.trim() || !formData.content.trim()) return;
    onSave(formData);
  };

  const addTag = () => {
    if (tagInput.trim() && !formData.tags.includes(tagInput.trim())) {
      setFormData(prev => ({
        ...prev,
        tags: [...prev.tags, tagInput.trim()]
      }));
      setTagInput('');
    }
  };

  const removeTag = (tagToRemove: string) => {
    setFormData(prev => ({
      ...prev,
      tags: prev.tags.filter(tag => tag !== tagToRemove)
    }));
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          {prompt ? 'Edit Demo Prompt' : 'Create Demo Prompt'}
        </h3>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Title
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Content
            </label>
            <textarea
              value={formData.content}
              onChange={(e) => setFormData(prev => ({ ...prev, content: e.target.value }))}
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Category
              </label>
              <select
                value={formData.category}
                onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="general">General</option>
                <option value="security">Security</option>
                <option value="tools">Tools</option>
                <option value="rag">RAG</option>
                <option value="malicious">Malicious</option>
              </select>
            </div>

            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="is_malicious"
                checked={formData.is_malicious}
                onChange={(e) => setFormData(prev => ({ ...prev, is_malicious: e.target.checked }))}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
              />
              <label htmlFor="is_malicious" className="text-sm font-medium text-gray-700">
                Mark as malicious
              </label>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Tags
            </label>
            <div className="flex space-x-2 mb-2">
              <input
                type="text"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
                placeholder="Add a tag..."
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <button
                type="button"
                onClick={addTag}
                className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
              >
                Add
              </button>
            </div>
            {formData.tags.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {formData.tags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center px-2 py-1 bg-primary-100 text-primary-800 text-xs rounded-full"
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(tag)}
                      className="ml-1 text-primary-600 hover:text-primary-800"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
            >
              {prompt ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DemoPromptManager;
