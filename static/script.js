/* ---------------------------------------------------------------------------
 * Hextech Intelligence Console - Interactive Script Engine
 * --------------------------------------------------------------------------- */

let currentThreadId = null;
let matrixEnabled = true;
let typewriterInterval = null;
let activeTypewriterResolve = null;

// Riot DDragon high-resolution champion splash image mapping
const splashImages = {
    ryze: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Ryze_11.jpg', // Championship Ryze
    aurelion: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/AurelionSol_0.jpg', // Cosmic Core Base
    jinx: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Jinx_0.jpg', // Slayer Jinx
    ahri: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Ahri_0.jpg', // Spirit Blossom Ahri
    yasuo: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Yasuo_0.jpg', // PROJECT Yasuo
    lux: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Lux_17.jpg', // Dark Cosmic Lux
    senna: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Senna_0.jpg', // Base Senna
    pantheon: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Pantheon_0.jpg', // Pulsefire Pantheon
    zed: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Zed_0.jpg',
    akali: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Akali_0.jpg',
    ekko: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Ekko_0.jpg',
    diana: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Diana_0.jpg',
    sylas: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Sylas_0.jpg',
    leona: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Leona_0.jpg',
    azir: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Azir_0.jpg',
    leesin: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/LeeSin_0.jpg',
    thresh: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Thresh_0.jpg'
};

const splashKeys = Object.keys(splashImages);
let currentSplashIndex = 0;
let splashRotationInterval = null;

// Global Sessions store for real-time local search
let cachedSessions = [];

// DOM Elements
const sessionListEl = document.getElementById('session-list');
const chatMessagesEl = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const currentChatTitle = document.getElementById('current-chat-title');
const renameChatBtn = document.getElementById('rename-chat-btn');
const sessionSearch = document.getElementById('session-search');

const activeBgName = document.getElementById('active-bg-name');
const bgLayer1 = document.getElementById('bg-layer-1');
const bgLayer2 = document.getElementById('bg-layer-2');

const particlesToggle = document.getElementById('particles-toggle');
const sidebarToggle = document.getElementById('sidebar-toggle');
const sidebar = document.getElementById('sidebar');

const thinkingBar = document.getElementById('thinking-bar');
const thinkingStatus = document.getElementById('thinking-status');

// Initialize
async function init() {
    // Set initial background image and begin rotation cycle
    changeBackground('ryze');
    startSplashRotation();

    // Fetch initial sessions
    await fetchSessions();

    // Register event listeners
    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    newChatBtn.addEventListener('click', createNewChat);

    particlesToggle.addEventListener('click', toggleParticles);

    // Collapsible Mobile Sidebar
    sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
    });

    // Session Search Filter
    sessionSearch.addEventListener('input', (e) => {
        filterSessions(e.target.value);
    });

    // Double click to rename active session
    currentChatTitle.addEventListener('dblclick', renameActiveSession);
    renameChatBtn.addEventListener('click', renameActiveSession);

    // Document-level clicks to skip typewriter
    document.addEventListener('click', skipTypewriter);

    // Initialize Particles Canvas Matrix
    initParticlesCanvas();
}

// ---------------------------------------------------------------------------
// Hardware Accelerated Cinematic Splash Background Fader & Rotation
// ---------------------------------------------------------------------------
let currentBgLayer = 1;
function changeBackground(champKey) {
    const url = splashImages[champKey] || splashImages.ryze;

    const nameMap = {
        ryze: 'Ryze',
        aurelion: 'Aurelion Sol',
        jinx: 'Jinx',
        ahri: 'Ahri',
        yasuo: 'Yasuo',
        lux: 'Lux',
        senna: 'Senna',
        pantheon: 'Pantheon',
        zed: 'Zed',
        akali: 'Akali',
        ekko: 'Ekko',
        diana: 'Diana',
        sylas: 'Sylas',
        leona: 'Leona',
        azir: 'Azir',
        leesin: 'Lee Sin',
        thresh: 'Thresh'
    };

    if (activeBgName) {
        activeBgName.textContent = nameMap[champKey] || champKey;
    }

    if (currentBgLayer === 1) {
        bgLayer2.style.backgroundImage = `url('${url}')`;
        bgLayer2.classList.add('active');
        bgLayer1.classList.remove('active');
        currentBgLayer = 2;
    } else {
        bgLayer1.style.backgroundImage = `url('${url}')`;
        bgLayer1.classList.add('active');
        bgLayer2.classList.remove('active');
        currentBgLayer = 1;
    }
}

