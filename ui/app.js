// ==========================================
// CONFIGURATION
// ==========================================
const BACKEND_URL = "http://localhost:8000";
const THREAD_ID_KEY = "enterprise_ai_thread_id";

// ==========================================
// STATE MANAGEMENT
// ==========================================
const state = {
    threadId: localStorage.getItem(THREAD_ID_KEY) || crypto.randomUUID(),
    messages: [],
    isGenerating: false,
    sidebarOpen: window.innerWidth > 1024,
    inspectorOpen: window.innerWidth > 1024,
    currentTab: 'sources',
    graphZoom: 1
};

// Persist thread ID
localStorage.setItem(THREAD_ID_KEY, state.threadId);

// ==========================================
// DOM ELEMENTS
// ==========================================
const elements = {
    systemStatus: document.getElementById('systemStatus'),
    sidebar: document.getElementById('sidebar'),
    inspector: document.getElementById('inspector'),
    chatArea: document.getElementById('chatArea'),
    heroState: document.getElementById('heroState'),
    messagesContainer: document.getElementById('messagesContainer'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    charCounter: document.getElementById('charCounter'),
    mainStatusOrb: document.getElementById('mainStatusOrb'),
    jumpToBottom: document.getElementById('jumpToBottom'),
    graphModal: document.getElementById('graphModal'),
    graphImage: document.getElementById('graphImage'),
    graphContainer: document.getElementById('graphContainer'),
    commandPalette: document.getElementById('commandPalette'),
    commandInput: document.getElementById('commandInput'),
    toastContainer: document.getElementById('toastContainer'),
    conversationList: document.getElementById('conversationList'),
    tabPanes: {
        sources: document.getElementById('tab-sources'),
        activity: document.getElementById('tab-activity'),
        request: document.getElementById('tab-request')
    }
};

// ==========================================
// INITIALIZATION
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    checkBackendHealth();
    setupEventListeners();
    renderMockConversations();
    autoResizeTextarea();
    
    // Check initial screen size
    if (window.innerWidth <= 1024) {
        state.sidebarOpen = false;
        state.inspectorOpen = false;
    }
});

// ==========================================
// API FUNCTIONS
// ==========================================
async function checkBackendHealth() {
    updateSystemStatus('checking', 'Checking System...');
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3000);
        
        const response = await fetch(`${BACKEND_URL}/`, { signal: controller.signal });
        clearTimeout(timeoutId);
        
        if (response.ok) {
            updateSystemStatus('online', 'System Online');
        } else {
            throw new Error('HTTP ' + response.status);
        }
    } catch (error) {
        updateSystemStatus('offline', 'Backend Offline');
        showToast('Unable to reach the AI backend. Check that the FastAPI server is running.', 'error');
    }
}

async function sendMessage(queryText = null) {
    const text = queryText || elements.messageInput.value.trim();
    if (!text || state.isGenerating) return;

    // Update UI
    elements.messageInput.value = '';
    autoResizeTextarea();
    elements.heroState.style.display = 'none';
    state.isGenerating = true;
    elements.sendBtn.disabled = true;
    
    // Add user message
    addMessage('user', text);
    updateCharCounter();
    
    // Show loading state
    const loadingId = showLoadingState();
    updateOrbState('thinking');
    
    // Cycle through loading messages
    const loadingMessages = [
        "Agent is analyzing...",
        "Searching knowledge...",
        "Reranking evidence...",
        "Generating response..."
    ];
    let msgIndex = 0;
    const loadingInterval = setInterval(() => {
        msgIndex = (msgIndex + 1) % loadingMessages.length;
        updateLoadingText(loadingId, loadingMessages[msgIndex]);
        if (msgIndex === 1) updateOrbState('retrieving');
        if (msgIndex === 3) updateOrbState('thinking');
    }, 800);

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout
        
        const startTime = performance.now();
        const response = await fetch(`${BACKEND_URL}/query`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                q: text,
                thread_id: state.threadId
            }),
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        const responseTime = Math.round(performance.now() - startTime);
        
        clearInterval(loadingInterval);
        removeLoadingState(loadingId);
        updateOrbState('idle');
        
        // Process response
        addMessage('assistant', data.answer, {
            thoughtProcess: data.thought_process || [],
            status: data.status || 'Response generated.',
            sources: data.sources || [],
            responseTime: responseTime,
            query: text
        });
        
        updateInspector(data, responseTime);
        state.isGenerating = false;
        elements.sendBtn.disabled = false;
        elements.messageInput.focus();
        
    } catch (error) {
        clearInterval(loadingInterval);
        removeLoadingState(loadingId);
        updateOrbState('error');
        state.isGenerating = false;
        elements.sendBtn.disabled = false;
        
        let errorMsg = "An unexpected error occurred.";
        if (error.name === 'AbortError') {
            errorMsg = "Request timed out. The backend may be overloaded.";
        } else if (error.message.includes('Failed to fetch')) {
            errorMsg = "Unable to reach the AI backend. Check your connection.";
        } else {
            errorMsg = error.message;
        }
        
        addMessage('assistant', `⚠️ **Error**: ${errorMsg}\n\nPlease try again or check system status.`, {
            status: 'Error',
            isError: true
        });
        showToast(errorMsg, 'error');
    }
}

