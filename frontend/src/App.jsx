import React, { useState, useEffect, useRef } from 'react';

const API_BASE = 'http://localhost:8000';

function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [username, setUsername] = useState(localStorage.getItem('username') || '');
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authName, setAuthName] = useState('');
  const [authRole, setAuthRole] = useState('passenger');
  const [authMode, setAuthMode] = useState('login'); // 'login' or 'register'
  const [authError, setAuthError] = useState('');

  // Sidebar navigation state: 'dashboard' | 'console' | 'sessions' | 'context' | 'agents' | 'providers'
  const [activeTab, setActiveTab] = useState('console');

  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState('');
  const [sessionDetails, setSessionDetails] = useState({
    workflow_state: 'NEW',
    tasks: [],
    conversation: []
  });
  const [studioDetails, setStudioDetails] = useState({
    timeline: [],
    metrics: {
      total_tokens: 0,
      estimated_cost_usd: 0.0,
      llm_calls_count: 0,
      cache_hits: 0,
      cache_misses: 0,
      cache_hit_rate: 0.0
    },
    agents: [],
    providers: []
  });

  // Replay engine states
  const [isReplaying, setIsReplaying] = useState(false);
  const [replayedTasks, setReplayedTasks] = useState([]);

  // Context Viewer states
  const [selectedPrompt, setSelectedPrompt] = useState('intent');
  const [promptContent, setPromptContent] = useState('');

  const [selectedNode, setSelectedNode] = useState(null);
  const [inputValue, setInputValue] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  
  const chatEndRef = useRef(null);

  const getHeaders = () => {
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    };
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthError('');
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: authEmail, password: authPassword })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Login failed');
      }
      const data = await res.json();
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('username', authEmail);
      setToken(data.access_token);
      setUsername(authEmail);
    } catch (err) {
      setAuthError(err.message);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setAuthError('');
    try {
      const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: authEmail,
          password: authPassword,
          name: authName,
          role: authRole
        })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Registration failed');
      }
      const loginRes = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: authEmail, password: authPassword })
      });
      const loginData = await loginRes.json();
      localStorage.setItem('token', loginData.access_token);
      localStorage.setItem('username', authEmail);
      setToken(loginData.access_token);
      setUsername(authEmail);
    } catch (err) {
      setAuthError(err.message);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    setToken('');
    setUsername('');
    setSessions([]);
    setCurrentSessionId('');
    setSessionDetails({
      workflow_state: 'NEW',
      tasks: [],
      conversation: []
    });
    setStudioDetails({
      timeline: [],
      metrics: {
        total_tokens: 0,
        estimated_cost_usd: 0.0,
        llm_calls_count: 0,
        cache_hits: 0,
        cache_misses: 0,
        cache_hit_rate: 0.0
      },
      agents: [],
      providers: []
    });
  };

  // Fetch sessions list
  const fetchSessions = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/api/sessions`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.status === 401) {
        handleLogout();
        return;
      }
      const data = await res.json();
      if (Array.isArray(data)) {
        setSessions(data);
        if (data.length > 0 && !currentSessionId) {
          setCurrentSessionId(data[0].session_id);
        }
      }
    } catch (err) {
      console.error("Failed to fetch sessions:", err);
    }
  };

  // Fetch session details
  const fetchSessionDetails = async (sessionId) => {
    if (!sessionId || !token) return;
    try {
      const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.status === 401) {
        handleLogout();
        return;
      }
      const data = await res.json();
      setSessionDetails(data);
    } catch (err) {
      console.error("Failed to fetch session details:", err);
    }
  };

  // Fetch session specific Studio details (metrics, timeline, health)
  const fetchStudioDetails = async (sessionId) => {
    if (!sessionId || !token) return;
    try {
      const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/studio-details`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.status === 401) {
        handleLogout();
        return;
      }
      const data = await res.json();
      setStudioDetails(data);
    } catch (err) {
      console.error("Failed to fetch studio details:", err);
    }
  };

  // Fetch prompt text template for Context Viewer
  const fetchPrompt = async (promptName) => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/api/prompts/${promptName}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setPromptContent(data.content);
      }
    } catch (err) {
      console.error("Failed to fetch prompt:", err);
    }
  };

  // Create a new session
  const handleNewSession = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/api/sessions`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({})
      });
      if (res.status === 401) {
        handleLogout();
        return;
      }
      const data = await res.json();
      await fetchSessions();
      setCurrentSessionId(data.session_id);
      setSelectedNode(null);
      setActiveTab('console');
    } catch (err) {
      console.error("Failed to create session:", err);
    }
  };

  // Send message
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isSending || !token) return;

    const userMsg = inputValue;
    setInputValue('');
    setIsSending(true);

    // Optimistically update conversation
    setSessionDetails(prev => ({
      ...prev,
      conversation: [
        ...prev.conversation,
        { sender: 'User', message: userMsg, timestamp: new Date().toISOString() }
      ]
    }));

    try {
      const res = await fetch(`${API_BASE}/api/sessions/${currentSessionId}/message`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ message: userMsg })
      });
      if (res.status === 401) {
        handleLogout();
        return;
      }
      await fetchSessionDetails(currentSessionId);
      await fetchStudioDetails(currentSessionId);
    } catch (err) {
      console.error("Failed to send message:", err);
    } finally {
      setIsSending(false);
    }
  };

  // Simulate workflow run execution
  const handleSimulateExecution = async () => {
    if (sessionDetails.tasks.length === 0 || isSimulating || !token) return;
    setIsSimulating(true);

    try {
      const res = await fetch(`${API_BASE}/api/sessions/${currentSessionId}/run`, {
        method: 'POST',
        headers: getHeaders()
      });
      if (res.status === 401) {
        handleLogout();
        return;
      }
      await fetchSessionDetails(currentSessionId);
      await fetchStudioDetails(currentSessionId);
    } catch (err) {
      console.error("Error launching simulation run:", err);
    } finally {
      setIsSimulating(false);
    }
  };

  // Playback Replay Engine (simulates steps chronologically in UI)
  const handleStartReplay = () => {
    if (sessionDetails.tasks.length === 0 || isReplaying) return;
    setIsReplaying(true);
    setSelectedNode(null);
    
    // Copy tasks and set initial status to PENDING
    const initialTasks = sessionDetails.tasks.map(t => ({ ...t, status: 'PENDING' }));
    setReplayedTasks(initialTasks);
    
    let step = 0;
    const runNextStep = () => {
      if (step >= sessionDetails.tasks.length) {
        setIsReplaying(false);
        return;
      }
      
      const nextTask = sessionDetails.tasks[step];
      setReplayedTasks(prev => prev.map(t => {
        if (t.task_id === nextTask.task_id) {
          return { ...t, status: nextTask.status };
        }
        return t;
      }));
      
      setSelectedNode(nextTask);
      step += 1;
      setTimeout(runNextStep, 1200);
    };
    
    setTimeout(runNextStep, 800);
  };

  // Setup periodic polling
  useEffect(() => {
    if (token) {
      fetchSessions();
    }
  }, [token]);

  useEffect(() => {
    if (currentSessionId && token) {
      fetchSessionDetails(currentSessionId);
      fetchStudioDetails(currentSessionId);
    }
    const interval = setInterval(() => {
      if (currentSessionId && token && !isReplaying) {
        fetchSessionDetails(currentSessionId);
        fetchStudioDetails(currentSessionId);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [currentSessionId, token, isReplaying]);

  useEffect(() => {
    if (activeTab === 'context') {
      fetchPrompt(selectedPrompt);
    }
  }, [activeTab, selectedPrompt]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [sessionDetails.conversation]);

  useEffect(() => {
    if (selectedNode && sessionDetails.tasks.length > 0 && !isReplaying) {
      const matching = sessionDetails.tasks.find(t => t.task_id === selectedNode.task_id);
      if (matching) {
        setSelectedNode(matching);
      }
    }
  }, [sessionDetails.tasks, isReplaying]);

  if (!token) {
    return (
      <div className="auth-overlay">
        <div className="auth-card">
          <h2>{authMode === 'login' ? 'Login to TravelOps AI' : 'Create Operator Account'}</h2>
          {authError && <div className="auth-error">{authError}</div>}
          <form onSubmit={authMode === 'login' ? handleLogin : handleRegister}>
            {authMode === 'register' && (
              <div className="auth-field">
                <label>Name</label>
                <input 
                  type="text" 
                  value={authName} 
                  onChange={(e) => setAuthName(e.target.value)} 
                  required 
                />
              </div>
            )}
            <div className="auth-field">
              <label>Email</label>
              <input 
                type="email" 
                value={authEmail} 
                onChange={(e) => setAuthEmail(e.target.value)} 
                required 
              />
            </div>
            <div className="auth-field">
              <label>Password</label>
              <input 
                type="password" 
                value={authPassword} 
                onChange={(e) => setAuthPassword(e.target.value)} 
                required 
              />
            </div>
            {authMode === 'register' && (
              <div className="auth-field">
                <label>Role</label>
                <select value={authRole} onChange={(e) => setAuthRole(e.target.value)}>
                  <option value="passenger">Passenger</option>
                  <option value="operator">Operator</option>
                  <option value="admin">Administrator</option>
                </select>
              </div>
            )}
            <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '16px' }}>
              {authMode === 'login' ? 'Login' : 'Register'}
            </button>
          </form>
          <div className="auth-toggle">
            {authMode === 'login' ? (
              <p>Don't have an account? <span onClick={() => setAuthMode('register')}>Register here</span></p>
            ) : (
              <p>Already have an account? <span onClick={() => setAuthMode('login')}>Login here</span></p>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Draw customized responsive SVG DAG
  const renderWorkflowSvg = () => {
    const tasks = isReplaying ? replayedTasks : sessionDetails.tasks;
    if (!tasks || tasks.length === 0) {
      return (
        <div style={{ color: 'var(--text-secondary)', textAlign: 'center', marginTop: '60px', padding: '20px' }}>
          No active DAG pipeline currently generated.<br/>Specify origin, destination, and travel parameters in the console to plan.
        </div>
      );
    }

    const nodePositions = {
      "search_buses": { x: 180, y: 40, label: "Search Buses", icon: "🔍" },
      "get_route_details": { x: 70, y: 140, label: "Maps Routing", icon: "🗺️" },
      "get_weather_forecast": { x: 290, y: 140, label: "Live Weather", icon: "🌤️" },
      "recommend_options": { x: 180, y: 240, label: "AI Recommend", icon: "💡" },
      "hold_seat": { x: 180, y: 340, label: "Hold Ticket", icon: "💺" },
      "process_payment": { x: 180, y: 440, label: "Billing Payment", icon: "💳" },
      "confirm_booking": { x: 180, y: 540, label: "Confirm Ticket", icon: "🎟️" },
      "send_notification": { x: 180, y: 640, label: "Notify Alerts", icon: "✉️" }
    };

    // Calculate coordinates for nodes dynamically
    const nodeCoords = {};
    tasks.forEach((task, idx) => {
      const standard = nodePositions[task.name];
      if (standard) {
        nodeCoords[task.task_id] = { ...standard, task };
      } else {
        nodeCoords[task.task_id] = {
          x: 180,
          y: 40 + idx * 80,
          label: task.name.replace('_', ' ').toUpperCase(),
          icon: "⚙️",
          task
        };
      }
    });

    const lines = [];
    tasks.forEach(task => {
      const targetCoord = nodeCoords[task.task_id];
      if (targetCoord && task.dependencies) {
        task.dependencies.forEach(depId => {
          const srcCoord = nodeCoords[depId];
          if (srcCoord) {
            let lineClass = "dag-connection-line";
            if (srcCoord.task.status === "COMPLETED") {
              lineClass += " completed";
            } else if (srcCoord.task.status === "RUNNING") {
              lineClass += " running";
            }
            lines.push({
              key: `${depId}-${task.task_id}`,
              x1: srcCoord.x + 60,
              y1: srcCoord.y + 40,
              x2: targetCoord.x + 60,
              y2: targetCoord.y,
              className: lineClass
            });
          }
        });
      }
    });

    return (
      <div className="dag-canvas">
        <svg width="100%" height="720" style={{ minWidth: '360px' }}>
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(255,255,255,0.15)" />
            </marker>
          </defs>
          
          {/* Render connection lines */}
          {lines.map(line => (
            <line 
              key={line.key}
              x1={line.x1} 
              y1={line.y1} 
              x2={line.x2} 
              y2={line.y2} 
              className={line.className}
              markerEnd="url(#arrow)"
            />
          ))}

          {/* Render node boxes */}
          {Object.entries(nodeCoords).map(([taskId, c]) => {
            const isSelected = selectedNode?.task_id === taskId;
            let nodeClass = `dag-node-rect ${c.task.status.toLowerCase()}`;
            if (isSelected) nodeClass += " selected";

            return (
              <g key={taskId} onClick={() => setSelectedNode(c.task)}>
                <rect 
                  x={c.x} 
                  y={c.y} 
                  width="130" 
                  height="45" 
                  className={nodeClass} 
                />
                <text 
                  x={c.x + 10} 
                  y={c.y + 26} 
                  fill="#ffffff" 
                  fontSize="11" 
                  fontWeight="600"
                  style={{ pointerEvents: 'none' }}
                >
                  {c.icon} {c.label.substring(0, 15)}
                </text>
                <circle 
                  cx={c.x + 120} 
                  cy={c.y + 8} 
                  r="4" 
                  fill={
                    c.task.status === "COMPLETED" ? "#10b981" :
                    c.task.status === "RUNNING" ? "#f59e0b" :
                    c.task.status === "FAILED" ? "#ef4444" : "#ffffff"
                  } 
                />
              </g>
            );
          })}
        </svg>
      </div>
    );
  };

  return (
    <div className="studio-layout">
      {/* SIDEBAR NAVIGATION PANEL */}
      <div className="studio-sidebar">
        <div className="studio-brand">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="3 11 22 2 13 21 11 13 3 11"></polygon></svg>
          TravelOps AI Studio
        </div>
        
        <div className="studio-nav">
          <div 
            className={`studio-nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="9"></rect><rect x="14" y="3" width="7" height="5"></rect><rect x="14" y="12" width="7" height="9"></rect><rect x="3" y="16" width="7" height="5"></rect></svg>
            Dashboard Home
          </div>
          <div 
            className={`studio-nav-item ${activeTab === 'console' ? 'active' : ''}`}
            onClick={() => setActiveTab('console')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
            Operations Console
          </div>
          <div 
            className={`studio-nav-item ${activeTab === 'sessions' ? 'active' : ''}`}
            onClick={() => setActiveTab('sessions')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
            Session Browser
          </div>
          <div 
            className={`studio-nav-item ${activeTab === 'context' ? 'active' : ''}`}
            onClick={() => setActiveTab('context')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>
            Context Viewer
          </div>
          <div 
            className={`studio-nav-item ${activeTab === 'agents' ? 'active' : ''}`}
            onClick={() => setActiveTab('agents')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
            Agent Registry
          </div>
          <div 
            className={`studio-nav-item ${activeTab === 'providers' ? 'active' : ''}`}
            onClick={() => setActiveTab('providers')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="12" x2="2" y2="12"></line><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"></path><line x1="6" y1="16" x2="6.01" y2="16"></line><line x1="10" y1="16" x2="10.01" y2="16"></line></svg>
            Provider Status
          </div>
        </div>

        {/* LOGGED IN USER CARD */}
        <div style={{ padding: '16px', borderTop: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            👤 {username}
          </div>
          <button className="btn-logout" onClick={handleLogout} style={{
            background: 'rgba(239, 68, 68, 0.15)',
            color: '#ef4444',
            border: '1px solid rgba(239, 68, 68, 0.25)',
            padding: '8px',
            borderRadius: '6px',
            fontSize: '0.8rem',
            cursor: 'pointer',
            width: '100%',
            fontWeight: 600
          }}>Logout</button>
        </div>
      </div>

      {/* MAIN VIEWPORT CANVAS */}
      <div className="studio-content">
        <div className="studio-header">
          <h2>
            {activeTab === 'dashboard' && 'Operations Dashboard'}
            {activeTab === 'console' && 'Operations Studio Console'}
            {activeTab === 'sessions' && 'Session Browser Log'}
            {activeTab === 'context' && 'Agent Context Viewer'}
            {activeTab === 'agents' && 'Dynamic Agent Registry'}
            {activeTab === 'providers' && 'Transit Providers Routing Telemetry'}
          </h2>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            {currentSessionId && (
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Session: {currentSessionId}
              </span>
            )}
            <div className={`state-badge ${sessionDetails.workflow_state.toLowerCase()}`}>
              {sessionDetails.workflow_state}
            </div>
          </div>
        </div>

        <div className="studio-body">
          {/* TAB 1: DASHBOARD HOME */}
          {activeTab === 'dashboard' && (
            <div>
              {/* Stat Cards */}
              <div className="stats-grid">
                <div className="stat-card">
                  <span className="label">Active Sessions</span>
                  <span className="value">{sessions.length}</span>
                  <span className="subtext">Running instances</span>
                </div>
                <div className="stat-card">
                  <span className="label">Estimated Costs (Session)</span>
                  <span className="value">${(studioDetails.metrics.estimated_cost_usd || 0).toFixed(5)}</span>
                  <span className="subtext">Total USD tokens cost</span>
                </div>
                <div className="stat-card">
                  <span className="label">Total Tokens</span>
                  <span className="value">{studioDetails.metrics.total_tokens}</span>
                  <span className="subtext">Consumed this session</span>
                </div>
                <div className="stat-card">
                  <span className="label">Cache Hit Rate</span>
                  <span className="value">{studioDetails.metrics.cache_hit_rate}%</span>
                  <span className="subtext">{studioDetails.metrics.cache_hits} hits / {studioDetails.metrics.cache_misses} misses</span>
                </div>
              </div>

              {/* Provider Router Health States */}
              <div style={{ background: 'rgba(25, 27, 41, 0.3)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '24px', marginBottom: '32px' }}>
                <h3 style={{ marginBottom: '16px' }}>🔌 Provider Router Health Matrix</h3>
                <table className="studio-table">
                  <thead>
                    <tr>
                      <th>Provider Name</th>
                      <th>Status</th>
                      <th>Avg Latency</th>
                      <th>Consecutive Faults</th>
                    </tr>
                  </thead>
                  <tbody>
                    {studioDetails.providers.map(p => (
                      <tr key={p.name}>
                        <td>{p.name}</td>
                        <td>
                          <span style={{ 
                            color: p.status === 'HEALTHY' ? 'var(--success)' : 'var(--danger)',
                            fontWeight: 600
                          }}>
                            {p.status}
                          </span>
                        </td>
                        <td>{p.avg_latency_ms} ms</td>
                        <td>{p.consecutive_failures} / 3</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 2: OPERATIONS CONSOLE (SPLIT VIEW) */}
          {activeTab === 'console' && (
            <div className="studio-workspace" style={{ margin: '-32px', height: 'calc(100% + 64px)' }}>
              {/* Left Column: Chat log */}
              <div className="studio-workspace-left">
                <div className="chat-messages" style={{ flex: 1 }}>
                  {sessionDetails.conversation.length === 0 ? (
                    <div className="message-bubble assistant">
                      👋 Welcome to the **TravelOps AI Studio Workspace**! 
                      Start an autonomous operations run by typing a route instruction in the input bar.
                      <br/><br/>
                      Example: <i>"Search for sleeper buses from Bangalore to Hyderabad on June 29"</i>
                    </div>
                  ) : (
                    sessionDetails.conversation.map((msg, i) => (
                      <div key={i} className={`message-bubble ${msg.sender.toLowerCase()}`}>
                        <div>{msg.message}</div>
                        <div className="message-meta">
                          {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </div>
                    ))
                  )}
                  <div ref={chatEndRef} />
                </div>
                
                <form className="chat-input-bar" onSubmit={handleSendMessage} style={{ padding: '16px', borderTop: '1px solid var(--border-color)' }}>
                  <input 
                    type="text" 
                    className="chat-input" 
                    placeholder="Type routing target instruction..." 
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    disabled={isSending}
                  />
                  <button type="submit" className="btn-send" disabled={isSending}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                  </button>
                </form>
              </div>

              {/* Right Column: Live DAG + Inspector */}
              <div className="studio-workspace-right">
                {/* SVG Live DAG */}
                <div style={{ flex: 1, borderBottom: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', height: '60%' }}>
                  <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>🕸5 Live Workflow DAG {isReplaying && "(REPLAY ACTIVE)"}</span>
                    {sessionDetails.tasks.length > 0 && (
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button 
                          className="btn-primary" 
                          onClick={handleStartReplay}
                          disabled={isReplaying || isSimulating}
                          style={{ margin: 0, padding: '6px 12px', fontSize: '0.8rem', background: '#4f46e5' }}
                        >
                          {isReplaying ? 'Replaying...' : '▶ Replay'}
                        </button>
                        <button 
                          className="btn-primary" 
                          onClick={handleSimulateExecution} 
                          disabled={isSimulating || isReplaying}
                          style={{ margin: 0, padding: '6px 12px', fontSize: '0.8rem', background: 'var(--success)' }}
                        >
                          {isSimulating ? 'Running...' : 'Simulate Run'}
                        </button>
                      </div>
                    )}
                  </div>
                  <div style={{ flex: 1, overflow: 'auto' }}>
                    {renderWorkflowSvg()}
                  </div>
                </div>

                {/* Node Inspector */}
                <div style={{ padding: '20px', height: '40%', overflowY: 'auto' }}>
                  {selectedNode ? (
                    <div>
                      <h4 style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                        <span>Inspect: {selectedNode.name.replace('_', ' ').toUpperCase()}</span>
                        <span style={{ 
                          color: selectedNode.status === 'COMPLETED' ? 'var(--success)' :
                                 selectedNode.status === 'RUNNING' ? 'var(--warning)' :
                                 selectedNode.status === 'FAILED' ? 'var(--danger)' : 'white'
                        }}>{selectedNode.status}</span>
                      </h4>
                      <table className="inspector-table">
                        <tbody>
                          <tr>
                            <th>Task ID</th>
                            <td>{selectedNode.task_id}</td>
                          </tr>
                          {selectedNode.latency_sec && (
                            <tr>
                              <th>Execution Latency</th>
                              <td>{selectedNode.latency_sec.toFixed(3)}s</td>
                            </tr>
                          )}
                          <tr>
                            <th>Input Payload</th>
                            <td>
                              <pre style={{ margin: 0, fontSize: '0.75rem', background: '#0a0a0f', padding: '6px', borderRadius: '4px', overflowX: 'auto' }}>
                                {JSON.stringify(selectedNode.input_data, null, 2)}
                              </pre>
                            </td>
                          </tr>
                          {selectedNode.output_data && Object.keys(selectedNode.output_data).length > 0 && (
                            <tr>
                              <th>Output Result</th>
                              <td>
                                <pre style={{ margin: 0, fontSize: '0.75rem', background: '#0a0a0f', padding: '6px', borderRadius: '4px', overflowX: 'auto' }}>
                                  {JSON.stringify(selectedNode.output_data, null, 2)}
                                </pre>
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={{ color: 'var(--text-secondary)', textAlign: 'center', paddingTop: '32px' }}>
                      Click on a DAG node to inspect execution inputs, results, and latency telemetry.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: SESSION BROWSER & TIMELINE */}
          {activeTab === 'sessions' && (
            <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '32px' }}>
              <div>
                <h3>Sessions History</h3>
                <button className="btn-primary" onClick={handleNewSession} style={{ margin: '16px 0', width: '100%' }}>
                  Create New Session
                </button>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {sessions.map(s => (
                    <div 
                      key={s.session_id} 
                      className={`session-item ${currentSessionId === s.session_id ? 'active' : ''}`}
                      onClick={() => {
                        setCurrentSessionId(s.session_id);
                        setSelectedNode(null);
                      }}
                    >
                      <div className="title">{s.session_id}</div>
                      <div className="date">{new Date(s.created_at).toLocaleString()}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h3>⏳ Session Event Timeline</h3>
                <br/>
                {studioDetails.timeline.length === 0 ? (
                  <p style={{ color: 'var(--text-secondary)' }}>No timeline logs generated yet.</p>
                ) : (
                  <div className="timeline-list">
                    {studioDetails.timeline.map(log => (
                      <div key={log.id} className="timeline-event-node">
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <strong style={{ color: 'var(--accent-color)' }}>{log.agent_name}</strong>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{log.action}</span>
                        </div>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>{log.reasoning_summary}</p>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginTop: '6px' }}>
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 4: CONTEXT VIEWER */}
          {activeTab === 'context' && (
            <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: '32px' }}>
              <div>
                <h3>Prompts Templates</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '16px' }}>
                  {['intent', 'memory', 'planner', 'reflection', 'support'].map(pName => (
                    <button 
                      key={pName} 
                      className={`studio-nav-item ${selectedPrompt === pName ? 'active' : ''}`}
                      onClick={() => setSelectedPrompt(pName)}
                      style={{ border: '1px solid var(--border-color)', textAlign: 'left', background: 'transparent' }}
                    >
                      📄 {pName.toUpperCase()} Prompt
                    </button>
                  ))}
                </div>
                
                <div style={{ marginTop: '32px', padding: '16px', background: 'rgba(25,27,41,0.3)', border: '1px solid var(--border-color)', borderRadius: '8px' }}>
                  <h4>Session Preferences</h4>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '8px', lineHeight: 1.4 }}>
                    Cognitive preferences compiled for this session:
                  </p>
                  <pre style={{ margin: '12px 0 0 0', fontSize: '0.75rem', color: '#818cf8', fontFamily: 'monospace' }}>
                    {JSON.stringify({
                      operator_preference: "VRL Travels",
                      sorting_preference: "highest_rating",
                      routing_source: "Google Distance Matrix API"
                    }, null, 2)}
                  </pre>
                </div>
              </div>

              <div>
                <h3>System Prompt Editor Preview</h3>
                <br/>
                <div style={{ background: '#090a0f', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '24px', position: 'relative' }}>
                  <span style={{ position: 'absolute', top: '12px', right: '20px', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    READ ONLY
                  </span>
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '0.85rem', color: 'var(--text-primary)', fontFamily: 'monospace', lineHeight: 1.5 }}>
                    {promptContent || 'Loading prompt content...'}
                  </pre>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: AGENT REGISTRY */}
          {activeTab === 'agents' && (
            <div className="agent-grid">
              {studioDetails.agents.map(agent => (
                <div key={agent.name} className="agent-studio-card">
                  <div className="agent-header">
                    <span className="agent-name">🤖 {agent.name}</span>
                    <span style={{ 
                      color: agent.health === 'HEALTHY' ? 'var(--success)' : 'var(--danger)',
                      fontWeight: 600,
                      fontSize: '0.85rem'
                    }}>{agent.health}</span>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>VERSION</span>
                    <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>v{agent.version}</div>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>CAPABILITIES</span>
                    <div className="capabilities">
                      {agent.capabilities.map(cap => (
                        <span key={cap} className="cap-badge">{cap}</span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>AVERAGE LATENCY</span>
                    <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>{(agent.avg_latency || 0).toFixed(3)}s</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* TAB 6: PROVIDER ROUTING TELEMETRY */}
          {activeTab === 'providers' && (
            <div style={{ background: 'rgba(25, 27, 41, 0.3)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '24px' }}>
              <h3 style={{ marginBottom: '16px' }}>Transit Vendor Routing Details</h3>
              <table className="studio-table">
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Status</th>
                    <th>Average Latency</th>
                    <th>Trip Threshold</th>
                  </tr>
                </thead>
                <tbody>
                  {studioDetails.providers.map(p => (
                    <tr key={p.name}>
                      <td>{p.name}</td>
                      <td>
                        <span style={{ 
                          color: p.status === 'HEALTHY' ? 'var(--success)' : 'var(--danger)',
                          fontWeight: 600
                        }}>{p.status}</span>
                      </td>
                      <td>{p.avg_latency_ms} ms</td>
                      <td>{p.consecutive_failures} consecutive faults / 3 max</td>
                    </tr>
                  ))}
                  <tr>
                    <td>Google Distance Matrix API</td>
                    <td><span style={{ color: 'var(--success)', fontWeight: 600 }}>HEALTHY</span></td>
                    <td>124 ms</td>
                    <td>0 / 3 max</td>
                  </tr>
                  <tr>
                    <td>Open-Meteo Weather API</td>
                    <td><span style={{ color: 'var(--success)', fontWeight: 600 }}>HEALTHY</span></td>
                    <td>85 ms</td>
                    <td>0 / 3 max</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
