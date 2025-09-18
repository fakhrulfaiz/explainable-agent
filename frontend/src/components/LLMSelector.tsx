import React, { useState, useEffect } from 'react';
import { Settings, Check, X, RefreshCw, Zap } from 'lucide-react';

interface LLMConfig {
  provider: string;
  model: string;
  available_providers: string[];
  available_models: Record<string, string[]>;
}

interface LLMSelectorProps {
  className?: string;
}

const LLMSelector: React.FC<LLMSelectorProps> = ({ className = "" }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [testing, setTesting] = useState(false);
  
  // Form state
  const [selectedProvider, setSelectedProvider] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [groqApiKey, setGroqApiKey] = useState('');
  
  // Status
  const [lastSwitchResult, setLastSwitchResult] = useState<{status: string, message: string} | null>(null);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/llm/config');
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
        setSelectedProvider(data.provider);
        setSelectedModel(data.model);
      }
    } catch (error) {
      console.error('Failed to fetch LLM config:', error);
    }
    setLoading(false);
  };

  const switchLLM = async () => {
    setSwitching(true);
    setLastSwitchResult(null);
    
    try {
      const payload: any = {
        provider: selectedProvider,
        model: selectedModel
      };
      
      // Add credentials based on provider
      if (selectedProvider === 'openai' && apiKey) {
        payload.api_key = apiKey;
      } else if (selectedProvider === 'ollama' && baseUrl) {
        payload.base_url = baseUrl;
      } else if (selectedProvider === 'deepseek' && apiKey) {
        payload.api_key = apiKey;
      } else if (selectedProvider === 'groq' && groqApiKey) {
        payload.groq_api_key = groqApiKey;
      }
      
      const response = await fetch('/api/llm/switch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
      });
      
      const result = await response.json();
      
      if (response.ok) {
        setLastSwitchResult({ status: 'success', message: result.message });
        await fetchConfig(); // Refresh config
        // Clear sensitive fields
        setApiKey('');
        setBaseUrl('');
        setGroqApiKey('');
      } else {
        setLastSwitchResult({ status: 'error', message: result.detail || 'Switch failed' });
      }
    } catch (error) {
      setLastSwitchResult({ status: 'error', message: `Network error: ${error}` });
    }
    
    setSwitching(false);
  };

  const testLLM = async () => {
    setTesting(true);
    try {
      const response = await fetch('/api/llm/test');
      const result = await response.json();
      
      if (response.ok) {
        setLastSwitchResult({ 
          status: 'success', 
          message: `Test successful! Response: ${result.response}` 
        });
      } else {
        setLastSwitchResult({ status: 'error', message: result.detail || 'Test failed' });
      }
    } catch (error) {
      setLastSwitchResult({ status: 'error', message: `Test failed: ${error}` });
    }
    setTesting(false);
  };

  useEffect(() => {
    if (isOpen && !config) {
      fetchConfig();
    }
  }, [isOpen]);

  const getProviderConfig = (provider: string) => {
    const configs: Record<string, { 
      label: string; 
      needsApiKey?: boolean; 
      needsBaseUrl?: boolean; 
      needsGroqKey?: boolean; 
      placeholder?: string;
    }> = {
      openai: { label: 'OpenAI', needsApiKey: true, placeholder: 'sk-...' },
      ollama: { label: 'Ollama', needsBaseUrl: true, placeholder: 'http://localhost:11434' },
      deepseek: { label: 'DeepSeek', needsApiKey: true, placeholder: 'sk-...' },
      groq: { label: 'Groq', needsGroqKey: true, placeholder: 'gsk_...' }
    };
    return configs[provider] || { label: provider };
  };

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
        title="LLM Settings"
      >
        <Settings className="w-4 h-4" />
        <span className="hidden sm:inline">
          {config ? `${config.provider}:${config.model}` : 'LLM'}
        </span>
      </button>

      {isOpen && (
        <div className="absolute top-full right-0 mt-2 w-96 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
          <div className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">LLM Configuration</h3>
              <button
                onClick={() => setIsOpen(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="w-5 h-5 animate-spin text-blue-500" />
                <span className="ml-2 text-sm text-gray-600">Loading...</span>
              </div>
            ) : config ? (
              <div className="space-y-4">
                {/* Current Status */}
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="text-sm font-medium text-gray-700">Current:</div>
                  <div className="text-lg font-semibold text-blue-600">
                    {config.provider} - {config.model}
                  </div>
                </div>

                {/* Provider Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Provider
                  </label>
                  <select
                    value={selectedProvider}
                    onChange={(e) => {
                      setSelectedProvider(e.target.value);
                      setSelectedModel(''); // Reset model when provider changes
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    {config.available_providers.map(provider => (
                      <option key={provider} value={provider}>
                        {getProviderConfig(provider).label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Model Selection */}
                {selectedProvider && config.available_models[selectedProvider] && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Model
                    </label>
                    <select
                      value={selectedModel}
                      onChange={(e) => setSelectedModel(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Select a model</option>
                      {config.available_models[selectedProvider].map(model => (
                        <option key={model} value={model}>
                          {model}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Provider-specific configuration */}
                {selectedProvider && (
                  <div className="space-y-3">
                    {getProviderConfig(selectedProvider).needsApiKey && (
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          API Key (optional if set in env)
                        </label>
                        <input
                          type="password"
                          value={apiKey}
                          onChange={(e) => setApiKey(e.target.value)}
                          placeholder={getProviderConfig(selectedProvider).placeholder}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        />
                      </div>
                    )}

                    {getProviderConfig(selectedProvider).needsBaseUrl && (
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Base URL (optional if set in env)
                        </label>
                        <input
                          type="text"
                          value={baseUrl}
                          onChange={(e) => setBaseUrl(e.target.value)}
                          placeholder={getProviderConfig(selectedProvider).placeholder}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        />
                      </div>
                    )}

                    {getProviderConfig(selectedProvider).needsGroqKey && (
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Groq API Key (optional if set in env)
                        </label>
                        <input
                          type="password"
                          value={groqApiKey}
                          onChange={(e) => setGroqApiKey(e.target.value)}
                          placeholder={getProviderConfig(selectedProvider).placeholder}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        />
                      </div>
                    )}
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex gap-2 pt-4">
                  <button
                    onClick={switchLLM}
                    disabled={switching || !selectedProvider || !selectedModel}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                  >
                    {switching ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <Check className="w-4 h-4" />
                    )}
                    Switch
                  </button>
                  
                  <button
                    onClick={testLLM}
                    disabled={testing}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                  >
                    {testing ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <Zap className="w-4 h-4" />
                    )}
                  </button>
                </div>

                {/* Status Message */}
                {lastSwitchResult && (
                  <div className={`p-3 rounded-lg ${
                    lastSwitchResult.status === 'success' 
                      ? 'bg-green-50 text-green-800 border border-green-200' 
                      : 'bg-red-50 text-red-800 border border-red-200'
                  }`}>
                    <div className="text-sm">
                      {lastSwitchResult.message}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                Failed to load configuration
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default LLMSelector;