// ==========================================
// UI RENDERING FUNCTIONS
// ==========================================
function addMessage(role, content, metadata = {}) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? 'You' : 'AI';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    if (role === 'assistant') {
        bubble.innerHTML = parseMarkdown(content);
        
        // Add code copy listeners
        bubble.querySelectorAll('pre').forEach(pre => {
            const btn = document.createElement('button');
            btn.className = 'copy-code-btn';
            btn.textContent = 'Copy';
            btn.onclick = () => {
                copyToClipboard(pre.querySelector('code').textContent);
                btn.textContent = 'Copied!';
                setTimeout(() => btn.textContent = 'Copy', 2000);
            };
            pre.appendChild(btn);
        });
        
        // Footer with actions
        const footer = document.createElement('div');
        footer.className = 'message-footer';
        
        const isGrounded = !metadata.isError && metadata.status !== 'Blocked by guardrails.';
        const statusBadge = document.createElement('span');
        statusBadge.className = 'status-badge';
        statusBadge.innerHTML = isGrounded ? '✓ Grounded response' : '⚠️ ' + metadata.status;
        footer.appendChild(statusBadge);
        
        if (!metadata.isError) {
            footer.innerHTML += `
                <button class="action-btn" onclick="copyToClipboard(this.closest('.message').querySelector('.markdown-body').innerText)">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    Copy
                </button>
                <button class="action-btn" onclick="showToast('Regeneration not implemented in demo', 'success')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
                    Regenerate
                </button>
                <button class="action-btn" onclick="showToast('Feedback recorded', 'success')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>
                    Useful
                </button>
            `;
        }
        contentDiv.appendChild(footer);
    } else {
        bubble.textContent = content;
    }
    
    contentDiv.insertBefore(bubble, contentDiv.firstChild);
    msgDiv.appendChild(avatar);
    msgDiv.appendChild(contentDiv);
    
    elements.messagesContainer.appendChild(msgDiv);
    scrollToBottom();
    
    // Store in state
    state.messages.push({ role, content, metadata });
}

function showLoadingState() {
    const id = 'loading-' + Date.now();
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message assistant';
    msgDiv.id = id;
    msgDiv.innerHTML = `
        <div class="message-avatar">AI</div>
        <div class="message-content">
            <div class="message-bubble">
                <div class="shimmer" style="height: 20px; width: 80%; margin-bottom: 10px;"></div>
                <div class="shimmer" style="height: 20px; width: 60%; margin-bottom: 10px;"></div>
                <div class="shimmer" style="height: 20px; width: 90%;"></div>
                <div style="margin-top: 1rem; font-size: 0.85rem; color: var(--accent-primary);" class="loading-text">
                    Agent is analyzing...
                </div>
            </div>
        </div>
    `;
    elements.messagesContainer.appendChild(msgDiv);
    scrollToBottom();
    return id;
}

function updateLoadingText(id, text) {
    const el = document.getElementById(id);
    if (el) {
        el.querySelector('.loading-text').textContent = text;
    }
}

