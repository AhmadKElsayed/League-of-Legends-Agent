let currentThreadId = null;

const sessionListEl = document.getElementById('session-list');
const chatMessagesEl = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const currentChatTitle = document.getElementById('current-chat-title');

// Initialize
async function init() {
    await fetchSessions();
    
    // Event listeners
    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    newChatBtn.addEventListener('click', createNewChat);
}

async function fetchSessions() {
    try {
        const res = await fetch('/api/sessions');
        const data = await res.json();
        renderSessions(data.sessions);
    } catch (err) {
        console.error("Failed to fetch sessions", err);
    }
}

function renderSessions(sessions) {
    sessionListEl.innerHTML = '';
    if (sessions.length === 0) {
        sessionListEl.innerHTML = '<div style="padding: 16px; color: var(--text-secondary);">No previous chats.</div>';
        return;
    }

    sessions.forEach(session => {
        const div = document.createElement('div');
        div.className = `session-item ${session.thread_id === currentThreadId ? 'active' : ''}`;
        div.innerHTML = `
            <div class="session-preview" title="${session.preview}">${session.preview}</div>
            <button class="delete-btn" onclick="deleteSession('${session.thread_id}', event)">✕</button>
        `;
        div.onclick = () => loadSession(session.thread_id);
        sessionListEl.appendChild(div);
    });
}

function createNewChat() {
    // Generate a random thread ID for a new chat
    currentThreadId = 'thread_' + Math.random().toString(36).substring(2, 9);
    
    // Update UI
    currentChatTitle.textContent = `Current Chat`;
    chatMessagesEl.innerHTML = '';
    chatInput.disabled = false;
    sendBtn.disabled = false;
    chatInput.focus();
    
    // Reset active class in sidebar
    document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
}

async function loadSession(threadId) {
    currentThreadId = threadId;
    currentChatTitle.textContent = `Current Chat`;
    
    // Enable inputs
    chatInput.disabled = false;
    sendBtn.disabled = false;
    
    // Show loading
    chatMessagesEl.innerHTML = '<div class="loading"><span></span><span></span><span></span></div>';
    
    // Fetch history
    try {
        const res = await fetch(`/api/sessions/${threadId}`);
        const data = await res.json();
        
        chatMessagesEl.innerHTML = '';
        data.messages.forEach(msg => {
            appendMessage(msg.type, msg.content, false);
        });
        
        // Update active class
        fetchSessions();
        setTimeout(scrollToBottom, 100);
    } catch (err) {
        chatMessagesEl.innerHTML = `<div class="message agent">Failed to load chat history.</div>`;
    }
}

function appendMessage(role, content, animate = true) {
    // role is 'human' or 'ai' or 'system'
    if (role === 'system') return; // Hide system messages
    if (!content) return; // Hide empty tool messages if any slip through
    
    const div = document.createElement('div');
    div.className = `message ${role === 'human' ? 'user' : 'agent'}`;
    
    if (role === 'ai' || role === 'agent') {
        // Parse markdown for agent
        div.innerHTML = marked.parse(content);
    } else {
        div.textContent = content;
    }
    
    chatMessagesEl.appendChild(div);
    scrollToBottom();
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text || !currentThreadId) return;

    // UI Updates
    chatInput.value = '';
    chatInput.disabled = true;
    sendBtn.disabled = true;
    appendMessage('human', text);
    
    // Loading indicator
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'loading';
    loadingDiv.innerHTML = '<span></span><span></span><span></span>';
    chatMessagesEl.appendChild(loadingDiv);
    scrollToBottom();

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, thread_id: currentThreadId })
        });
        
        const data = await res.json();
        
        // Remove loading
        loadingDiv.remove();
        
        // Append response
        appendMessage('agent', data.response || "No response.");
        
        // Refresh sidebar to show updated preview
        fetchSessions();
        
    } catch (err) {
        loadingDiv.remove();
        appendMessage('agent', `**Error:** ${err.message}`);
    } finally {
        chatInput.disabled = false;
        sendBtn.disabled = false;
        chatInput.focus();
    }
}

function scrollToBottom() {
    chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

async function deleteSession(threadId, event) {
    event.stopPropagation();
    try {
        await fetch(`/api/sessions/${threadId}`, { method: 'DELETE' });
        if (currentThreadId === threadId) {
            currentThreadId = null;
            chatMessagesEl.innerHTML = '';
            currentChatTitle.textContent = 'Current Chat';
            chatInput.disabled = true;
            sendBtn.disabled = true;
        }
        fetchSessions();
    } catch (err) {
        console.error("Failed to delete session", err);
    }
}

init();
