import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { ChevronDown, ChevronRight, Database, Image, Link, Brain, User, Bot, Search, Layers } from 'lucide-react';
import agentLogData from '../data/agentLog.json';

const AgentExplorer = () => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [agentLog, setAgentLog] = useState(null);
  const [expandedNodes, setExpandedNodes] = useState({});
  const [logs, setLogs] = useState([]);
  const [selectedLog, setSelectedLog] = useState('');

  const loadLog = async (filename) => {
    try {
      setLoading(true);
      const url = filename ? `http://localhost:8000/api/log/${encodeURIComponent(filename)}` : 'http://localhost:8000/api/log/latest';
      const res = await axios.get(url);
      if (res && res.data && res.data.steps) {
        setAgentLog(res.data);
        setExpandedNodes({});
      }
    } catch (e) {
      setError(e?.response?.data?.detail || 'Failed to load log');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.post('http://localhost:8000/api/query', { query });
      setAgentLog(response.data);
      setExpandedNodes({});
      // If backend returned the saved filename, reflect it in the selector
      if (response.data?.log_filename) {
        setLogs(prev => [response.data.log_filename, ...prev.filter(n => n !== response.data.log_filename)]);
        setSelectedLog(response.data.log_filename);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred while processing your query');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Load list of logs and latest log on mount; fallback to bundled data
    const fetchLogs = async () => {
      try {
        const res = await axios.get('http://localhost:8000/api/logs');
        if (res && res.data && Array.isArray(res.data.logs)) {
          setLogs(res.data.logs);
          if (res.data.logs.length > 0) {
            setSelectedLog(res.data.logs[0]);
          }
        }
      } catch (_) {
        // ignore if backend not available
      }
    };

    const fetchLatest = async () => {
      try {
        const res = await axios.get('http://localhost:8000/api/log/latest');
        if (res && res.data && res.data.steps) {
          setAgentLog(res.data);
          return;
        }
      } catch (_) {
        // fallback below
      }
      // Fallback to bundled local data
      setAgentLog(agentLogData);
    };

    fetchLogs();
    fetchLatest();
  }, []);

  const onSelectLog = async (e) => {
    const filename = e.target.value;
    setSelectedLog(filename);
    await loadLog(filename);
  };

  const toggleNode = (nodeId) => {
    setExpandedNodes(prev => ({
      ...prev,
      [nodeId]: !prev[nodeId]
    }));
  };

  // Function to clean up formatting in outputs
  const cleanOutput = (text) => {
    if (!text) return text;
    
    // Remove markdown code blocks
    let cleaned = text.replace(/```[\s\S]*?```/g, '');
    
    // Replace \n with actual line breaks for readability
    cleaned = cleaned.replace(/\\n/g, '\n');
    
    // Clean up excessive whitespace but preserve intentional formatting
    cleaned = cleaned.replace(/\n\s*\n\s*\n/g, '\n\n');
    
    return cleaned.trim();
  };

  // Function to determine if content should be displayed as code
  const isCodeContent = (text) => {
    if (!text) return false;
    if (typeof text !== 'string') {
      // If it's an object, you can decide to stringify or just return false
      try {
        text = JSON.stringify(text);
      } catch {
        return false;
      }
    }
    try {
      const parsed = JSON.parse(text);
      return parsed.type === 'table' || 
             parsed.details ||  // Check for SQL result details
             text.includes('CREATE TABLE') || 
             text.includes('SELECT') || 
             text.includes('query') ||
             text.startsWith('[(') ||  // SQL result format
             (text.includes('{') && text.includes('}')); // JSON-like input
    } catch {
      return text.includes('CREATE TABLE') || 
             text.includes('SELECT') || 
             text.includes('```') ||
             text.includes('query') ||
             text.startsWith('[(') ||  // SQL result format
             (text.includes('{') && text.includes('}')); // JSON-like input
    }
  };

  // Function to format code content nicely
  const formatCode = (text) => {
    let formatted = cleanOutput(text);
    
    // If it's a SQL result like [(0,)], make it more readable
    if (formatted.match(/^\[\([^)]*\)\]$/)) {
      const result = formatted.match(/\(([^)]*)\)/)?.[1];
      return `Query Result: ${result}`;
    }
    
    return formatted;
  };

  // Function to render code content with proper styling
  const renderCodeContent = (content) => {
  if (!content) return null;

  try {
    const parsed = typeof content === 'string' ? JSON.parse(content) : content;

    const details = parsed?.details;
    
    if (Array.isArray(details) && details.length > 0 && typeof details[0] === 'object') {
      const columns = Object.keys(details[0]);

      return (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border-collapse">
            <thead>
              <tr>
                {columns.map((column, index) => (
                  <th key={index} className="px-4 py-2 bg-gray-100 border font-medium text-gray-700">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {details.map((row, rowIndex) => (
                <tr key={rowIndex} className={rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                  {columns.map((column, cellIndex) => (
                    <td key={cellIndex} className="px-4 py-2 border text-gray-600">
                      {row[column]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-xs text-gray-500 mt-2">
            Total rows: {details.length}
          </div>
        </div>
      );
    } else if (typeof details === 'string') {
      return details;
    }

  } catch (e) {
    // If JSON parsing fails, fall through to render raw
  }

  // Render as plain code (fallback)
  return (
    <pre className="text-gray-600 text-sm bg-gray-50 p-2 rounded border overflow-x-auto">
      <code>{formatCode(typeof content === 'string' ? content : JSON.stringify(content, null, 2))}</code>
    </pre>
  );
};


  const getToolIcon = (toolType) => {
    switch(toolType) {
      case 'text2SQL': return <Database className="w-4 h-4" />;
      case 'schema_analysis': return <Layers className="w-4 h-4" />;
      case 'data_processing': return <Search className="w-4 h-4" />;
      case 'synthesis': return <Link className="w-4 h-4" />;
      case 'image_analysis': return <Image className="w-4 h-4" />;
      default: return <Brain className="w-4 h-4" />;
    }
  };

  const getToolColor = (toolType) => {
    switch(toolType) {
      case 'text2SQL': return 'bg-blue-500';
      case 'schema_analysis': return 'bg-indigo-500';
      case 'data_processing': return 'bg-orange-500';
      case 'synthesis': return 'bg-purple-500';
      case 'image_analysis': return 'bg-green-500';
      default: return 'bg-gray-500';
    }
  };

  const formatTime = (seconds) => {
    return `${seconds.toFixed(2)}s`;
  };

  const getFinalAnswer = () => {
    if (!agentLog) return null;
    
    // Check if there's a final_structured_result in the log
    if (agentLog.final_structured_result && agentLog.final_structured_result.Summary) {
      return agentLog.final_structured_result.Summary;
    }
    
    // Otherwise, look for a final_result step
    const finalStep = agentLog.steps.find(step => step.type === 'final_result');
    if (finalStep && finalStep.output) {
      try {
        const parsed = JSON.parse(finalStep.output);
        if (parsed.Summary) {
          return parsed.Summary;
        }
      } catch (e) {
        // If parsing fails, use the raw output
        return cleanOutput(finalStep.output);
      }
    }
    
    // Fallback to the last step's output or decision
    const lastStep = agentLog.steps[agentLog.steps.length - 1];
    if (lastStep) {
      if (lastStep.decision) {
        return lastStep.decision;
      }
      if (lastStep.output) {
        return cleanOutput(lastStep.output);
      }
    }
    
    return "Analysis completed - see detailed steps above for the exploration process.";
  };

  const getFinalAnswerDetails = () => {
    if (!agentLog) return null;

    // If there are details, render them as code/table
    if (agentLog.final_structured_result) {
      if (isCodeContent(agentLog.final_structured_result)) {
        return renderCodeContent(agentLog.final_structured_result);
      } else {
        return agentLog.final_structured_result.details;
      }
    }

    // Otherwise, look for a final_result step
    const finalStep = agentLog.steps.find(step => step.type === 'final_result');
    if (finalStep && finalStep.output) {
      try {
       
        if (isCodeContent(finalStep.output)) {
        return renderCodeContent(finalStep.output);
        } else { 
          const parsed = JSON.parse(finalStep.output)
          return parsed.details;
      }
        
      } catch (e) {
        const parsed = JSON.parse(finalStep.output)
        return parsed.details;
      }
      
    }
    
    return finalStep.output;
  };

  return (
    <div className="max-w-6xl mx-auto p-6 bg-gray-50 min-h-screen">
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h1 className="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2">
          <Brain className="w-6 h-6 text-blue-600" />
          LLM Agent Tracker
        </h1>

        {/* Controls Row: Query + Log selector */}
        <div className="mb-6 flex flex-col md:flex-row gap-2">
          <form onSubmit={handleSubmit} className="flex-1 flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter your query..."
              className="flex-1 p-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            >
              {loading ? 'Processing...' : 'Submit'}
            </button>
          </form>

          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-700">Load log:</label>
            <select
              value={selectedLog}
              onChange={onSelectLog}
              className="border rounded px-2 py-2 text-gray-800"
            >
              <option value="">Latest</option>
              {logs.map(name => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
            <button
              onClick={() => loadLog(selectedLog)}
              className="px-3 py-2 rounded bg-gray-100 hover:bg-gray-200 text-gray-800"
            >
              Load
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 rounded-lg border-l-4 border-red-500">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {loading && (
          <div className="flex justify-center items-center py-10">
           <span className="text-lg text-blue-600 font-semibold">Processing...</span>
          </div>
        )}

        {!loading && agentLog && (
          <>
            {/* Query Context */}
            <div className="mb-6 p-4 bg-blue-50 rounded-lg border-l-4 border-blue-500">
              <div className="flex items-center gap-2 mb-2">
                <User className="w-5 h-5 text-blue-600" />
                <span className="font-semibold text-blue-800">User Query:</span>
              </div>
              <p className="text-gray-700 italic">"{agentLog.question}"</p>
            </div>

            {/* Statistics Bar */}
            <div className="mb-6 grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-gray-50 p-3 rounded-lg text-center">
                <div className="text-2xl font-bold text-gray-800">{agentLog.steps.length}</div>
                <div className="text-sm text-gray-600">Total Steps</div>
              </div>
              <div className="bg-green-50 p-3 rounded-lg text-center">
                <div className="text-2xl font-bold text-green-800">{(agentLog.overall_confidence * 100).toFixed(0)}%</div>
                <div className="text-sm text-gray-600">Overall Confidence</div>
              </div>
              <div className="bg-purple-50 p-3 rounded-lg text-center">
                <div className="text-2xl font-bold text-purple-800">{formatTime(agentLog.total_time)}</div>
                <div className="text-sm text-gray-600">Processing Time</div>
              </div>
              <div className="bg-blue-50 p-3 rounded-lg text-center">
                <div className="text-2xl font-bold text-blue-800">LLM</div>
                <div className="text-sm text-gray-600">Explanations</div>
              </div>
            </div>

            {/* Decision Tree */}
            <div className="space-y-4">
              {agentLog.steps.map((step, index) => (
                <div key={step.id} className="relative">
                  {/* Connection Line */}
                  {index > 0 && (
                    <div className="absolute left-6 -top-4 w-0.5 h-4 bg-gray-300"></div>
                  )}
                  
                  {/* Step Node */}
                  <div 
                    className="flex items-start gap-4 p-4 bg-white border border-gray-200 rounded-lg hover:shadow-md transition-shadow cursor-pointer"
                    onClick={() => toggleNode(step.id)}
                  >
                    {/* Step Number and Icon */}
                    <div className="flex-shrink-0">
                      <div className={`w-12 h-12 ${getToolColor(step.type)} rounded-full flex items-center justify-center text-white font-bold relative`}>
                        {getToolIcon(step.type)}
                        <span className="absolute -top-1 -right-1 w-5 h-5 bg-gray-600 rounded-full text-xs flex items-center justify-center">
                          {step.id}
                        </span>
                      </div>
                    </div>

                    {/* Step Content */}
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-semibold text-lg text-gray-800">{step.type}</h3>
                        <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                          {(step.confidence * 100).toFixed(0)}% confidence
                        </span>
                        <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                          LLM-Generated
                        </span>
                        {expandedNodes[step.id] ? 
                          <ChevronDown className="w-4 h-4 text-gray-500" /> : 
                          <ChevronRight className="w-4 h-4 text-gray-500" />
                        }
                      </div>
                      
                      <p className="text-gray-600 mb-2">{step.decision}</p>
                      
                      {/* Expanded Details */}
                      {expandedNodes[step.id] && (
                        <div className="mt-4 space-y-3 border-t pt-4">
                          <div>
                            <h4 className="font-medium text-gray-800 mb-1">LLM Reasoning:</h4>
                            <p className="text-gray-600 text-sm">{step.reasoning}</p>
                          </div>
                          
                          <div>
                            <h4 className="font-medium text-gray-800 mb-1">Why this approach was chosen:</h4>
                            <p className="text-gray-600 text-sm">{step.why_chosen}</p>
                          </div>
                          
                          <div className="grid md:grid-cols-1 gap-4">
                            <div>
                              <h4 className="font-medium text-gray-800 mb-1">Input:</h4>
                              {isCodeContent(step.input) ? (
                                renderCodeContent(step.input)
                              ) : (
                                <p className="text-gray-600 text-sm bg-gray-50 p-2 rounded">{step.input}</p>
                              )}
                            </div>
                            
                            <div>
                              <h4 className="font-medium text-gray-800 mb-1">Output:</h4>
                              {isCodeContent(step.output) ? (
                                renderCodeContent(step.output)
                              ) : (
                                <p className="text-gray-600 text-sm bg-gray-50 p-2 rounded">{cleanOutput(step.output)}</p>
                              )}
                            </div>
                          </div>

                          <div>
                            <h4 className="font-medium text-gray-800 mb-1">Timestamp:</h4>
                            <p className="text-gray-500 text-xs">{new Date(step.timestamp).toLocaleString()}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Final Result */}
            <div className="mt-6 p-4 bg-green-50 rounded-lg border-l-4 border-green-500">
              <div className="mb-4">
              <div className="flex items-center gap-2 mb-2">
                <Bot className="w-5 h-5 text-green-600" />
                <span className="font-semibold text-green-800">Final Result:</span>
              </div>
              <p className="text-gray-700">
                {getFinalAnswer()}
                </p>
              </div>
              <div>
                <div className="flex items-center gap-2 mb-2">
                <span className="font-semibold text-green-800">Details:</span>
              </div>
              <div className="text-gray-700">
                {getFinalAnswerDetails()}
              </div> 
              </div>
            </div>

          

            {/* Decision Summary */}
            <div className="mt-6 p-4 bg-gray-50 rounded-lg">
              <h3 className="font-semibold text-gray-800 mb-2">Explainability Summary:</h3>
              <div className="space-y-2 text-sm text-gray-600">
                <div className="flex items-center justify-between">
                  <span>Decision Path: {agentLog.steps.map(step => step.type.replace(/_/g, ' ')).join(' → ')}</span>
                  <span className="font-medium">{agentLog.steps.length} LLM-explained steps</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Average confidence across all steps</span>
                  <span className="font-medium">{(agentLog.overall_confidence * 100).toFixed(0)}% overall confidence</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Tool types used: {[...new Set(agentLog.steps.map(step => step.type))].length} unique tools</span>
                  <span className="font-medium">Total time: {formatTime(agentLog.total_time)}</span>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default AgentExplorer;