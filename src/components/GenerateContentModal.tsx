import React, { useState } from 'react';
import { X, Download, Eye, EyeOff } from 'lucide-react';
import { apiService } from '../services/api';

interface GenerateContentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onContentGenerated: () => void;
}

const INDUSTRIES = [
  'FinTech', 'Retail', 'Healthcare', 'SaaS', 'Cybersecurity', 
  'Education', 'Manufacturing', 'Real Estate', 'Transportation'
];

const TONES = ['professional', 'casual', 'technical', 'friendly'];
const DEPTHS = ['short', 'medium', 'long'];
const SECTIONS = [
  { id: 'faqs', label: 'FAQs' },
  { id: 'glossary', label: 'Glossary' },
  { id: 'policies', label: 'Policies' },
  { id: 'objections', label: 'Objections' }
];

const GenerateContentModal: React.FC<GenerateContentModalProps> = ({ 
  isOpen, 
  onClose, 
  onContentGenerated 
}) => {
  const [mode, setMode] = useState<'quick' | 'guided'>('quick');
  const [industry, setIndustry] = useState('FinTech');
  const [audience, setAudience] = useState('B2B professionals');
  const [tone, setTone] = useState('professional');
  const [depth, setDepth] = useState('medium');
  const [selectedSections, setSelectedSections] = useState(['faqs', 'glossary']);
  const [constraints, setConstraints] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [preview, setPreview] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [isIngested, setIsIngested] = useState(false);

  const handleGenerate = async (previewOnly: boolean = true) => {
    setIsGenerating(true);
    try {
      const request = {
        industry,
        seed_prompt: `Produce a ${depth} knowledge pack about ${industry} for ${audience} with a ${tone} tone. Include sections: ${selectedSections.join(', ')}. ${constraints ? `Constraints: ${constraints}` : ''}`,
        preview_only: previewOnly
      };

      const response = await apiService.generateRagContent(request);
      setPreview(response.markdown);
      setIsIngested(response.ingested);
      
      if (previewOnly) {
        setShowPreview(true);
      } else {
        onContentGenerated();
        onClose();
      }
    } catch (error) {
      console.error('Failed to generate content:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleIngest = async () => {
    await handleGenerate(false);
  };

  const toggleSection = (sectionId: string) => {
    setSelectedSections(prev => 
      prev.includes(sectionId) 
        ? prev.filter(id => id !== sectionId)
        : [...prev, sectionId]
    );
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl mx-4 max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="bg-primary-600 text-white p-4 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="font-semibold">Generate AI Content</span>
          </div>
          <button onClick={onClose} className="text-white hover:text-gray-200">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex h-[calc(90vh-80px)]">
          {/* Left Panel - Configuration */}
          <div className="w-1/2 p-6 overflow-y-auto border-r">
            <div className="space-y-6">
              {/* Mode Selection */}
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">Generation Mode</h3>
                <div className="flex space-x-4">
                  <button
                    onClick={() => setMode('quick')}
                    className={`px-4 py-2 rounded-lg ${
                      mode === 'quick' 
                        ? 'bg-primary-600 text-white' 
                        : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    Quick Generate
                  </button>
                  <button
                    onClick={() => setMode('guided')}
                    className={`px-4 py-2 rounded-lg ${
                      mode === 'guided' 
                        ? 'bg-primary-600 text-white' 
                        : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    Guided Generate
                  </button>
                </div>
              </div>

              {/* Industry Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Industry
                </label>
                <select
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  {INDUSTRIES.map(ind => (
                    <option key={ind} value={ind}>{ind}</option>
                  ))}
                </select>
              </div>

              {mode === 'guided' && (
                <>
                  {/* Audience */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Target Audience
                    </label>
                    <input
                      type="text"
                      value={audience}
                      onChange={(e) => setAudience(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </div>

                  {/* Tone */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Tone
                    </label>
                    <select
                      value={tone}
                      onChange={(e) => setTone(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    >
                      {TONES.map(t => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </div>

                  {/* Depth */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Content Depth
                    </label>
                    <select
                      value={depth}
                      onChange={(e) => setDepth(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    >
                      {DEPTHS.map(d => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                  </div>

                  {/* Sections */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Include Sections
                    </label>
                    <div className="space-y-2">
                      {SECTIONS.map(section => (
                        <label key={section.id} className="flex items-center">
                          <input
                            type="checkbox"
                            checked={selectedSections.includes(section.id)}
                            onChange={() => toggleSection(section.id)}
                            className="mr-2"
                          />
                          {section.label}
                        </label>
                      ))}
                    </div>
                  </div>

                  {/* Constraints */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Constraints (Optional)
                    </label>
                    <textarea
                      value={constraints}
                      onChange={(e) => setConstraints(e.target.value)}
                      rows={3}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                      placeholder="e.g., avoid medical advice, focus on technical details..."
                    />
                  </div>
                </>
              )}

              {/* Action Buttons */}
              <div className="flex space-x-4 pt-4">
                <button
                  onClick={() => handleGenerate(true)}
                  disabled={isGenerating}
                  className="flex-1 bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 disabled:opacity-50"
                >
                  {isGenerating ? 'Generating...' : 'Preview'}
                </button>
                {showPreview && (
                  <button
                    onClick={handleIngest}
                    disabled={isGenerating || isIngested}
                    className="flex-1 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50"
                  >
                    {isIngested ? 'Ingested' : 'Ingest'}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Right Panel - Preview */}
          <div className="w-1/2 p-6 overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900">Preview</h3>
              {showPreview && (
                <button
                  onClick={() => setShowPreview(!showPreview)}
                  className="flex items-center space-x-1 text-gray-600 hover:text-gray-800"
                >
                  {showPreview ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  <span>{showPreview ? 'Hide' : 'Show'}</span>
                </button>
              )}
            </div>

            {isGenerating ? (
              <div className="text-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
                <p className="mt-2 text-gray-600">Generating content...</p>
              </div>
            ) : showPreview && preview ? (
              <div className="prose max-w-none">
                <pre className="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded-lg overflow-auto max-h-96">
                  {preview}
                </pre>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p>Click "Preview" to generate content</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default GenerateContentModal;
