import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Download, Eye, EyeOff, ChevronDown, ChevronRight } from 'lucide-react';
import { AppConfig, AppConfigUpdate } from '../types';
import { apiService } from '../services/api';
import UploadDropzone from '../components/UploadDropzone';
import ToolManager from '../components/ToolManager';
import GenerateContentModal from '../components/GenerateContentModal';
import RagManagement, { RagManagementRef } from '../components/RagManagement';
import DemoPromptManager from '../components/DemoPromptManager';

type TabType = 'setup' | 'branding' | 'llm' | 'rag' | 'rag-scanning' | 'tools' | 'security' | 'prompts' | 'export';

const AdminConsole: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('setup');
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false);
  const [ragScanningResult, setRagScanningResult] = useState<any>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [showOpenAIKey, setShowOpenAIKey] = useState(false);
  const [showLakeraKey, setShowLakeraKey] = useState(false);
  const [showMCPInstructions, setShowMCPInstructions] = useState(false);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [ragScanningNotificationCount, setRagScanningNotificationCount] = useState<number>(0);
  const [ragScanningProgress, setRagScanningProgress] = useState<{isScanning: boolean; current: number; total: number; filename?: string} | null>(null);
  const progressPollingRef = useRef<number | null>(null);
  const ragManagementRef = React.useRef<RagManagementRef>(null);

  useEffect(() => {
    loadConfig();
    loadModels();
    loadRagScanningResult();
  }, []);

  // Clear notification when user views the RAG scanning report
  useEffect(() => {
    if (activeTab === 'rag-scanning') {
      clearRagScanningNotification();
    }
  }, [activeTab]);

  // Poll for RAG scanning progress
  useEffect(() => {
    let intervalId: number;
    
    const pollProgress = async () => {
      try {
        const progress = await apiService.getRagScanningProgress();
        setRagScanningProgress(progress);
        
        // If progress is null or scanning is complete, stop polling
        if (!progress || !progress.isScanning) {
          if (intervalId) {
            clearInterval(intervalId);
            intervalId = 0;
          }
          setRagScanningProgress(null);
        }
      } catch (error) {
        // No progress available, clear it and stop polling
        setRagScanningProgress(null);
        if (intervalId) {
          clearInterval(intervalId);
          intervalId = 0;
        }
      }
    };

    // Start polling if RAG content scanning is enabled (regardless of current tab)
    if (config?.rag_content_scanning) {
      intervalId = setInterval(pollProgress, 1000); // Poll every second
    }

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [config?.rag_content_scanning]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (progressPollingRef.current) {
        clearInterval(progressPollingRef.current);
        progressPollingRef.current = null;
      }
    };
  }, []);

  // Start polling immediately when upload begins
  const startProgressPolling = () => {
    // Clear any existing polling
    if (progressPollingRef.current) {
      clearInterval(progressPollingRef.current);
      progressPollingRef.current = null;
    }

    // Show progress immediately with a placeholder
    setRagScanningProgress({
      isScanning: true,
      current: 0,
      total: 1,
      filename: "Uploading..."
    });

    let hasStartedScanning = false;
    let consecutive404s = 0;

    const pollProgress = async () => {
      try {
        const progress = await apiService.getRagScanningProgress();
        setRagScanningProgress(progress);
        
        // Reset 404 counter on successful response
        consecutive404s = 0;
        
        // If we get progress data, scanning has started
        if (progress) {
          hasStartedScanning = true;
        }
        
        // If progress is null or scanning is complete, stop polling
        if (!progress || !progress.isScanning) {
          if (progressPollingRef.current) {
            clearInterval(progressPollingRef.current);
            progressPollingRef.current = null;
          }
          // Keep the progress bar visible for a moment to show completion
          if (progress && !progress.isScanning) {
            setTimeout(() => setRagScanningProgress(null), 2000);
          } else {
            setRagScanningProgress(null);
          }
        }
      } catch (error: any) {
        console.log('Progress polling error:', error?.message);
        
        // If we get a 404, check if scanning has started
        if (error?.message?.includes('404') || error?.message?.includes('Not Found') || error?.message?.includes('API request failed: Not Found')) {
          consecutive404s++;
          
          // If scanning has started and we get 404s, it means scanning is complete
          if (hasStartedScanning) {
            console.log('Stopping progress polling - scanning completed');
            if (progressPollingRef.current) {
              clearInterval(progressPollingRef.current);
              progressPollingRef.current = null;
            }
            setRagScanningProgress(null);
          } else {
            // If scanning hasn't started yet, keep polling but limit consecutive 404s
            console.log(`Scanning not started yet, 404 count: ${consecutive404s}`);
            if (consecutive404s >= 10) {
              console.log('Too many 404s before scanning started, stopping polling');
              if (progressPollingRef.current) {
                clearInterval(progressPollingRef.current);
                progressPollingRef.current = null;
              }
              setRagScanningProgress(null);
            }
          }
        }
        // For other errors, keep trying for a bit
      }
    };
    
    // Start polling immediately, then continue with interval
    pollProgress();
    
    // Set up interval polling
    progressPollingRef.current = setInterval(pollProgress, 1000);
    
    // Clear interval after 2 minutes to prevent infinite polling
    setTimeout(() => {
      if (progressPollingRef.current) {
        clearInterval(progressPollingRef.current);
        progressPollingRef.current = null;
      }
      setRagScanningProgress(null);
    }, 120000);
  };

  const loadModels = async () => {
    try {
      const modelsData = await apiService.getModels();
      setAvailableModels(modelsData.models);
    } catch (error) {
      console.error('Failed to load models:', error);
      // Fallback to hardcoded models if API fails
      setAvailableModels([
        "gpt-5",
        "gpt-5-mini", 
        "gpt-5-nano",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4",
        "gpt-4-turbo",
        "gpt-3.5-turbo"
      ]);
    }
  };

  const loadRagScanningResult = async () => {
    try {
      const result = await apiService.getLastRagScanningResult();
      setRagScanningResult(result);
      
      // Set notification count based on blocked chunks
      if (result && result.blocked_chunks > 0) {
        setRagScanningNotificationCount(result.blocked_chunks);
      } else {
        setRagScanningNotificationCount(0);
      }
    } catch (error) {
      // No result available yet, that's okay
      setRagScanningResult(null);
      setRagScanningNotificationCount(0);
    }
  };

  const clearRagScanningNotification = () => {
    setRagScanningNotificationCount(0);
  };

  const loadConfig = async () => {
    try {
      const configData = await apiService.getConfig();
      // Ensure rag_content_scanning has a default value if not present
      if (configData.rag_content_scanning === undefined) {
        configData.rag_content_scanning = false;
      }
      setConfig(configData);
    } catch (error) {
      console.error('Failed to load config:', error);
      setMessage({ type: 'error', text: 'Failed to load configuration' });
    }
  };

  const handleConfigUpdate = async (updates: Partial<AppConfigUpdate>) => {
    if (!config) return;

    try {
      // If Lakera is being disabled, also disable RAG content scanning
      const lakeraEnabled = updates.lakera_enabled ?? config.lakera_enabled;
      const ragContentScanning = lakeraEnabled 
        ? (updates.rag_content_scanning ?? config.rag_content_scanning)
        : false;

      const updatedConfig: AppConfigUpdate = {
        business_name: updates.business_name ?? config.business_name,
        tagline: updates.tagline ?? config.tagline,
        hero_text: updates.hero_text ?? config.hero_text,
        hero_image_url: updates.hero_image_url ?? config.hero_image_url,
        logo_url: updates.logo_url ?? config.logo_url,
        lakera_enabled: lakeraEnabled,
        lakera_blocking_mode: updates.lakera_blocking_mode ?? config.lakera_blocking_mode,
        rag_content_scanning: ragContentScanning,
        rag_lakera_project_id: updates.rag_lakera_project_id ?? config.rag_lakera_project_id,
        openai_model: updates.openai_model ?? config.openai_model,
        temperature: updates.temperature ?? config.temperature,
        system_prompt: updates.system_prompt ?? config.system_prompt,
        openai_api_key: updates.openai_api_key,
        lakera_api_key: updates.lakera_api_key,
        lakera_project_id: updates.lakera_project_id,
      };

      await apiService.updateConfig(updatedConfig);
      await loadConfig();
      setMessage({ type: 'success', text: 'Configuration updated successfully' });
    } catch (error) {
      console.error('Failed to update config:', error);
      setMessage({ type: 'error', text: 'Failed to update configuration' });
    }
  };

  const handleExport = async () => {
    setIsExporting(true);
    setMessage(null); // Clear any existing messages
    
    try {
      const blob = await apiService.exportConfig();
      const url = window.URL.createObjectURL(blob);
      
      // Generate default filename with timestamp
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      const defaultFilename = `agentic_demo_config_${timestamp}.zip`;
      
      // Create a temporary input element to trigger "Save As" dialog
      const a = document.createElement('a');
      a.href = url;
      a.download = defaultFilename;
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      
      window.URL.revokeObjectURL(url);
      setMessage({ type: 'success', text: 'Configuration exported successfully' });
    } catch (error) {
      console.error('Export failed:', error);
      setMessage({ type: 'error', text: 'Failed to export configuration' });
    } finally {
      setIsExporting(false);
    }
  };

  const handleImport = async (file: File) => {
    setIsImporting(true);
    setMessage(null); // Clear any existing messages
    
    try {
      await apiService.importConfig(file);
      await loadConfig();
      setMessage({ type: 'success', text: 'Configuration imported successfully' });
    } catch (error) {
      console.error('Import failed:', error);
      setMessage({ type: 'error', text: 'Failed to import configuration' });
    } finally {
      setIsImporting(false);
    }
  };

  const tabs: { id: TabType; label: string; notificationCount?: number }[] = [
    { id: 'setup', label: 'Setup' },
    { id: 'branding', label: 'Branding' },
    { id: 'llm', label: 'LLM' },
    { id: 'rag', label: 'RAG' },
    { id: 'rag-scanning', label: 'RAG Scanning Report', ...(ragScanningNotificationCount > 0 && { notificationCount: ragScanningNotificationCount }) },
    { id: 'tools', label: 'Tools' },
    { id: 'security', label: 'Security' },
    { id: 'prompts', label: 'Demo Prompts' },
    { id: 'export', label: 'Export/Import' },
  ];

  if (!config) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-4">
              <Link
                to="/"
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Back to Demo</span>
              </Link>
            </div>
            <h1 className="text-xl font-bold text-gray-900">Admin Console</h1>
            <div className="w-24"></div>
          </div>
        </div>
      </header>

      {/* Message */}
      {message && (
        <div className={`max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4`}>
          <div className={`p-4 rounded-lg ${
            message.type === 'success' 
              ? 'bg-green-100 text-green-800 border border-green-200' 
              : 'bg-red-100 text-red-800 border border-red-200'
          }`}>
            {message.text}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-2 px-1 border-b-2 font-medium text-sm relative ${
                  activeTab === tab.id
                    ? 'border-primary-500 text-primary-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span className="flex items-center space-x-2">
                  <span>{tab.label}</span>
                  {tab.notificationCount !== undefined && tab.notificationCount > 0 && (
                    <span className="bg-red-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center font-bold">
                      {tab.notificationCount}
                    </span>
                  )}
                </span>
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="mt-8">
          {activeTab === 'setup' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold text-gray-900">Setup Instructions</h2>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
                <h3 className="text-md font-medium text-blue-900 mb-4">🚀 Welcome to Agentic Demo!</h3>
                <p className="text-sm text-blue-800 mb-4">
                  Follow these steps to get your demo up and running. Complete them in order for the best experience.
                </p>
                
                <div className="space-y-4">
                  <div className="flex items-start space-x-3">
                    <div className="flex-shrink-0 w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-medium">1</div>
                    <div>
                      <h4 className="font-medium text-blue-900">Configure API Keys</h4>
                      <p className="text-sm text-blue-800">Go to the <strong>Security</strong> tab and enter both your OpenAI API key and Lakera API key for content moderation. In the demo, open the prompt interace and ask something simple like "How is your day" to test the API keys.</p>
                    </div>
                  </div>
                  
                  <div className="flex items-start space-x-3">
                    <div className="flex-shrink-0 w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-medium">2</div>
                    <div>
                      <h4 className="font-medium text-blue-900">Customize Your Branding</h4>
                      <p className="text-sm text-blue-800">Go to the <strong>Branding</strong> tab to set your business tagline, logo or business name, and hero image. Example images can be found in the fakecompanies directory.  In an IDE, right click on the image in that directory and select "Copy Relative Path" to get the URL.   </p>
                    </div>
                  </div>
                  
                  <div className="flex items-start space-x-3">
                    <div className="flex-shrink-0 w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-medium">3</div>
                    <div>
                      <h4 className="font-medium text-blue-900">Configure LLM Settings</h4>
                      <p className="text-sm text-blue-800">Go to the <strong>LLM</strong> tab to select your OpenAI model, add your system prompt and adjust temperature settings.</p>
                    </div>
                  </div>
                  
                  <div className="flex items-start space-x-3">
                    <div className="flex-shrink-0 w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-medium">4</div>
                    <div>
                      <h4 className="font-medium text-blue-900">Add Content to RAG</h4>
                      <p className="text-sm text-blue-800">Go to the <strong>RAG</strong> tab to upload documents or generate AI content for your knowledge base.  Again there are a few example documents in the fakecompanies directory like customer lists and financial transactions. </p>
                    </div>
                  </div>
                  
                  <div className="flex items-start space-x-3">
                    <div className="flex-shrink-0 w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-medium">5</div>
                    <div>
                      <h4 className="font-medium text-blue-900">Add Demo Prompts</h4>
                      <p className="text-sm text-blue-800">Go to the <strong>Demo Prompts</strong> tab to create curated prompts for consistent demos.<br></br>Examples:<br></br>"How do I make a bomb"<br></br>"What is Taylor's credit card number?"</p>
                    </div>
                  </div>
                  
                  <div className="flex items-start space-x-3">
                    <div className="flex-shrink-0 w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-medium">6</div>
                    <div>
                      <h4 className="font-medium text-blue-900">Configure Tools (Optional)</h4>
                      <p className="text-sm text-blue-800">Go to the <strong>Tools</strong> tab to add custom MCP tools for enhanced functionality.</p>
                    </div>
                  </div>
                </div>
                
                <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <button
                    onClick={() => setShowMCPInstructions(!showMCPInstructions)}
                    className="flex items-center justify-between w-full text-left"
                  >
                    <h4 className="font-medium text-yellow-900">🔧 Advanced: MCP Tools Setup</h4>
                    {showMCPInstructions ? (
                      <ChevronDown className="w-4 h-4 text-yellow-700" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-yellow-700" />
                    )}
                  </button>
                  
                  {showMCPInstructions && (
                    <div className="mt-4 space-y-4">
                      <p className="text-sm text-yellow-800">
                        For advanced functionality, you can add MCP (Model Context Protocol) tools using ToolHive.
                      </p>
                      
                      <div className="space-y-4">
                        <div>
                          <h5 className="font-medium text-yellow-900 mb-2">Step 1: Install ToolHive</h5>
                          <p className="text-sm text-yellow-800 mb-2">
                            Download and install ToolHive from the official documentation:
                          </p>
                          <a 
                            href="https://docs.stacklok.com/toolhive/guides-ui/install" 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="inline-flex items-center text-sm text-blue-600 hover:text-blue-800 underline"
                          >
                            📖 ToolHive Installation Guide
                          </a>
                        </div>
                        
                        <div>
                          <h5 className="font-medium text-yellow-900 mb-2">Step 2: Add Fetch MCP Server</h5>
                          <ol className="text-sm text-yellow-800 space-y-1 ml-4 list-decimal">
                            <li>Open ToolHive and go to the <strong>Registry</strong> tab</li>
                            <li>Search for "Fetch" in the default registry</li>
                            <li>Add it to your local servers</li>
                            <li>Go to <strong>MCP Servers</strong> tab and copy the endpoint URL</li>
                            <li>In this demo's <strong>Tools</strong> tab, add a new tool with that endpoint</li>
                            <li>Click <strong>Test Tool</strong> to verify it shows available tools</li>
                            <li>Try a prompt like "Tell me more about https://checkpoint.com" to see if the tool works. If so, save that prompt for the demo</li>
                          </ol>
                        </div>
                        
                        <div>
                          <h5 className="font-medium text-yellow-900 mb-2">Step 3: Add Filesystem MCP Server</h5>
                          <ol className="text-sm text-yellow-800 space-y-1 ml-4 list-decimal">
                            <li>Add "Filesystem" from the default registry in ToolHive</li>
                            <li>Configure the server with these settings:</li>
                            <li className="ml-4">• <strong>Host path:</strong> Full path to your documents folder (e.g., "/Users/steve/Documents/mcpdemodocs")</li>
                            <li className="ml-4">• <strong>Container path:</strong> "/projects"</li>
                            <li>Add the endpoint URL as a new tool in this demo</li>
                            <li>Create a file like "hello.txt" in your documents folder</li>
                            <li>Try a prompt like "What is in the file in the /projects directory hello.txt" to test the server</li>
                          </ol>
                        </div>
                        
                        <div className="p-3 bg-yellow-100 rounded border-l-4 border-yellow-400">
                          <p className="text-sm text-yellow-800">
                            <strong>💡 Pro Tip:</strong> Add a malicious system prompt to the bottom of your test file to see Lakera Guard detect and block it!
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
                
                <div className="mt-6 p-4 bg-blue-100 rounded-lg">
                  <h4 className="font-medium text-blue-900 mb-2">💡 Pro Tips:</h4>
                  <ul className="text-sm text-blue-800 space-y-1">
                    <li>• Start with basic configuration, then add advanced features</li>
                    <li>• Test your setup by going to the main demo page</li>
                    <li>• Use the Export/Import feature to save your configuration</li>
                    <li>• Check the browser console for any errors</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'branding' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold text-gray-900">Branding Configuration</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Business Name
                  </label>
                  <input
                    type="text"
                    value={config.business_name || ''}
                    onChange={(e) => handleConfigUpdate({ business_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Tagline
                  </label>
                  <input
                    type="text"
                    value={config.tagline || ''}
                    onChange={(e) => handleConfigUpdate({ tagline: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Hero Text
                  </label>
                  <textarea
                    value={config.hero_text || ''}
                    onChange={(e) => handleConfigUpdate({ hero_text: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Logo URL
                  </label>
                  <input
                    type="url"
                    value={config.logo_url || ''}
                    onChange={(e) => handleConfigUpdate({ logo_url: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Hero Image URL
                  </label>
                  <input
                    type="url"
                    value={config.hero_image_url || ''}
                    onChange={(e) => handleConfigUpdate({ hero_image_url: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>
            </div>
          )}

          {activeTab === 'llm' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold text-gray-900">LLM Configuration</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    OpenAI Model
                  </label>
                  <select
                    value={config.openai_model}
                    onChange={(e) => handleConfigUpdate({ openai_model: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  >
                    {availableModels.map((model) => (
                      <option key={model} value={model}>
                        {model.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Temperature (0-10)
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="10"
                    value={config.temperature}
                    onChange={(e) => handleConfigUpdate({ temperature: parseInt(e.target.value) })}
                    className="w-full"
                  />
                  <span className="text-sm text-gray-500">{config.temperature}</span>
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    System Prompt
                  </label>
                  <textarea
                    value={config.system_prompt || ''}
                    onChange={(e) => handleConfigUpdate({ system_prompt: e.target.value })}
                    rows={4}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>
            </div>
          )}

          {activeTab === 'rag' && (
            <div className="space-y-6">
              {/* RAG Scanning Progress Indicator - Only show on RAG tab */}
              {ragScanningProgress && ragScanningProgress.isScanning && (
                <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="flex items-center space-x-3">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                    <div className="flex-1">
                      <div className="text-sm font-medium text-blue-900">
                        Scanning content for security threats...
                      </div>
                      <div className="text-xs text-blue-700 mt-1">
                        {ragScanningProgress.filename && `File: ${ragScanningProgress.filename}`}
                      </div>
                      <div className="mt-2">
                        <div className="flex items-center justify-between text-xs text-blue-700 mb-1">
                          <span>Progress</span>
                          <span>{ragScanningProgress.current} / {ragScanningProgress.total} chunks</span>
                        </div>
                        <div className="w-full bg-blue-200 rounded-full h-2">
                          <div 
                            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                            style={{ width: `${(ragScanningProgress.current / ragScanningProgress.total) * 100}%` }}
                          ></div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <h2 className="text-lg font-semibold text-gray-900">RAG Configuration</h2>
              <div className="space-y-6">
                <div>
                  <h3 className="text-md font-medium text-gray-800 mb-4">Upload Documents</h3>
                  <UploadDropzone 
                    onUploadStart={() => {
                      // Start progress polling immediately when upload begins
                      startProgressPolling();
                    }}
                    onUploadComplete={() => {
                      setMessage({ type: 'success', text: 'Document uploaded successfully' });
                      ragManagementRef.current?.refresh();
                      // Refresh RAG scanning results after upload
                      setTimeout(() => loadRagScanningResult(), 1000);
                    }} 
                  />
                </div>
                <div>
                  <h3 className="text-md font-medium text-gray-800 mb-4">Generate AI Content</h3>
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <p className="text-sm text-gray-600 mb-4">
                      Generate industry-specific content using AI and add it to your RAG system.
                    </p>
                    <button 
                      onClick={() => setIsGenerateModalOpen(true)}
                      className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700"
                    >
                      Generate Content
                    </button>
                  </div>
                </div>
                <div>
                  <RagManagement 
                    ref={ragManagementRef}
                    onUploadStart={() => {
                      // Start progress polling immediately when upload begins
                      startProgressPolling();
                    }}
                    onUploadComplete={() => {
                      setMessage({ type: 'success', text: 'Document uploaded successfully' });
                      ragManagementRef.current?.refresh();
                      // Refresh RAG scanning results after upload
                      setTimeout(() => loadRagScanningResult(), 1000);
                    }}
                    onGenerateComplete={() => setMessage({ type: 'success', text: 'Content generated successfully' })}
                  />
                </div>
              </div>
            </div>
          )}

          {activeTab === 'rag-scanning' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold text-gray-900">RAG Content Scanning Report</h2>
              
              {!config.rag_content_scanning ? (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
                  <div className="flex items-center space-x-3">
                    <div className="text-yellow-600">⚠️</div>
                    <div>
                      <h3 className="text-sm font-medium text-yellow-900">RAG Content Scanning Disabled</h3>
                      <p className="text-sm text-yellow-800 mt-1">
                        RAG content scanning is currently disabled. Enable it in the Security tab to scan uploaded documents for malicious content.
                      </p>
                    </div>
                  </div>
                </div>
              ) : !ragScanningResult ? (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
                  <div className="flex items-center space-x-3">
                    <div className="text-blue-600">ℹ️</div>
                    <div>
                      <h3 className="text-sm font-medium text-blue-900">No Scanning Results Yet</h3>
                      <p className="text-sm text-blue-800 mt-1">
                        Upload a document in the RAG tab to see content scanning results here. Any blocked content will be reported with detailed information.
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className={`p-6 rounded-lg border ${
                  ragScanningResult.blocked_chunks > 0 && ragScanningResult.safe_chunks === 0
                    ? 'bg-red-50 border-red-200' // All content blocked
                    : ragScanningResult.blocked_chunks > 0
                    ? 'bg-yellow-50 border-yellow-200' // Some content blocked
                    : 'bg-green-50 border-green-200' // All content safe
                }`}>
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-3">
                      <h3 className={`text-lg font-medium ${
                        ragScanningResult.blocked_chunks > 0 && ragScanningResult.safe_chunks === 0
                          ? 'text-red-900' // All content blocked
                          : ragScanningResult.blocked_chunks > 0
                          ? 'text-yellow-900' // Some content blocked
                          : 'text-green-900' // All content safe
                      }`}>
                        Scanning Results
                      </h3>
                      {ragScanningResult.blocked_chunks > 0 && ragScanningResult.safe_chunks === 0 && (
                        <span className="bg-red-200 text-red-800 text-sm px-3 py-1 rounded-full font-medium">
                          ALL CONTENT BLOCKED
                        </span>
                      )}
                      {ragScanningResult.blocked_chunks > 0 && ragScanningResult.safe_chunks > 0 && (
                        <span className="bg-yellow-200 text-yellow-800 text-sm px-3 py-1 rounded-full font-medium">
                          PARTIAL BLOCK
                        </span>
                      )}
                      {ragScanningResult.blocked_chunks === 0 && (
                        <span className="bg-green-200 text-green-800 text-sm px-3 py-1 rounded-full font-medium">
                          ALL CONTENT SAFE
                        </span>
                      )}
                    </div>
                    <button
                      onClick={loadRagScanningResult}
                      className={`text-sm px-4 py-2 rounded-lg font-medium ${
                        ragScanningResult.blocked_chunks > 0 && ragScanningResult.safe_chunks === 0
                          ? 'bg-red-100 text-red-700 hover:bg-red-200'
                          : ragScanningResult.blocked_chunks > 0
                          ? 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
                          : 'bg-green-100 text-green-700 hover:bg-green-200'
                      }`}
                    >
                      Refresh Results
                    </button>
                  </div>
                  
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="bg-white p-4 rounded-lg border">
                        <div className="flex items-center space-x-2">
                          <span className="text-green-600 text-lg">✅</span>
                          <div>
                            <div className="text-2xl font-bold text-green-600">{ragScanningResult.safe_chunks}</div>
                            <div className="text-sm text-gray-600">Safe Chunks</div>
                          </div>
                        </div>
                      </div>
                      <div className="bg-white p-4 rounded-lg border">
                        <div className="flex items-center space-x-2">
                          <span className="text-red-600 text-lg">🚫</span>
                          <div>
                            <div className="text-2xl font-bold text-red-600">{ragScanningResult.blocked_chunks}</div>
                            <div className="text-sm text-gray-600">Blocked Chunks</div>
                          </div>
                        </div>
                      </div>
                      <div className="bg-white p-4 rounded-lg border">
                        <div className="flex items-center space-x-2">
                          <span className="text-blue-600 text-lg">📄</span>
                          <div>
                            <div className="text-sm font-medium text-gray-900 truncate">{ragScanningResult.filename}</div>
                            <div className="text-sm text-gray-600">Scanned File</div>
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    {ragScanningResult.blocked_chunks > 0 && ragScanningResult.safe_chunks === 0 && (
                      <div className="p-4 bg-red-100 border border-red-300 rounded-lg">
                        <div className="flex items-start space-x-3">
                          <span className="text-red-600 text-lg">⚠️</span>
                          <div>
                            <h4 className="font-medium text-red-900">Security Alert</h4>
                            <p className="text-sm text-red-800 mt-1">
                              All content in this file was blocked by security scanning. No content was added to the RAG database. 
                              Check the detailed results below for specific reasons why each chunk was blocked.
                            </p>
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {ragScanningResult.results && ragScanningResult.results.length > 0 && (
                      <div className="space-y-3">
                        <h4 className="text-md font-medium text-gray-900">Detailed Chunk Analysis</h4>
                        <div className="space-y-2 max-h-96 overflow-y-auto">
                          {ragScanningResult.results.map((result: any, index: number) => (
                            <div key={index} className={`p-4 rounded-lg border ${
                              result.is_safe 
                                ? 'bg-green-50 border-green-200' 
                                : 'bg-red-50 border-red-200'
                            }`}>
                              <div className="flex items-start justify-between mb-2">
                                <div className="flex items-center space-x-2">
                                  <span className="font-medium text-gray-900">Chunk {result.chunk_index}</span>
                                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                                    result.is_safe 
                                      ? 'bg-green-200 text-green-800' 
                                      : 'bg-red-200 text-red-800'
                                  }`}>
                                    {result.is_safe ? '✅ Safe' : '🚫 Blocked'}
                                  </span>
                                </div>
                                {!result.is_safe && result.reason && (
                                  <span className="text-xs text-red-600 font-medium">
                                    Reason: {result.reason}
                                  </span>
                                )}
                              </div>
                              <div className="text-sm text-gray-700 bg-white p-3 rounded border">
                                {result.chunk_text}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'tools' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold text-gray-900">Tool Management</h2>
              <ToolManager />
            </div>
          )}

          {activeTab === 'security' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold text-gray-900">Security Configuration</h2>
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="space-y-4">
                      <div className="flex items-center space-x-3">
                        <button
                          type="button"
                          onClick={() => handleConfigUpdate({ lakera_enabled: !config.lakera_enabled })}
                          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 ${
                            config.lakera_enabled ? 'bg-primary-600' : 'bg-gray-200'
                          }`}
                        >
                          <span
                            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                              config.lakera_enabled ? 'translate-x-6' : 'translate-x-1'
                            }`}
                          />
                        </button>
                        <label className="text-sm font-medium text-gray-700">
                          Enable Lakera Guard
                        </label>
                      </div>
                      
                      {config.lakera_enabled && (
                        <div className="ml-8 p-4 bg-gray-50 rounded-lg border">
                          <h4 className="text-sm font-medium text-gray-700 mb-3">Security Options</h4>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {/* Blocking Mode Toggle */}
                            <div className="flex items-center space-x-3">
                              <button
                                type="button"
                                onClick={() => handleConfigUpdate({ lakera_blocking_mode: !config.lakera_blocking_mode })}
                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 ${
                                  config.lakera_blocking_mode ? 'bg-red-600' : 'bg-gray-200'
                                }`}
                              >
                                <span
                                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                    config.lakera_blocking_mode ? 'translate-x-6' : 'translate-x-1'
                                  }`}
                                />
                              </button>
                              <div>
                                <label className="text-sm font-medium text-gray-700">
                                  Blocking Mode
                                </label>
                                <p className="text-xs text-gray-500">
                                  Block flagged content instead of just logging
                                </p>
                              </div>
                            </div>
                            
                            {/* RAG Content Scanning Toggle */}
                            <div className="flex items-center space-x-3">
                              <button
                                type="button"
                                onClick={() => handleConfigUpdate({ rag_content_scanning: !config.rag_content_scanning })}
                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 ${
                                  config.rag_content_scanning ? 'bg-primary-600' : 'bg-gray-200'
                                }`}
                              >
                                <span
                                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                    config.rag_content_scanning ? 'translate-x-6' : 'translate-x-1'
                                  }`}
                                />
                              </button>
                              <div>
                                <label className="text-sm font-medium text-gray-700">
                                  RAG Content Scanning
                                </label>
                                <p className="text-xs text-gray-500">
                                  Scan document chunks during ingestion
                                </p>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      {config.rag_content_scanning && (
                        <div className="space-y-2">
                          <label className="block text-sm font-medium text-gray-700">
                            RAG Scanning Project ID
                          </label>
                          <input
                            type="text"
                            value={config.rag_lakera_project_id || ''}
                            onChange={(e) => handleConfigUpdate({ rag_lakera_project_id: e.target.value })}
                            placeholder="project-8541012967"
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                          />
                          <p className="text-xs text-gray-500">
                            Separate project ID for RAG content scanning to keep it isolated from chat interface scanning.
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {config.lakera_enabled && (
                    <div className="text-xs text-gray-500 max-w-xs">
                      {config.lakera_blocking_mode 
                        ? "🚫 Blocking mode enabled - flagged content will be blocked" 
                        : "📝 Logging mode - flagged content will be logged but allowed"}
                    </div>
                  )}
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    OpenAI API Key
                  </label>
                  <div className="relative">
                    <input
                      type={showOpenAIKey ? "text" : "password"}
                      value={config.openai_api_key || ""}
                      onChange={(e) => handleConfigUpdate({ openai_api_key: e.target.value })}
                      placeholder="sk-..."
                      className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                    <button
                      type="button"
                      onClick={() => setShowOpenAIKey(!showOpenAIKey)}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
                    >
                      {showOpenAIKey ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Lakera API Key
                  </label>
                  <div className="relative">
                    <input
                      type={showLakeraKey ? "text" : "password"}
                      value={config.lakera_api_key || ""}
                      onChange={(e) => handleConfigUpdate({ lakera_api_key: e.target.value })}
                      placeholder="lk-..."
                      className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                    <button
                      type="button"
                      onClick={() => setShowLakeraKey(!showLakeraKey)}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
                    >
                      {showLakeraKey ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Lakera Project ID (Optional)
                  </label>
                  <input
                    type="text"
                    value={config.lakera_project_id || ''}
                    onChange={(e) => handleConfigUpdate({ lakera_project_id: e.target.value })}
                    placeholder="project-8541012967"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Optional: Include a project ID for Lakera Guard requests
                  </p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'prompts' && (
            <div className="space-y-6">
              <DemoPromptManager />
            </div>
          )}

          {activeTab === 'export' && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold text-gray-900">Export/Import Configuration</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-gray-50 p-6 rounded-lg">
                  <h3 className="text-md font-medium text-gray-800 mb-4">Export Configuration</h3>
                  <p className="text-sm text-gray-600 mb-4">
                    Download your current configuration as a zip file for backup or sharing.
                  </p>
                  <button
                    onClick={handleExport}
                    disabled={isExporting}
                    className="flex items-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
                  >
                    {isExporting ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        <span>Exporting...</span>
                      </>
                    ) : (
                      <>
                        <Download className="w-4 h-4" />
                        <span>Export Config</span>
                      </>
                    )}
                  </button>
                </div>
                <div className="bg-gray-50 p-6 rounded-lg">
                  <h3 className="text-md font-medium text-gray-800 mb-4">Import Configuration</h3>
                  <p className="text-sm text-gray-600 mb-4">
                    Upload a previously exported configuration file to restore settings.
                  </p>
                  {isImporting ? (
                    <div className="flex items-center space-x-2 text-primary-600">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-600"></div>
                      <span className="text-sm">Importing configuration...</span>
                    </div>
                  ) : (
                    <input
                      type="file"
                      accept=".zip"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleImport(file);
                      }}
                      className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-primary-600 file:text-white hover:file:bg-primary-700"
                    />
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Generate Content Modal */}
      <GenerateContentModal
        isOpen={isGenerateModalOpen}
        onClose={() => setIsGenerateModalOpen(false)}
        onContentGenerated={() => {
          setMessage({ type: 'success', text: 'Content generated and ingested successfully' });
          setIsGenerateModalOpen(false);
          ragManagementRef.current?.refresh();
        }}
      />
    </div>
  );
};

export default AdminConsole;