function startSplashRotation() {
    if (splashRotationInterval) clearInterval(splashRotationInterval);
    
    // Cycle backgrounds every 12 seconds with absolute cross-fade precision
    splashRotationInterval = setInterval(() => {
        currentSplashIndex = (currentSplashIndex + 1) % splashKeys.length;
        changeBackground(splashKeys[currentSplashIndex]);
    }, 12000);
}

// ---------------------------------------------------------------------------
// Session Renaming & Local Storage Cache
// ---------------------------------------------------------------------------
function renameActiveSession() {
    if (!currentThreadId) return;

    const originalTitle = currentChatTitle.textContent;
    const newTitle = prompt("Enter a custom archives name:", originalTitle);

    if (newTitle && newTitle.trim()) {
        const sanitized = newTitle.trim();
        // Save to browser cache
        localStorage.setItem(`session_title_${currentThreadId}`, sanitized);
        currentChatTitle.textContent = sanitized;

        // Redraw lists
        renderSessions(cachedSessions);
    }
}

function getSessionName(session) {
    // Check if user set a custom title in cache
    const custom = localStorage.getItem(`session_title_${session.thread_id}`);
    if (custom) return custom;

    // Fallback to auto preview
    return session.preview || "Chat Session";
}

// ---------------------------------------------------------------------------
// Session Lists, Search & API
// ---------------------------------------------------------------------------
async function fetchSessions() {
    try {
        const res = await fetch('/api/sessions');
        const data = await res.json();
        cachedSessions = data.sessions || [];

        // Filter session list against search text if present
        filterSessions(sessionSearch.value);
    } catch (err) {
        console.error("Failed to load archive histories", err);
    }
}

function renderSessions(sessions) {
    sessionListEl.innerHTML = '';

    if (sessions.length === 0) {
        sessionListEl.innerHTML = `
            <div style="padding: 20px; text-align: center; color: var(--text-secondary); font-size: 0.85rem;">
                No matching archives.
            </div>`;
        return;
    }

    sessions.forEach(session => {
        const displayName = getSessionName(session);
        const div = document.createElement('div');
        const isActive = session.thread_id === currentThreadId;

        div.className = `session-item ${isActive ? 'active' : ''}`;
        div.innerHTML = `
            <div class="session-preview" title="${displayName}">${displayName}</div>
            <button class="delete-btn" title="Delete Archive">✕</button>
        `;

        // Session selection click
        div.addEventListener('click', (e) => {
            // Block click if delete icon clicked
            if (e.target.classList.contains('delete-btn')) return;
            loadSession(session.thread_id);
        });

        // Double click to rename directly from sidebar
        div.addEventListener('dblclick', (e) => {
            if (e.target.classList.contains('delete-btn')) return;

            const originalName = displayName;
            const newName = prompt("Rename archives:", originalName);
            if (newName && newName.trim()) {
                localStorage.setItem(`session_title_${session.thread_id}`, newName.trim());
                fetchSessions();
                if (currentThreadId === session.thread_id) {
                    currentChatTitle.textContent = newName.trim();
                }
            }
        });

        // Delete button listener
        div.querySelector('.delete-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteSession(session.thread_id);
        });

        sessionListEl.appendChild(div);
    });
}

function filterSessions(query) {
    const text = query.trim().toLowerCase();
    if (!text) {
        renderSessions(cachedSessions);
        return;
    }

    const filtered = cachedSessions.filter(s => {
        const customTitle = getSessionName(s).toLowerCase();
        return customTitle.includes(text) || s.preview.toLowerCase().includes(text);
    });

    renderSessions(filtered);
}

function createNewChat() {
    // Generate a unique Hextech thread token
    currentThreadId = 'thread_' + Math.random().toString(36).substring(2, 10);

    // Clear inputs
    chatInput.disabled = false;
    sendBtn.disabled = false;
    chatInput.value = '';

    // Header edits
    currentChatTitle.textContent = `New Core Chat`;
    renameChatBtn.style.display = 'block';

    // Redraw messaging box (Show starter matrix dashboard)
    renderLandingView();

    // Update active highlight classes in sidebar
    document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));

    chatInput.focus();
}

