import React, { useState, useEffect, useRef } from 'react';
import { Settings, Check, X, RefreshCw, Zap, ChevronDown, ChevronUp } from 'lucide-react';

interface LLMConfig {
  provider: string;
  model: string;
  available_providers: string[];
  available_models: Record<string, string[]>;
}

interface LLMSelectorProps {
  className?: string;
  compact?: boolean; // renders a minimal trigger suitable for inline placement
}

const MENU_WIDTH_PX = 288; // ~w-72
const MENU_MARGIN_PX = 8;

const LLMSelector: React.FC<LLMSelectorProps> = ({ className = "", compact = false }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [testing, setTesting] = useState(false);

  // Popover positioning
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [placeUp, setPlaceUp] = useState(false);
  const [alignLeft, setAlignLeft] = useState(true);
  
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

  // Positioning logic on open/resize
  useEffect(() => {
    const computePlacement = () => {
      if (!triggerRef.current) return;
      const rect = triggerRef.current.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const viewportWidth = window.innerWidth;
      const spaceBelow = viewportHeight - rect.bottom;
      const spaceAbove = rect.top;
      setPlaceUp(spaceBelow < 200 && spaceAbove > spaceBelow); // prefer up if below space is tight

      // Horizontal alignment: prefer left if fits, else switch to right
      const fitsRight = rect.left + MENU_WIDTH_PX <= viewportWidth - MENU_MARGIN_PX;
      const fitsLeft = rect.right - MENU_WIDTH_PX >= MENU_MARGIN_PX;
      if (compact) {
        // Compact defaults to left; flip if it overflows right
        setAlignLeft(fitsRight || !fitsLeft);
      } else {
        // Non-compact defaults to right; flip if it overflows left
        setAlignLeft(!(fitsLeft || !fitsRight));
      }
    };

    if (isOpen) {
      computePlacement();
      const onResize = () => computePlacement();
      window.addEventListener('resize', onResize);
      window.addEventListener('scroll', onResize, true);
      return () => {
        window.removeEventListener('resize', onResize);
        window.removeEventListener('scroll', onResize, true);
      };
    }
  }, [isOpen, compact]);

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
        ref={triggerRef}
        onClick={() => setIsOpen(!isOpen)}
        className={compact
          ? "flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          : "flex items-center gap-1.5 px-2 py-1 text-xs bg-muted hover:bg-accent rounded-md transition-colors"}
        title="LLM Settings"
      >
        {compact ? (
          <>
            <span className="font-medium">{config ? `${config.provider}:${config.model}` : 'LLM'}</span>
            {isOpen ? <ChevronUp className="w-2 h-2" /> : <ChevronDown className="w-2 h-2" />}
          </>
        ) : (
          <>
            <Settings className="w-3 h-3" />
            <span className="hidden sm:inline">
              {config ? `${config.provider}:${config.model}` : 'LLM'}
            </span>
          </>
        )}
      </button>

      {isOpen && (
        <div className={`absolute ${placeUp ? 'bottom-full mb-2' : 'top-full mt-2'} ${alignLeft ? 'left-0' : 'right-0'} w-72 bg-popover border border-border rounded-md shadow-lg z-50`}>
          <div className="p-3">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-popover-foreground text-sm">LLM Configuration</h3>
              <button
                onClick={() => setIsOpen(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="w-3 h-3" />
              </button>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-6">
                <RefreshCw className="w-4 h-4 animate-spin text-primary" />
                <span className="ml-2 text-xs text-muted-foreground">Loading...</span>
              </div>
            ) : config ? (
              <div className="space-y-3">
                {/* Current Status */}
                <div className="p-2 bg-muted rounded-md">
                  <div className="text-xs font-medium text-foreground">Current:</div>
                  <div className="text-sm font-semibold text-primary">
                    {config.provider} - {config.model}
                  </div>
                </div>

                {/* Provider Selection */}
                <div>
                  <label className="block text-xs font-medium text-foreground mb-1">
                    Provider
                  </label>
                  <select
                    value={selectedProvider}
                    onChange={(e) => {
                      setSelectedProvider(e.target.value);
                      setSelectedModel(''); // Reset model when provider changes
                    }}
                    className="w-full px-2 py-1 border border-border rounded-md focus:ring-2 focus:ring-ring focus:border-transparent text-xs bg-background text-foreground"
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
                    <label className="block text-xs font-medium text-foreground mb-1">
                      Model
                    </label>
                    <select
                      value={selectedModel}
                      onChange={(e) => setSelectedModel(e.target.value)}
                      className="w-full px-2 py-1 border border-border rounded-md focus:ring-2 focus:ring-ring focus:border-transparent text-xs bg-background text-foreground"
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
                  <div className="space-y-2">
                    {getProviderConfig(selectedProvider).needsApiKey && (
                      <div>
                        <label className="block text-xs font-medium text-foreground mb-1">
                          API Key (optional if set in env)
                        </label>
                        <input
                          type="password"
                          value={apiKey}
                          onChange={(e) => setApiKey(e.target.value)}
                          placeholder={getProviderConfig(selectedProvider).placeholder}
                          className="w-full px-2 py-1 border border-border rounded-md focus:ring-2 focus:ring-ring focus:border-transparent text-xs bg-background text-foreground"
                        />
                      </div>
                    )}

                    {getProviderConfig(selectedProvider).needsBaseUrl && (
                      <div>
                        <label className="block text-xs font-medium text-foreground mb-1">
                          Base URL (optional if set in env)
                        </label>
                        <input
                          type="text"
                          value={baseUrl}
                          onChange={(e) => setBaseUrl(e.target.value)}
                          placeholder={getProviderConfig(selectedProvider).placeholder}
                          className="w-full px-2 py-1 border border-border rounded-md focus:ring-2 focus:ring-ring focus:border-transparent text-xs bg-background text-foreground"
                        />
                      </div>
                    )}

                    {getProviderConfig(selectedProvider).needsGroqKey && (
                      <div>
                        <label className="block text-xs font-medium text-foreground mb-1">
                          Groq API Key (optional if set in env)
                        </label>
                        <input
                          type="password"
                          value={groqApiKey}
                          onChange={(e) => setGroqApiKey(e.target.value)}
                          placeholder={getProviderConfig(selectedProvider).placeholder}
                          className="w-full px-2 py-1 border border-border rounded-md focus:ring-2 focus:ring-ring focus:border-transparent text-xs bg-background text-foreground"
                        />
                      </div>
                    )}
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex gap-2 pt-2">
                  <button
                    onClick={switchLLM}
                    disabled={switching || !selectedProvider || !selectedModel}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed transition-colors text-xs"
                  >
                    {switching ? (
                      <RefreshCw className="w-3 h-3 animate-spin" />
                    ) : (
                      <Check className="w-3 h-3" />
                    )}
                    Switch
                  </button>
                  
                  <button
                    onClick={testLLM}
                    disabled={testing}
                    className="px-3 py-1.5 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed transition-colors text-xs"
                  >
                    {testing ? (
                      <RefreshCw className="w-3 h-3 animate-spin" />
                    ) : (
                      <Zap className="w-3 h-3" />
                    )}
                  </button>
                </div>

                {/* Status Message */}
                {lastSwitchResult && (
                  <div className={`p-2 rounded-md ${
                    lastSwitchResult.status === 'success' 
                      ? 'bg-green-500/10 text-green-600 dark:text-green-400 border border-green-500/20' 
                      : 'bg-destructive/10 text-destructive border border-destructive/20'
                  }`}>
                    <div className="text-xs">
                      {lastSwitchResult.message}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-6 text-muted-foreground text-xs">
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