function removeLoadingState(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function updateInspector(data, responseTime) {
    // Sources Tab
    if (data.sources && data.sources.length > 0) {
        elements.tabPanes.sources.innerHTML = data.sources.map((source, idx) => `
            <div class="source-card">
                <div class="source-header">
                    <span class="source-id">Source ${String(idx + 1).padStart(2, '0')}</span>
                    <button class="icon-btn-sm" onclick="copyToClipboard(\`${source.replace(/`/g, '\\`')}\`)" title="Copy source">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    </button>
                </div>
                <div class="source-content" onclick="this.classList.toggle('expanded')">
                    ${source}
                </div>
            </div>
        `).join('');
    } else {
        elements.tabPanes.sources.innerHTML = '<div class="empty-state-small">No knowledge sources were required for this response.</div>';
    }
    
    // Activity Tab
    if (data.thought_process && data.thought_process.length > 0) {
        elements.tabPanes.activity.innerHTML = data.thought_process.map((step, idx) => `
            <div class="agent-step ${idx < data.thought_process.length - 1 ? 'completed' : 'active'}">
                <div>
                    <div class="step-label">${step}</div>
                </div>
            </div>
        `).join('');
    } else {
        elements.tabPanes.activity.innerHTML = '<div class="empty-state-small">No agent activity trace available.</div>';
    }
    
    // Request Info Tab
    elements.tabPanes.request.innerHTML = `
        <div class="request-info-row">
            <span class="label">Query</span>
            <span class="value">${data.question || 'N/A'}</span>
        </div>
        <div class="request-info-row">
            <span class="label">Thread ID</span>
            <span class="value">${state.threadId}</span>
        </div>
        <div class="request-info-row">
            <span class="label">Status</span>
            <span class="value" style="color: ${data.status === 'Blocked by guardrails.' ? 'var(--error)' : 'var(--success)'}">${data.status}</span>
        </div>
        <div class="request-info-row">
            <span class="label">Response Time</span>
            <span class="value">${responseTime}ms</span>
        </div>
        <div class="request-info-row">
            <span class="label">Sources</span>
            <span class="value">${data.sources ? data.sources.length : 0}</span>
        </div>
        <div class="request-info-row">
            <span class="label">Agent State</span>
            <span class="value">Idle</span>
        </div>
    `;
    
    // Switch to sources tab if there are sources, else activity
    if (data.sources && data.sources.length > 0) {
        switchTab('sources');
    } else {
        switchTab('activity');
    }
}

// ==========================================
// MARKDOWN PARSER (Lightweight)
// ==========================================
function parseMarkdown(text) {
    if (!text) return '';
    
    let html = text
        // Escape HTML
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        // Code blocks
        .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
        // Inline code
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        // Bold
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Italic
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        // Headings
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        // Unordered lists
        .replace(/^\s*[-*+]\s+(.*$)/gim, '<li>$1</li>')
        // Ordered lists
        .replace(/^\s*\d+\.\s+(.*$)/gim, '<li>$1</li>')
        // Wrap consecutive lis in ul
        .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
        // Paragraphs (simple)
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');
    
    return `<div class="markdown-body"><p>${html}</p></div>`;
}

