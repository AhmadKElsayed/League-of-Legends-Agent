import { useState, useCallback } from 'react';

export function useChatStream() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [statusText, setStatusText] = useState('');

  const loadSession = useCallback(async (threadId) => {
    setIsLoading(true);
    setStatusText('');
    try {
      const res = await fetch(`/api/sessions/${threadId}`);
      if (!res.ok) throw new Error('Failed to load session');
      const data = await res.json();
      
      const formattedMessages = data.messages?.map(msg => ({
        id: Math.random().toString(36).substring(7),
        role: msg.type === 'human' || msg.type === 'user' ? 'user' : 'assistant',
        content: msg.content,
        isTool: msg.type === 'tool_log',
        toolName: msg.tool_name
      })) || [];
      
      setMessages(formattedMessages);
    } catch (error) {
      console.error(error);
      setMessages([{ id: 'error', role: 'assistant', content: 'Failed to load session.' }]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const sendMessage = useCallback(async (text, threadId) => {
    if (!text.trim() || !threadId) return;

    // Add user message
    const userMessage = { id: Math.random().toString(36).substring(7), role: 'user', content: text };
    setMessages(prev => [...prev, userMessage]);
    
    // Add temporary assistant message for streaming
    const assistantId = Math.random().toString(36).substring(7);
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '' }]);
    
    setIsLoading(true);
    setStatusText('Initializing Agent Core...');

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, thread_id: threadId })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        let parts = buffer.split('\n\n');
        buffer = parts.pop();

        for (let part of parts) {
          if (!part.trim()) continue;

          let lines = part.split('\n');
          let eventType = '';
          let dataString = '';

          for (let line of lines) {
            if (line.startsWith('event:')) eventType = line.slice(6).trim();
            else if (line.startsWith('data:')) dataString = line.slice(5).trim();
          }

          if (eventType === 'status') {
            try {
              const data = JSON.parse(dataString);
              const statusMap = {
                'Supervisor': 'Supervisor is analyzing query routes...',
                'OPGGWorker': 'OP.GG Analyst is crawling match databases...',
                'ResearchWorker': 'Research Analyst is searching Tavily web logs...',
                'GeneralAgent': 'Nexus is formulating general chat...'
              };
              setStatusText(statusMap[data.node] || `Interfacing with ${data.node}...`);
            } catch (e) {}
          } else if (eventType === 'token') {
            try {
              setStatusText(''); // Clear status when typing
              const data = JSON.parse(dataString);
              setMessages(prev => prev.map(msg => 
                msg.id === assistantId ? { ...msg, content: msg.content + data.text } : msg
              ));
            } catch (e) {}
          } else if (eventType === 'tool_log') {
            try {
              const data = JSON.parse(dataString);
              if (data.status === 'start') {
                 setMessages(prev => {
                    const newMessages = [...prev];
                    // Insert tool log before the streaming assistant message
                    const assistantIndex = newMessages.findIndex(m => m.id === assistantId);
                    if (assistantIndex !== -1) {
                        newMessages.splice(assistantIndex, 0, {
                            id: Math.random().toString(36).substring(7),
                            isTool: true,
                            toolName: data.tool,
                            status: 'start'
                        });
                    }
                    return newMessages;
                 });
              } else if (data.status === 'end') {
                 setMessages(prev => prev.map(msg => 
                    (msg.isTool && msg.toolName === data.tool && msg.status === 'start') 
                      ? { ...msg, status: 'end' } 
                      : msg
                 ));
              }
            } catch (e) {}
          }
        }
      }
    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, { id: 'error', role: 'assistant', content: '**Error:** ' + error.message }]);
    } finally {
      setIsLoading(false);
      setStatusText('');
    }
  }, []);

  return { messages, setMessages, isLoading, statusText, sendMessage, loadSession };
}