async function loadSession(threadId) {
    currentThreadId = threadId;

    // Enable inputs
    chatInput.disabled = false;
    sendBtn.disabled = false;
    renameChatBtn.style.display = 'block';

    // Find active name
    const activeName = getSessionName({ thread_id: threadId });
    currentChatTitle.textContent = activeName;

    // Show spinner inside messages viewport
    chatMessagesEl.innerHTML = '<div class="loading"><span></span><span></span><span></span></div>';

    // Close mobile menu slide
    sidebar.classList.remove('open');

    try {
        const res = await fetch(`/api/sessions/${threadId}`);
        const data = await res.json();

        chatMessagesEl.innerHTML = '';

        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(msg => {
                appendMessage(msg.type, msg.content, false);
            });
        } else {
            renderLandingView();
        }

        // Redraw lists
        fetchSessions();
        setTimeout(scrollToBottom, 100);
    } catch (err) {
        chatMessagesEl.innerHTML = `
            <div class="message agent">
                <h4 style="color:#ff5252">Archive Core Fault</h4>
                <p>Failed to query chat memory. Database locked or missing.</p>
            </div>`;
    }
}

// ---------------------------------------------------------------------------
// Starter Landing Dashboard & Queries
// ---------------------------------------------------------------------------
function renderLandingView() {
    chatMessagesEl.innerHTML = `
        <div id="landing-view" class="landing-view">
            <div class="hextech-core-container">
                <div class="hextech-core-outer"></div>
                <div class="hextech-core-inner"></div>
                <div class="hextech-core-center"></div>
            </div>
            <h1 class="landing-title">Hextech Intelligence Console</h1>
            <p class="landing-subtitle">Welcome, Summoner. Powered by Runeterra Core and OP.GG match analytics. Select a query matrix or write your own.</p>
            
            <div class="starter-chips-container">
                <div class="starter-chip" data-query="What is the best build and skill order for Jinx in the current patch?">
                    <span class="chip-emoji">⚔️</span>
                    <div class="chip-content">
                        <span class="chip-title">Combat Build</span>
                        <span class="chip-desc">Optimize Jinx runes and items</span>
                    </div>
                </div>
                <div class="starter-chip" data-query="How does Kayle survive the early lane matchup against Jax?">
                    <span class="chip-emoji">🛡️</span>
                    <div class="chip-content">
                        <span class="chip-title">Matchup Strategy</span>
                        <span class="chip-desc">Kayle vs Jax lane tactics</span>
                    </div>
                </div>
                <div class="starter-chip" data-query="Explain the lore relationship between Aurelion Sol and the Targonian Aspect of War.">
                    <span class="chip-emoji">📜</span>
                    <div class="chip-content">
                        <span class="chip-title">Runeterra Lore</span>
                        <span class="chip-desc">Aurelion Sol's cosmic history</span>
                    </div>
                </div>
                <div class="starter-chip" data-query="Who are the current S-tier Midlaners and what makes them strong in the meta?">
                    <span class="chip-emoji">📈</span>
                    <div class="chip-content">
                        <span class="chip-title">Meta Analytics</span>
                        <span class="chip-desc">Find top-tier mid pick rates</span>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Register starter chips click handlers
    document.querySelectorAll('.starter-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const promptText = chip.getAttribute('data-query');
            if (promptText) {
                chatInput.value = promptText;
                sendMessage();
            }
        });
    });
}

// ---------------------------------------------------------------------------
// Progressive thinking progress bar
// ---------------------------------------------------------------------------
let thinkingProgressInterval = null;
const thinkingStatements = [
    "Interfacing with Runeterra Archives...",
    "Crawling OP.GG champion databases...",
    "Retrieving itemization win rates...",
    "Analyzing matchup counter mechanics...",
    "Formulating optimal tactical strategy...",
    "Synthesizing cognitive agent insights..."
];

function startThinkingProgress() {
    thinkingBar.style.display = 'flex';
    let index = 0;
    thinkingStatus.textContent = thinkingStatements[0];

    thinkingProgressInterval = setInterval(() => {
        index = (index + 1) % thinkingStatements.length;
        thinkingStatus.textContent = thinkingStatements[index];
    }, 2800);
}

function stopThinkingProgress() {
    if (thinkingProgressInterval) {
        clearInterval(thinkingProgressInterval);
        thinkingProgressInterval = null;
    }
    thinkingBar.style.display = 'none';
}

// ---------------------------------------------------------------------------
// Typewriter Response Engine & Streaming
// ---------------------------------------------------------------------------
function skipTypewriter() {
    if (activeTypewriterResolve) {
        activeTypewriterResolve(); // Resolve immediately
    }
}

async function runTypewriter(element, markdownContent) {
    return new Promise((resolve) => {
        // Prepare HTML using marked
        const fullHTML = marked.parse(markdownContent);

        // Render characters incrementally inside a sandbox to preserve HTML tags
        // To build a robust HTML typewriter, we type plain text and gradually match indices 
        // or quickly typewriter render in blocks. A smooth, bulletproof word-by-word or tag-by-tag 
        // printing is best:
        let currentHTMLIndex = 0;
        let visibleText = "";

        element.classList.add('typewriter-cursor');

        activeTypewriterResolve = () => {
            // Skip directly to completed markdown state
            element.innerHTML = fullHTML;
            element.classList.remove('typewriter-cursor');
            activeTypewriterResolve = null;
            clearInterval(typewriterInterval);
            scrollToBottom();
            resolve();
        };

        // We print characters, skipping tags to avoid rendering broken tag blocks
        let rawWords = markdownContent.split(' ');
        let currentWordIndex = 0;

        typewriterInterval = setInterval(() => {
            if (currentWordIndex >= rawWords.length) {
                activeTypewriterResolve();
                return;
            }

            // Build current string
            visibleText = rawWords.slice(0, currentWordIndex + 1).join(' ');
            element.innerHTML = marked.parse(visibleText);

            currentWordIndex++;
            scrollToBottom();
        }, 15); // Fast, smooth typewriter step
    });
}

function appendMessage(role, content, animate = true) {
    if (role === 'system') return;
    if (!content) return;

    // Remove empty landing view if it exists
    const landing = document.getElementById('landing-view');
    if (landing) landing.remove();

    const div = document.createElement('div');
    div.className = `message ${role === 'human' || role === 'user' ? 'user' : 'agent'}`;

    chatMessagesEl.appendChild(div);

    if ((role === 'ai' || role === 'agent') && animate) {
        // Stream text with typewriter effect
        return runTypewriter(div, content);
    } else {
        // Render instantly
        if (role === 'ai' || role === 'agent') {
            div.innerHTML = marked.parse(content);
        } else {
            div.textContent = content;
        }
        scrollToBottom();
        return Promise.resolve();
    }
}

// ---------------------------------------------------------------------------
// Send Message
// ---------------------------------------------------------------------------
async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text || !currentThreadId) return;

    // UI Updates
    chatInput.value = '';
    chatInput.disabled = true;
    sendBtn.disabled = true;

    // Append human query bubble
    appendMessage('human', text, false);

    // Initiate loader dots and progressive terminal logging
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'loading';
    loadingDiv.innerHTML = '<span></span><span></span><span></span>';
    chatMessagesEl.appendChild(loadingDiv);
    scrollToBottom();

    startThinkingProgress();

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, thread_id: currentThreadId })
        });

        const data = await res.json();

        // Remove loading dots & dynamic logging
        loadingDiv.remove();
        stopThinkingProgress();

        // Append Agent bubble with typewriter effects
        await appendMessage('agent', data.response || "No response core loaded.");

        // Refresh sidebar previews
        fetchSessions();

    } catch (err) {
        loadingDiv.remove();
        stopThinkingProgress();
        appendMessage('agent', `**Hextech Error Core:** ${err.message}`, false);
    } finally {
        chatInput.disabled = false;
        sendBtn.disabled = false;
        chatInput.focus();
    }
}

function scrollToBottom() {
    chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

function confirmHextechPurge() {
    return new Promise((resolve) => {
        const modal = document.getElementById('custom-modal');
        const confirmBtn = document.getElementById('modal-confirm-btn');
        const cancelBtn = document.getElementById('modal-cancel-btn');

        if (!modal || !confirmBtn || !cancelBtn) {
            resolve(false);
            return;
        }

        const show = () => {
            modal.classList.add('active');
        };

        const hide = () => {
            modal.classList.remove('active');
        };

        const onConfirm = () => {
            hide();
            cleanup();
            resolve(true);
        };

        const onCancel = () => {
            hide();
            cleanup();
            resolve(false);
        };

        const cleanup = () => {
            confirmBtn.removeEventListener('click', onConfirm);
            cancelBtn.removeEventListener('click', onCancel);
        };

        confirmBtn.addEventListener('click', onConfirm);
        cancelBtn.addEventListener('click', onCancel);

        show();
    });
}

function showToastNotification(message) {
    const toast = document.getElementById('custom-toast');
    const toastMsg = document.getElementById('toast-message');
    if (!toast || !toastMsg) return;

    toastMsg.textContent = message;
    toast.classList.add('active');

    // Snappy: shows for exactly 0.1 seconds (100ms) then disappears
    setTimeout(() => {
        toast.classList.remove('active');
    }, 100);
}

async function deleteSession(threadId) {
    const verify = await confirmHextechPurge();
    if (!verify) return;

    try {
        await fetch(`/api/sessions/${threadId}`, { method: 'DELETE' });

        // Clear cached storage keys
        localStorage.removeItem(`session_title_${threadId}`);

        if (currentThreadId === threadId) {
            currentThreadId = null;
            chatMessagesEl.innerHTML = '';
            currentChatTitle.textContent = 'Select a chat or start a new one';
            renameChatBtn.style.display = 'none';
            chatInput.disabled = true;
            sendBtn.disabled = true;

            // Draw empty dashboard
            renderLandingView();
        }

        fetchSessions();
        showToastNotification("Session Deleted.");
    } catch (err) {
        console.error("Failed to delete session", err);
    }
}

// ---------------------------------------------------------------------------
// Interactive Background Particle System (Canvas)
// ---------------------------------------------------------------------------
let canvas, ctx, animationFrameId;
let particles = [];
const mouse = { x: null, y: null, radius: 110 };

class Particle {
    constructor() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height;
        this.size = Math.random() * 2.5 + 0.5;
        this.speedX = Math.random() * 0.4 - 0.2; // Very slow drift
        this.speedY = Math.random() * 0.4 - 0.2;

        // Alternating gold and cyan dust particles
        this.color = Math.random() > 0.55 ? 'rgba(200, 155, 60, 0.22)' : 'rgba(10, 200, 185, 0.22)';
    }

    update() {
        this.x += this.speedX;
        this.y += this.speedY;

        // Loop back on border collision
        if (this.x < 0) this.x = canvas.width;
        if (this.x > canvas.width) this.x = 0;
        if (this.y < 0) this.y = canvas.height;
        if (this.y > canvas.height) this.y = 0;

        // Mouse interaction attraction/push
        if (mouse.x && mouse.y) {
            let dx = mouse.x - this.x;
            let dy = mouse.y - this.y;
            let dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < mouse.radius) {
                const force = (mouse.radius - dist) / mouse.radius;
                const dirX = dx / dist;
                const dirY = dy / dist;

                // Attract gold particles, repel cyan ones (creates awesome organic visual separation!)
                if (this.color.includes('200')) {
                    this.x += dirX * force * 1.5;
                    this.y += dirY * force * 1.5;
                } else {
                    this.x -= dirX * force * 1.5;
                    this.y -= dirY * force * 1.5;
                }
            }
        }
    }

    draw() {
        ctx.fillStyle = this.color;
        ctx.shadowBlur = this.size * 2;
        ctx.shadowColor = this.color.includes('200') ? 'rgba(200, 155, 60, 0.4)' : 'rgba(10, 200, 185, 0.4)';

        ctx.beginPath();
        // Drawing hextech diamond particles instead of basic circles!
        ctx.moveTo(this.x, this.y - this.size);
        ctx.lineTo(this.x + this.size, this.y);
        ctx.lineTo(this.x, this.y + this.size);
        ctx.lineTo(this.x - this.size, this.y);
        ctx.closePath();
        ctx.fill();

        ctx.shadowBlur = 0; // Reset shadow
    }
}

function initParticlesCanvas() {
    canvas = document.getElementById('particles-canvas');
    ctx = canvas.getContext('2d');

    resizeCanvas();

    // Spawn particles density based on size
    const pCount = Math.floor((canvas.width * canvas.height) / 13000);
    particles = [];
    for (let i = 0; i < Math.min(pCount, 120); i++) {
        particles.push(new Particle());
    }

    // Handle mouse tracking
    window.addEventListener('mousemove', (e) => {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
    });

    window.addEventListener('mouseleave', () => {
        mouse.x = null;
        mouse.y = null;
    });

    window.addEventListener('resize', () => {
        resizeCanvas();
    });

    // Start drawing loop
    animateParticles();
}

function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}

function animateParticles() {
    if (!matrixEnabled) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    particles.forEach(p => {
        p.update();
        p.draw();
    });

    animationFrameId = requestAnimationFrame(animateParticles);
}

function toggleParticles() {
    matrixEnabled = !matrixEnabled;
    if (matrixEnabled) {
        particlesToggle.classList.add('active');
        particlesToggle.innerHTML = '<span class="particles-icon">✨</span> Matrix On';
        initParticlesCanvas();
    } else {
        particlesToggle.classList.remove('active');
        particlesToggle.innerHTML = '<span class="particles-icon">✨</span> Matrix Off';
        cancelAnimationFrame(animationFrameId);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
}

// Kickoff
init();
