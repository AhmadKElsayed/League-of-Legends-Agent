import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useChatStream } from './hooks/useChatStream';
import { Backgrounds } from './components/Backgrounds';
import { Particles } from './components/Particles';
import { LandingView } from './components/LandingView';

function App() {
  const [sessions, setSessions] = useState([]);
  const [currentThreadId, setCurrentThreadId] = useState(null);
  const [input, setInput] = useState('');
  const [particlesEnabled, setParticlesEnabled] = useState(true);
  const [activeBgName, setActiveBgName] = useState('Ryze');
  const [searchQuery, setSearchQuery] = useState('');
  const [sessionToDelete, setSessionToDelete] = useState(null);
  
  const { messages, setMessages, isLoading, statusText, sendMessage, loadSession } = useChatStream();
  const messagesEndRef = useRef(null);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, statusText]);

  // Fetch sessions on load
  const fetchSessions = async () => {
    try {
      const res = await fetch('/api/sessions');
      const data = await res.json();
      setSessions(data.sessions || []);
    } catch (err) {
      console.error('Failed to load sessions', err);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [currentThreadId]);

  const handleNewChat = () => {
    const newId = 'thread_' + Math.random().toString(36).substring(2, 10);
    setCurrentThreadId(newId);
    setMessages([]);
  };

  const handleSelectSession = (id) => {
    if (id === currentThreadId) return;
    setCurrentThreadId(id);
    loadSession(id);
  };

  const handleDeleteSession = (e, id) => {
    e.stopPropagation();
    setSessionToDelete(id);
  };

  const confirmDeleteSession = async () => {
    if (!sessionToDelete) return;
    const id = sessionToDelete;
    
    try {
      await fetch(`/api/sessions/${id}`, { method: 'DELETE' });
      if (currentThreadId === id) {
        setCurrentThreadId(null);
        setMessages([]);
      }
      fetchSessions();
    } catch (err) {
      console.error('Failed to delete session', err);
    } finally {
      setSessionToDelete(null);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    
    let targetThreadId = currentThreadId;
    if (!targetThreadId) {
      targetThreadId = 'thread_' + Math.random().toString(36).substring(2, 10);
      setCurrentThreadId(targetThreadId);
    }

    const currentInput = input;
    setInput('');
    sendMessage(currentInput, targetThreadId);
  };

  const currentSession = sessions.find(s => s.thread_id === currentThreadId);
  const chatTitle = currentSession ? (currentSession.custom_name || currentSession.preview) : 'Select a chat or start a new one';

  const filteredSessions = sessions.filter(s => {
    const title = (s.custom_name || s.preview).toLowerCase();
    return title.includes(searchQuery.toLowerCase());
  });

  return (
    <>
      <Backgrounds onBgNameChange={setActiveBgName} />
      <Particles enabled={particlesEnabled} />
      
      <div id="app-container">
        {/* Sidebar */}
        <aside id="sidebar">
          <div className="sidebar-header">
              <div className="brand">
                  <div className="hextech-mini-core"></div>
                  <h2>Hextech Agent</h2>
              </div>
              <button id="new-chat-btn" title="New Chat" onClick={handleNewChat}>
                  <span className="plus-icon">+</span> New Chat
              </button>
          </div>

          <div className="search-container">
              <span className="search-icon">🔍</span>
              <input 
                type="text" 
                id="session-search" 
                placeholder="Search archives..." 
                autoComplete="off"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
          </div>

          <div id="session-list" className="session-list">
            {filteredSessions.map(session => (
              <div 
                key={session.thread_id} 
                className={`session-item ${session.thread_id === currentThreadId ? 'active' : ''}`}
                onClick={() => handleSelectSession(session.thread_id)}
              >
                <div className="session-preview" title={session.custom_name || session.preview}>
                  {session.custom_name || session.preview}
                </div>
                <button 
                  className="delete-btn" 
                  title="Delete Archive"
                  onClick={(e) => handleDeleteSession(e, session.thread_id)}
                >✕</button>
              </div>
            ))}
          </div>
        </aside>

        {/* Main Content */}
        <main id="chat-area">
          <header className="chat-header">
              <div className="header-left">
                  <button id="sidebar-toggle" className="sidebar-toggle-btn" title="Toggle Archive Sidebar">
                      <span></span><span></span><span></span>
                  </button>
                  <div className="title-container">
                      <h3 id="current-chat-title">{chatTitle}</h3>
                  </div>
              </div>

              <div className="header-actions">
                  <button 
                    id="particles-toggle" 
                    className={`header-control-btn ${particlesEnabled ? 'active' : ''}`}
                    onClick={() => setParticlesEnabled(!particlesEnabled)}
                  >
                      <span className="particles-icon">✨</span> Matrix {particlesEnabled ? 'On' : 'Off'}
                  </button>
              </div>
          </header>

          <div id="chat-messages" className="chat-messages">
            {messages.length === 0 && !isLoading && (
              <LandingView onQueryClick={(query) => {
                setInput(query);
                // Can't auto submit here cleanly without a ref or useEffect on input change, but user can click send
              }} />
            )}

            {messages.map((msg, index) => {
              if (msg.isTool) {
                return (
                  <div key={index} className="hextech-terminal" data-tool-name={msg.toolName}>
                    <div className="hextech-terminal-header">
                      {msg.status === 'start' ? (
                        <><span>🔧 Executing <code>{msg.toolName}</code></span><span className="tool-loader" style={{ animation: 'pulseDot 1.5s infinite ease-in-out', width: '8px', height: '8px', backgroundColor: 'var(--hextech-blue)', borderRadius: '50%' }}></span></>
                      ) : (
                        <span>✅ Completed <code>{msg.toolName}</code></span>
                      )}
                    </div>
                  </div>
                );
              }

              // Hide the empty assistant bubble while thinking
              if (msg.role === 'assistant' && !msg.content) {
                return null;
              }

              return (
                <div key={index} className={`message ${msg.role === 'user' ? 'user' : 'agent'}`}>
                  {msg.role === 'user' ? (
                    msg.content
                  ) : (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  )}
                </div>
              );
            })}
            
            {/* Status Indicator */}
            {statusText && (
              <div className="hextech-terminal">
                <div className="hextech-terminal-header" style={{display: 'flex', alignItems: 'center', gap: '10px'}}>
                  <span className="routing-text" style={{color: 'var(--text-secondary)'}}>{statusText}</span>
                  <div className="thinking-pulse"></div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          <form className="chat-input-container" style={{ padding: '20px', borderTop: '1px solid var(--glass-border)', display: 'flex', gap: '10px', background: 'var(--glass-bg-dense)' }} onSubmit={handleSubmit}>
            <input 
              type="text" 
              id="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Query Runeterra archives or OP.GG profiles..." 
              disabled={isLoading}
              style={{ flex: 1, padding: '15px 20px', borderRadius: '4px', border: '1px solid var(--glass-border-blue)', background: 'rgba(0, 0, 0, 0.4)', color: 'white', fontSize: '1rem', outline: 'none' }}
            />
            <button 
              id="send-btn" 
              type="submit" 
              disabled={isLoading || !input.trim()}
              style={{ background: 'var(--hextech-blue)', color: '#010a13', border: 'none', padding: '0 25px', borderRadius: '4px', fontWeight: 'bold', textTransform: 'uppercase', cursor: 'pointer' }}
            >
              Send
            </button>
          </form>
        </main>
      </div>

      {/* Delete Confirmation Modal */}
      {sessionToDelete && (
        <div id="custom-modal" className="custom-modal-overlay active">
            <div className="custom-modal-content">
                <h3 className="modal-title">Delete chat session?</h3>
                <p className="modal-desc">Are you sure you want to delete this chat session?</p>
                <div className="modal-actions">
                    <button className="modal-btn confirm-btn" onClick={confirmDeleteSession}>Delete</button>
                    <button className="modal-btn cancel-btn" onClick={() => setSessionToDelete(null)}>Cancel</button>
                </div>
            </div>
        </div>
      )}
    </>
  );
}

export default App;