// ==========================================
// UTILITY FUNCTIONS
// ==========================================
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard', 'success');
    }).catch(() => {
        showToast('Failed to copy', 'error');
    });
}

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            ${type === 'success' 
                ? '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>'
                : '<circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line>'}
        </svg>
        <span>${message}</span>
    `;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function updateSystemStatus(status, text) {
    const dot = elements.systemStatus.querySelector('.status-dot');
    const txt = elements.systemStatus.querySelector('.status-text');
    dot.className = `status-dot ${status}`;
    txt.textContent = text;
}

function updateOrbState(stateName) {
    elements.mainStatusOrb.className = `status-orb ${stateName}`;
}

function switchTab(tabName) {
    state.currentTab = tabName;
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    Object.values(elements.tabPanes).forEach(pane => {
        pane.classList.remove('active');
    });
    if (elements.tabPanes[tabName]) {
        elements.tabPanes[tabName].classList.add('active');
    }
}

function scrollToBottom() {
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}

function autoResizeTextarea() {
    elements.messageInput.style.height = 'auto';
    elements.messageInput.style.height = Math.min(elements.messageInput.scrollHeight, 200) + 'px';
}

function updateCharCounter() {
    const len = elements.messageInput.value.length;
    elements.charCounter.textContent = `${len}/2000`;
    elements.charCounter.style.color = len > 1800 ? 'var(--error)' : 'var(--text-muted)';
}

function clearConversation() {
    if (confirm('Are you sure you want to clear this conversation?')) {
        state.messages = [];
        elements.messagesContainer.innerHTML = '';
        elements.heroState.style.display = 'flex';
        // Reset inspector
        elements.tabPanes.sources.innerHTML = '<div class="empty-state-small">No knowledge sources retrieved yet.</div>';
        elements.tabPanes.activity.innerHTML = '<div class="empty-state-small">Agent activity trace will appear here.</div>';
        elements.tabPanes.request.innerHTML = '<div class="empty-state-small">Request metadata will appear here.</div>';
        showToast('Conversation cleared', 'success');
    }
}

function renderMockConversations() {
    const mocks = [
        { icon: '🔍', title: 'Knowledge Search', time: '2m ago' },
        { icon: '🔧', title: 'System Troubleshooting', time: '1h ago' },
        { icon: '📜', title: 'Policy Analysis', time: '3h ago' },
        { icon: '📄', title: 'Technical Documentation', time: '1d ago' }
    ];
    elements.conversationList.innerHTML = mocks.map((m, i) => `
        <div class="conv-item ${i === 0 ? 'active' : ''}">
            <span>${m.icon}</span>
            <div style="flex: 1; overflow: hidden;">
                <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${m.title}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">${m.time}</div>
            </div>
        </div>
    `).join('');
}

// ==========================================
// EVENT LISTENERS
// ==========================================
function setupEventListeners() {
    // Input handling
    elements.messageInput.addEventListener('input', () => {
        autoResizeTextarea();
        updateCharCounter();
    });
    
    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    elements.sendBtn.addEventListener('click', () => sendMessage());
    
    // Suggestion cards
    document.querySelectorAll('.suggestion-card').forEach(card => {
        card.addEventListener('click', () => {
            sendMessage(card.dataset.query);
        });
    });
    
    // Scroll handling
    elements.messagesContainer.addEventListener('scroll', () => {
        const { scrollTop, scrollHeight, clientHeight } = elements.messagesContainer;
        if (scrollHeight - scrollTop - clientHeight > 200) {
            elements.jumpToBottom.classList.add('visible');
        } else {
            elements.jumpToBottom.classList.remove('visible');
 }
    });
    
    elements.jumpToBottom.addEventListener('click', scrollToBottom);
    
    // Sidebar & Inspector toggles
    document.getElementById('toggleSidebar').addEventListener('click', () => {
        state.sidebarOpen = !state.sidebarOpen;
        elements.sidebar.classList.toggle('open', state.sidebarOpen);
    });
    
    document.getElementById('toggleInspector').addEventListener('click', () => {
        state.inspectorOpen = !state.inspectorOpen;
        elements.inspector.classList.toggle('open', state.inspectorOpen);
    });
    
    document.getElementById('newChatBtn').addEventListener('click', () => {
        state.threadId = crypto.randomUUID();
        localStorage.setItem(THREAD_ID_KEY, state.threadId);
        clearConversation();
        showToast('New conversation started', 'success');
    });
    
    document.getElementById('clearChatBtn').addEventListener('click', clearConversation);
    
    // Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
    
    // Graph Modal
    document.getElementById('viewGraphBtn').addEventListener('click', openGraphModal);
    document.querySelectorAll('.close-modal').forEach(btn => {
        btn.addEventListener('click', () => {
            elements.graphModal.classList.remove('active');
            elements.commandPalette.classList.remove('active');
        });
    });
    
    document.getElementById('zoomIn').addEventListener('click', () => {
        state.graphZoom = Math.min(state.graphZoom + 0.2, 3);
        elements.graphImage.style.transform = `scale(${state.graphZoom})`;
    });
    
    document.getElementById('zoomOut').addEventListener('click', () => {
        state.graphZoom = Math.max(state.graphZoom - 0.2, 0.5);
        elements.graphImage.style.transform = `scale(${state.graphZoom})`;
    });
    
    document.getElementById('zoomReset').addEventListener('click', () => {
        state.graphZoom = 1;
        elements.graphImage.style.transform = `scale(1)`;
    });
    
    // Command Palette
    document.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            openCommandPalette();
        }
        if (e.key === 'Escape') {
            elements.graphModal.classList.remove('active');
            elements.commandPalette.classList.remove('active');
        }
    });
    
    document.querySelectorAll('.command-item').forEach(item => {
        item.addEventListener('click', () => {
            const action = item.dataset.action;
            elements.commandPalette.classList.remove('active');
            
            switch(action) {
                case 'newChat': document.getElementById('newChatBtn').click(); break;
                case 'clearChat': clearConversation(); break;
                case 'toggleSidebar': document.getElementById('toggleSidebar').click(); break;
                case 'toggleInspector': document.getElementById('toggleInspector').click(); break;
                case 'viewGraph': openGraphModal(); break;
                case 'focusInput': elements.messageInput.focus(); break;
            }
        });
    });
    
    // Close modals on outside click
    elements.graphModal.addEventListener('click', (e) => {
        if (e.target === elements.graphModal) elements.graphModal.classList.remove('active');
    });
    elements.commandPalette.addEventListener('click', (e) => {
        if (e.target === elements.commandPalette) elements.commandPalette.classList.remove('active');
    });
}

function openGraphModal() {
    elements.graphImage.src = `${BACKEND_URL}/graph?t=${Date.now()}`;
    state.graphZoom = 1;
    elements.graphImage.style.transform = 'scale(1)';
    elements.graphModal.classList.add('active');
    showToast('Agent graph loaded', 'success');
}

function openCommandPalette() {
    elements.commandPalette.classList.add('active');
    elements.commandInput.value = '';
    elements.commandInput.focus();
}