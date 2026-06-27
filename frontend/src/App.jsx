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

  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState('');
  const [sessionDetails, setSessionDetails] = useState({
    workflow_state: 'NEW',
    tasks: [],
    conversation: []
  });
  const [inputValue, setInputValue] = useState('');
  const [metrics, setMetrics] = useState({
    latency: '0s',
    tokens: 0,
    calls: 0,
    cost: 0
  });
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
  };

  // Fetch session list
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
      } else {
        setSessions([]);
      }
    } catch (err) {
      console.error("Failed to fetch sessions:", err);
      setSessions([]);
    }
  };

  // Fetch active session details
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

  // Fetch observability metrics
  const fetchMetrics = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/api/observability/metrics`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.status === 401) {
        handleLogout();
        return;
      }
      const data = await res.json();
      const calls = data.llm_calls || [];
      const totalTokens = calls.reduce((acc, c) => acc + (c.total_tokens || 0), 0);
      const avgLatency = calls.length 
        ? (calls.reduce((acc, c) => acc + (c.latency_sec || 0), 0) / calls.length).toFixed(2)
        : 0;

      setMetrics({
        latency: `${avgLatency}s`,
        tokens: totalTokens,
        calls: calls.length,
        cost: data.total_cost_usd || 0
      });
    } catch (err) {
      console.error("Failed to fetch metrics:", err);
    }
  };

  // Create new session
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

    // Optimistically update UI
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
      const data = await res.json();
      
      // Refresh session details & metrics
      await fetchSessionDetails(currentSessionId);
      await fetchMetrics();
    } catch (err) {
      console.error("Failed to send message:", err);
    } finally {
      setIsSending(false);
    }
  };

  // Simulation execution runner calling the backend background run orchestrator
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
      if (res.ok) {
        // Refresh details right away
        await fetchSessionDetails(currentSessionId);
      } else {
        console.error("Failed to start run execution on backend:", await res.text());
      }
    } catch (err) {
      console.error("Error launching simulation run:", err);
    } finally {
      setIsSimulating(false);
    }
  };

  // Initial load
  useEffect(() => {
    if (token) {
      fetchSessions();
      fetchMetrics();
    }
    
    // Poll metrics & session details periodically
    const interval = setInterval(() => {
      if (token) {
        fetchMetrics();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [token]);

  // Update details and poll when session changes
  useEffect(() => {
    if (currentSessionId && token) {
      fetchSessionDetails(currentSessionId);
    }
    
    const interval = setInterval(() => {
      if (currentSessionId && token) {
        fetchSessionDetails(currentSessionId);
      }
    }, 2000); // Poll every 2 seconds for snappy updates during run
    
    return () => clearInterval(interval);
  }, [currentSessionId, token]);

  // Scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [sessionDetails.conversation]);

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

  return (
    <div className="app-container">
      {/* LEFT SIDEBAR: Sessions List */}
      <div className="sidebar">
        <div className="panel-header">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
          Conversations
        </div>
        <button className="btn-primary" onClick={handleNewSession}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          New Operations Session
        </button>
        <div className="session-list">
          {sessions.map(s => (
            <div 
              key={s.session_id} 
              className={`session-item ${currentSessionId === s.session_id ? 'active' : ''}`}
              onClick={() => setCurrentSessionId(s.session_id)}
            >
              <div className="title">Session: {s.session_id.substring(5, 13)}...</div>
              <div className="date">{new Date(s.created_at).toLocaleString()}</div>
            </div>
          ))}
        </div>

        {/* METRICS PANEL */}
        <div className="metrics-widget">
          <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
            System Metrics
          </div>
          <div className="metric-row">
            <div className="metric-label">Avg LLM Latency</div>
            <div className="metric-val">{metrics.latency}</div>
          </div>
          <div className="metric-row">
            <div className="metric-label">Total Token usage</div>
            <div className="metric-val">{metrics.tokens}</div>
          </div>
          <div className="metric-row">
            <div className="metric-label">AI Agent Calls</div>
            <div className="metric-val">{metrics.calls}</div>
          </div>
          <div className="metric-row">
            <div className="metric-label">Estimated LLM Cost</div>
            <div className="metric-val">${(metrics.cost || 0).toFixed(4)}</div>
          </div>
        </div>
      </div>

      {/* CENTRAL AREA: Chat */}
      <div className="chat-container">
        <div className="chat-header">
          <div>
            <h1>TravelOps AI</h1>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Session ID: {currentSessionId}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div className={`state-badge ${sessionDetails.workflow_state.toLowerCase()}`}>
              {sessionDetails.workflow_state}
            </div>
            <button className="btn-logout" onClick={handleLogout} style={{
              background: 'rgba(239, 68, 68, 0.2)',
              color: '#ef4444',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              padding: '6px 12px',
              borderRadius: '6px',
              fontSize: '0.8rem',
              cursor: 'pointer'
            }}>Logout</button>
          </div>
        </div>

        <div className="chat-messages">
          {sessionDetails.conversation.length === 0 ? (
            <div className="message-bubble assistant">
              Hello! I am the TravelOps Autonomous Travel Operations Agent. 
              Ask me to search for buses, cancel a booking, or track a journey. 
              <br/><br/>
              Try typing: <i>"Search for buses from Hyderabad to Bangalore tomorrow"</i>
            </div>
          ) : (
            sessionDetails.conversation.map((msg, i) => (
              <div key={i} className={`message-bubble ${msg.sender.toLowerCase()}`}>
                <div>{msg.message}</div>
                {msg.payload?.task_graph && (
                  <div style={{ marginTop: '8px', fontSize: '0.8rem', opacity: 0.8 }}>
                    📌 Generated task graph with {msg.payload.task_graph.tasks?.length} tasks.
                  </div>
                )}
                <div className="message-meta">
                  {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            ))
          )}
          <div ref={chatEndRef} />
        </div>

        <form className="chat-input-bar" onSubmit={handleSendMessage}>
          <input 
            type="text" 
            className="chat-input" 
            placeholder="Type your instruction (e.g. Find tickets from Delhi to Jaipur...)" 
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={isSending}
          />
          <button type="submit" className="btn-send" disabled={isSending}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          </button>
        </form>
      </div>

      {/* RIGHT SIDEBAR: Task Dependency Graph and State Machine */}
      <div className="detail-panel">
        <div className="panel-header">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="9"></rect><rect x="14" y="3" width="7" height="5"></rect><rect x="14" y="12" width="7" height="9"></rect><rect x="3" y="16" width="7" height="5"></rect></svg>
          Orchestration Graph
        </div>

        {sessionDetails.tasks.length > 0 && (
          <button 
            className="btn-primary" 
            style={{ margin: '12px 16px 4px 16px', background: 'var(--success)' }}
            onClick={handleSimulateExecution}
            disabled={isSimulating}
          >
            {isSimulating ? 'Simulating...' : 'Simulate Workflow'}
          </button>
        )}

        <div className="task-graph-container">
          {sessionDetails.tasks.length === 0 ? (
            <div style={{ color: 'var(--text-secondary)', textAlign: 'center', marginTop: '40px', fontSize: '0.9rem' }}>
              No tasks currently generated.<br/>Specify a route in chat to plan a trip.
            </div>
          ) : (
            sessionDetails.tasks.map(task => (
              <div key={task.task_id} className={`task-node ${task.status.toLowerCase()}`}>
                <div className="task-header">
                  <div className="task-title">{task.name.replace('_', ' ')}</div>
                  <div className={`task-status-badge ${task.status.toLowerCase()}`}>
                    {task.status}
                  </div>
                </div>
                {task.dependencies.length > 0 && (
                  <div className="task-deps">
                    <span style={{ color: 'var(--text-muted)' }}>Depends:</span>
                    {task.dependencies.join(', ')}
                  </div>
                )}
                {Object.keys(task.input_data).length > 0 && (
                  <div className="task-data-block">
                    {JSON.stringify(task.input_data, null, 2)}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
