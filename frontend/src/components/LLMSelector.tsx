import React, { useState, useEffect } from 'react';
import { Settings, Check, RefreshCw, Zap, ChevronDown, ChevronUp } from 'lucide-react';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

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

const LLMSelector: React.FC<LLMSelectorProps> = ({ className = "", compact = false }) => {
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
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant={compact ? "ghost" : "secondary"}
          size="sm"
          className={`${compact ? "h-auto px-1 py-0 text-xs" : "gap-1.5 text-xs"} ${className}`}
        >
          {compact ? (
            <>
              <span className="font-medium">
                {config ? `${config.provider}:${config.model}` : 'LLM'}
              </span>
              {isOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </>
          ) : (
            <>
              <Settings className="w-3 h-3" />
              <span className="hidden sm:inline">
                {config ? `${config.provider}:${config.model}` : 'LLM'}
              </span>
            </>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-3 space-y-3">
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-popover-foreground">LLM Configuration</h3>
          <p className="text-xs text-muted-foreground">
            Choose the provider and model used by the agent.
          </p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-6 text-xs text-muted-foreground">
            <RefreshCw className="w-4 h-4 animate-spin text-primary mr-2" />
            Loading...
          </div>
        ) : config ? (
          <div className="space-y-3">
            <div className="p-2 bg-muted rounded-md">
              <div className="text-xs font-medium text-foreground">Current</div>
              <div className="text-sm font-semibold text-primary">
                {config.provider} - {config.model}
              </div>
            </div>

            <div className="space-y-2">
              <div>
                <Label className="text-xs">Provider</Label>
                <Select
                  value={selectedProvider || undefined}
                  onValueChange={(value) => {
                    setSelectedProvider(value);
                    setSelectedModel('');
                  }}
                >
                  <SelectTrigger className="h-8">
                    <SelectValue placeholder="Select provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {config.available_providers.map((provider) => (
                      <SelectItem key={provider} value={provider}>
                        {getProviderConfig(provider).label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {selectedProvider && config.available_models[selectedProvider] && (
                <div>
                  <Label className="text-xs">Model</Label>
                  <Select
                    value={selectedModel || undefined}
                    onValueChange={(value) => setSelectedModel(value)}
                  >
                    <SelectTrigger className="h-8">
                      <SelectValue placeholder="Select model" />
                    </SelectTrigger>
                    <SelectContent>
                      {config.available_models[selectedProvider].map((model) => (
                        <SelectItem key={model} value={model}>
                          {model}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>

            {selectedProvider && (
              <div className="space-y-2">
                {getProviderConfig(selectedProvider).needsApiKey && (
                  <div className="space-y-1">
                    <Label className="text-xs">API Key (optional if set in env)</Label>
                    <Input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder={getProviderConfig(selectedProvider).placeholder}
                      className="h-8 text-xs"
                    />
                  </div>
                )}
                {getProviderConfig(selectedProvider).needsBaseUrl && (
                  <div className="space-y-1">
                    <Label className="text-xs">Base URL (optional if set in env)</Label>
                    <Input
                      type="text"
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      placeholder={getProviderConfig(selectedProvider).placeholder}
                      className="h-8 text-xs"
                    />
                  </div>
                )}
                {getProviderConfig(selectedProvider).needsGroqKey && (
                  <div className="space-y-1">
                    <Label className="text-xs">Groq API Key (optional if set in env)</Label>
                    <Input
                      type="password"
                      value={groqApiKey}
                      onChange={(e) => setGroqApiKey(e.target.value)}
                      placeholder={getProviderConfig(selectedProvider).placeholder}
                      className="h-8 text-xs"
                    />
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-2 pt-2">
              <Button
                className="flex-1 gap-1 text-xs"
                onClick={switchLLM}
                disabled={switching || !selectedProvider || !selectedModel}
              >
                {switching ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                Switch
              </Button>
              <Button
                variant="outline"
                className="gap-1 text-xs"
                onClick={testLLM}
                disabled={testing}
              >
                {testing ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
              </Button>
            </div>

            {lastSwitchResult && (
              <div
                className={`p-2 rounded-md text-xs ${
                  lastSwitchResult.status === 'success'
                    ? 'bg-green-500/10 text-green-600 dark:text-green-400 border border-green-500/20'
                    : 'bg-destructive/10 text-destructive border border-destructive/20'
                }`}
              >
                {lastSwitchResult.message}
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-6 text-muted-foreground text-xs">
            Failed to load configuration
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
};

export default LLMSelector;
