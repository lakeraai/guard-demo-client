import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Settings, Shield } from 'lucide-react';
import ChatWidget from '../components/ChatWidget';
import LakeraOverlay from '../components/LakeraOverlay';
import { AppConfig } from '../types';
import { apiService } from '../services/api';

const LandingPage: React.FC = () => {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [isLakeraOverlayOpen, setIsLakeraOverlayOpen] = useState(false);
  const [isLakeraEnabled, setIsLakeraEnabled] = useState(false);
  const [isChatExpanded, setIsChatExpanded] = useState(false);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const configData = await apiService.getConfig();
      setConfig(configData);
      setIsLakeraEnabled(configData.lakera_enabled);
    } catch (error) {
      console.error('Failed to load config:', error);
    }
  };

  const handleLakeraToggle = (enabled: boolean) => {
    setIsLakeraOverlayOpen(enabled);
  };

  const handleOpenChat = () => {
    setIsChatExpanded(true);
  };

  if (!config) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-4">
              {config.logo_url && (
                <img 
                  src={config.logo_url} 
                  alt="Logo" 
                  className="h-8 w-auto"
                />
              )}
              <div>
                <h1 className="text-xl font-bold text-gray-900">
                  {config.business_name}
                </h1>
                <p className="text-sm text-gray-600">{config.tagline}</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              {/* Lakera Status Indicator */}
              <div className="flex items-center space-x-2">
                <Shield className={`w-5 h-5 ${isLakeraEnabled ? 'text-green-600' : 'text-gray-400'}`} />
                <span className="text-sm text-gray-600">
                  {isLakeraEnabled ? 'Guard Active' : 'Guard Inactive'}
                </span>
              </div>
              
              {/* Admin Link */}
              <Link
                to="/admin"
                className="flex items-center space-x-2 px-3 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <Settings className="w-4 h-4" />
                <span>About Us</span>
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
          {/* Hero Text - Left Side */}
          <div className="text-right">
            <h2 className="text-4xl font-bold text-gray-900 mb-6">
              {config.business_name}
            </h2>
            
            <p className="text-[1.75rem] text-gray-600 mb-8 leading-relaxed">
              {config.hero_text}
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-end">
              <button 
                onClick={handleOpenChat}
                className="bg-primary-600 text-white px-6 py-3 rounded-lg hover:bg-primary-700 transition-colors font-medium"
              >
                Get Started
              </button>
              <button 
                onClick={handleOpenChat}
                className="border border-gray-300 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-50 transition-colors font-medium"
              >
                Learn More
              </button>
            </div>
          </div>

          {/* Hero Image - Right Side */}
          {config.hero_image_url && (
            <div className="flex justify-start">
              <img
                src={config.hero_image_url}
                alt="Hero"
                className="h-[25rem] w-auto rounded-lg shadow-lg"
              />
            </div>
          )}
        </div>

        {/* Features Section */}
        <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="text-center">
            <div className="bg-primary-100 w-12 h-12 rounded-lg flex items-center justify-center mx-auto mb-4">
              <Shield className="w-6 h-6 text-primary-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              AI-Powered Security
            </h3>
            <p className="text-gray-600">
              Advanced content moderation and guardrails powered by Lakera Guard.
            </p>
          </div>
          
          <div className="text-center">
            <div className="bg-primary-100 w-12 h-12 rounded-lg flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Secure RAG System
            </h3>
            <p className="text-gray-600">
              AI-powered content for Lakera-protected intelligent responses.
            </p>
          </div>
          
          <div className="text-center">
            <div className="bg-primary-100 w-12 h-12 rounded-lg flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Tool Integration
            </h3>
            <p className="text-gray-600">
              Confidently integrate with external MCP tools and APIs via ToolHive.
            </p>
          </div>
        </div>
      </main>

      {/* Chat Widget */}
      <ChatWidget 
        onLakeraToggle={handleLakeraToggle}
        forceExpanded={isChatExpanded}
        onExpandedChange={setIsChatExpanded}
        config={config}
      />

      {/* Lakera Overlay */}
      <LakeraOverlay 
        isOpen={isLakeraOverlayOpen} 
        onClose={() => setIsLakeraOverlayOpen(false)} 
      />
    </div>
  );
};

export default LandingPage;

