import { useState, useCallback } from 'react';

// Flavour text per graph node, and the label used in the fan-out progress list.
export const NODE_LABELS = {
  Supervisor: 'Supervisor is analyzing query routes...',
  OPGGWorker: 'OP.GG Analyst is crawling match databases...',
  ResearchWorker: 'Research Analyst is searching Tavily web logs...',
  GeneralAgent: 'Nexus is formulating general chat...',
  Synthesizer: 'Merging intelligence into a single answer...'
};

export const NODE_SHORT_LABELS = {
  OPGGWorker: 'OP.GG Analyst',
  ResearchWorker: 'Research Analyst',
  GeneralAgent: 'Nexus',
  Synthesizer: 'Synthesizer'
};

export function useChatStream() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [statusText, setStatusText] = useState('');
  // Populated only when the Supervisor dispatches more than one specialist.
  const [activeWorkers, setActiveWorkers] = useState([]);

  const loadSession = useCallback(async (threadId) => {
    setIsLoading(true);
    setStatusText('');
    setActiveWorkers([]);
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
    setActiveWorkers([]);
    setStatusText('Initializing Agent Core...');

    // Tracked outside React state so status events can be ignored for a
    // single-worker turn without waiting for a re-render.
    let isFanout = false;

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
            // SSE allows several data: lines per frame; they join with a newline.
            else if (line.startsWith('data:')) {
              dataString += (dataString ? '\n' : '') + line.slice(5).trim();
            }
          }

          if (eventType === 'plan') {
            try {
              const data = JSON.parse(dataString);
              const workers = data.workers || [];
              isFanout = workers.length > 1;
              // A single worker answers inline; only show the checklist when
              // several are genuinely running at once.
              setActiveWorkers(isFanout ? workers.map(name => ({ name, status: 'pending' })) : []);
            } catch (e) {
              console.error('Bad plan frame', e);
            }
          } else if (eventType === 'status') {
            try {
              const data = JSON.parse(dataString);
              if (data.state === 'end') {
                setActiveWorkers(prev => prev.map(w =>
                  w.name === data.node ? { ...w, status: 'done' } : w
                ));
                // Don't clear statusText here: another branch may still be running.
              } else {
                setActiveWorkers(prev => prev.map(w =>
                  w.name === data.node ? { ...w, status: 'running' } : w
                ));
                // During fan-out the checklist carries the detail, so only
                // surface the Synthesizer's line.
                if (!isFanout || data.node === 'Synthesizer') {
                  setStatusText(NODE_LABELS[data.node] || `Interfacing with ${data.node}...`);
                }
              }
            } catch (e) {
              console.error('Bad status frame', e);
            }
          } else if (eventType === 'token') {
            try {
              setStatusText(''); // Clear status when typing
              const data = JSON.parse(dataString);
              setMessages(prev => prev.map(msg =>
                msg.id === assistantId ? { ...msg, content: msg.content + data.text } : msg
              ));
            } catch (e) {
              console.error('Bad token frame', e);
            }
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
            } catch (e) {
              console.error('Bad tool_log frame', e);
            }
          } else if (eventType === 'error') {
            // The server emits this when the graph raises mid-stream. Previously
            // it was ignored, leaving an empty assistant bubble.
            let detail = 'Unknown stream error';
            try {
              detail = JSON.parse(dataString).error || detail;
            } catch (e) {
              console.error('Bad error frame', e);
            }
            setMessages(prev => prev.map(msg =>
              msg.id === assistantId
                ? { ...msg, content: (msg.content ? msg.content + '\n\n' : '') + `**Error:** ${detail}` }
                : msg
            ));
          }
        }
      }
    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, { id: 'error', role: 'assistant', content: '**Error:** ' + error.message }]);
    } finally {
      setIsLoading(false);
      setStatusText('');
      setActiveWorkers([]);
    }
  }, []);

  return { messages, setMessages, isLoading, statusText, activeWorkers, sendMessage, loadSession };
}
