import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, MessageCircle, Minimize2 } from 'lucide-react';
import { ChatMessage, LakeraResult, AppConfig, DemoPromptSuggestion } from '../types';
import { apiService } from '../services/api';

interface ChatWidgetProps {
  onLakeraToggle?: (enabled: boolean) => void;
  forceExpanded?: boolean;
  onExpandedChange?: (expanded: boolean) => void;
  config?: AppConfig | null;
}

const ChatWidget: React.FC<ChatWidgetProps> = ({ onLakeraToggle, forceExpanded, onExpandedChange, config }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [lastLakeraResult, setLastLakeraResult] = useState<LakeraResult | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [suggestions, setSuggestions] = useState<DemoPromptSuggestion[]>([]);
  const [currentSuggestion, setCurrentSuggestion] = useState<DemoPromptSuggestion | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Handle external control of expanded state
  useEffect(() => {
    if (forceExpanded !== undefined) {
      setIsExpanded(forceExpanded);
    }
  }, [forceExpanded]);

  // Notify parent of expanded state changes
  useEffect(() => {
    onExpandedChange?.(isExpanded);
  }, [isExpanded, onExpandedChange]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initialize Lakera result on mount
  useEffect(() => {
    const initializeLakeraResult = async () => {
      try {
        const result = await apiService.getLastLakeraResult();
        setLastLakeraResult(result);
      } catch (error) {
        // No existing Lakera result, that's fine
      }
    };
    initializeLakeraResult();
  }, []);

  const hasLakeraViolations = () => {
    if (!lastLakeraResult) return false;
    return lastLakeraResult.flagged || lastLakeraResult.breakdown?.some(detector => detector.detected);
  };

  // Search for demo prompt suggestions
  const searchSuggestions = async (query: string) => {
    if (query.length < 2) {
      setSuggestions([]);
      setCurrentSuggestion(null);
      setShowSuggestions(false);
      return;
    }

    try {
      const response = await apiService.searchDemoPrompts(query);
      setSuggestions(response.suggestions);
      setCurrentSuggestion(response.suggestions[0] || null);
      setShowSuggestions(response.suggestions.length > 0);
    } catch (error) {
      console.error('Failed to search suggestions:', error);
      setSuggestions([]);
      setCurrentSuggestion(null);
      setShowSuggestions(false);
    }
  };

  // Complete the current suggestion
  const completeSuggestion = () => {
    if (currentSuggestion) {
      setInputMessage(currentSuggestion.full_content);
      setSuggestions([]);
      setCurrentSuggestion(null);
      setShowSuggestions(false);
      inputRef.current?.focus();
    }
  };

  // Handle input change with autocomplete
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInputMessage(value);
    searchSuggestions(value);
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: inputMessage,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await apiService.sendMessage({
        message: inputMessage,
      });

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        tool_traces: response.tool_traces,
        lakera: response.lakera,
      };

      setMessages(prev => [...prev, assistantMessage]);
      
      // Update last Lakera result if available
      if (response.lakera) {
        setLastLakeraResult(response.lakera);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    } else if (e.key === 'ArrowRight' && currentSuggestion) {
      e.preventDefault();
      completeSuggestion();
    } else if (e.key === 'Escape') {
      setSuggestions([]);
      setCurrentSuggestion(null);
      setShowSuggestions(false);
    }
  };

  return (
    <>
      {/* Collapsed Chat Widget */}
      {!isExpanded && (
        <div className="fixed bottom-4 right-4">
          <button
            onClick={() => setIsExpanded(true)}
            className="bg-primary-600 text-white p-4 rounded-full shadow-lg hover:bg-primary-700 transition-colors duration-200 flex items-center justify-center group"
          >
            <MessageCircle className="w-6 h-6" />
            {messages.length > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
                {messages.length}
              </span>
            )}
          </button>
        </div>
      )}

      {/* Expanded Chat Window */}
      {isExpanded && (
        <div className="fixed bottom-4 right-4 w-96 h-[500px] bg-white rounded-lg shadow-xl border border-gray-200 flex flex-col animate-in slide-in-from-bottom-2 duration-300">
          {/* Header */}
          <div className="bg-primary-600 text-white p-4 rounded-t-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Bot className="w-5 h-5" />
                <span className="font-semibold">AI Assistant</span>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => onLakeraToggle?.(true)}
                  className={`text-xs px-2 py-1 rounded ${
                    hasLakeraViolations() 
                      ? 'bg-red-600 hover:bg-red-700' 
                      : 'bg-primary-700 hover:bg-primary-800'
                  }`}
                >
                  {config?.lakera_enabled && config?.lakera_blocking_mode 
                    ? 'Lakera Blocking' 
                    : config?.lakera_enabled 
                      ? 'Lakera Watching' 
                      : 'Lakera'
                  }
                </button>
                <button
                  onClick={() => setIsExpanded(false)}
                  className="text-white hover:bg-primary-700 p-1 rounded transition-colors duration-200"
                  title="Minimize"
                >
                  <Minimize2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="text-center text-gray-500 mt-8">
                <Bot className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                <p>Start a conversation with the AI assistant</p>
              </div>
            )}
            
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                    message.role === 'user'
                      ? 'bg-primary-600 text-white'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  <div className="flex items-start space-x-2">
                    {message.role === 'assistant' && (
                      <Bot className="w-4 h-4 mt-1 flex-shrink-0" />
                    )}
                    <div className="flex-1">
                      <p className="text-sm">{message.content}</p>
                      {message.tool_traces && message.tool_traces.length > 0 && (
                        <div className="mt-2 text-xs text-gray-500">
                          <p>Tools used: {message.tool_traces.length}</p>
                        </div>
                      )}
                    </div>
                    {message.role === 'user' && (
                      <User className="w-4 h-4 mt-1 flex-shrink-0" />
                    )}
                  </div>
                </div>
              </div>
            ))}
            
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 text-gray-800 px-4 py-2 rounded-lg">
                  <div className="flex items-center space-x-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm">Thinking...</span>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t border-gray-200">
            <div className="relative">
              <div className="flex space-x-2">
                <div className="flex-1 relative">
                  <input
                    ref={inputRef}
                    type="text"
                    value={inputMessage}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyPress}
                    placeholder="Type your message..."
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    disabled={isLoading}
                    autoFocus
                  />
                  
                  {/* Autocomplete suggestion overlay */}
                  {showSuggestions && currentSuggestion && (
                    <div className="absolute top-0 left-0 right-0 px-3 py-2 text-gray-400 pointer-events-none">
                      <span className="text-transparent">{inputMessage}</span>
                      <span className="text-gray-400">{currentSuggestion.text.substring(inputMessage.length)}</span>
                      <span className="text-xs ml-2 text-gray-500">
                        Press → to complete
                      </span>
                    </div>
                  )}
                </div>
                <button
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || isLoading}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
              
              {/* Suggestions dropdown */}
              {showSuggestions && suggestions.length > 0 && (
                <div className="absolute bottom-full left-0 right-0 mb-2 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto z-10">
                  {suggestions.map((suggestion, index) => (
                    <div
                      key={index}
                      className={`px-3 py-2 cursor-pointer hover:bg-gray-50 border-b border-gray-100 last:border-b-0 ${
                        index === 0 ? 'bg-blue-50' : ''
                      }`}
                      onClick={() => {
                        setInputMessage(suggestion.full_content);
                        setSuggestions([]);
                        setCurrentSuggestion(null);
                        setShowSuggestions(false);
                        inputRef.current?.focus();
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="text-sm font-medium text-gray-900">{suggestion.title}</div>
                          <div className="text-xs text-gray-500 truncate">{suggestion.text}</div>
                        </div>
                        <div className="flex items-center space-x-1 ml-2">
                          {suggestion.is_malicious && (
                            <span className="text-xs text-red-600">⚠️</span>
                          )}
                          <span className={`text-xs px-2 py-1 rounded ${
                            suggestion.category === 'security' ? 'bg-red-100 text-red-800' :
                            suggestion.category === 'malicious' ? 'bg-red-100 text-red-800' :
                            suggestion.category === 'tools' ? 'bg-blue-100 text-blue-800' :
                            suggestion.category === 'rag' ? 'bg-green-100 text-green-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {suggestion.category}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ChatWidget;

