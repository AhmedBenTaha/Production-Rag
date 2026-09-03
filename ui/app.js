/**
 * Enterprise AI Copilot - Vanilla JS Application
 * Modular architecture: State, API, UI, Utils
 */

// ==========================================
// 1. STATE MANAGEMENT
// ==========================================

const State = {
    threadId:
        localStorage.getItem("nexus_thread_id") ||
        "default_user",

    messages: JSON.parse(
        localStorage.getItem("nexus_messages") || "[]"
    ),

    theme:
        localStorage.getItem("nexus_theme") || "dark",

    isProcessing: false,

    save() {
        localStorage.setItem(
            "nexus_thread_id",
            this.threadId
        );

        localStorage.setItem(
            "nexus_messages",
            JSON.stringify(this.messages)
        );

        localStorage.setItem(
            "nexus_theme",
            this.theme
        );
    },

    clear() {
        this.messages = [];
        this.threadId = this.generateThreadId();
        this.save();
    },

    generateThreadId() {
        return (
            "thread_" +
            Math.random()
                .toString(36)
                .substring(2, 15)
        );
    },

    addMessage(role, content, metadata = {}) {
        const msg = {
            id: Date.now().toString(),
            role,
            content,
            timestamp: new Date().toISOString(),
            ...metadata
        };

        this.messages.push(msg);
        this.save();

        return msg;
    }
};


// ==========================================
// 2. API CLIENT
// ==========================================

const API = {

    /*
     * IMPORTANT:
     * The frontend is running on:
     *
     * http://127.0.0.1:5500
     *
     * while FastAPI is running on:
     *
     * http://127.0.0.1:8000
     *
     * Therefore requests MUST go to port 8000.
     */
    baseURL: "http://127.0.0.1:8000",

    async checkHealth() {
        try {
            const res = await fetch(
                `${this.baseURL}/`
            );

            if (!res.ok) {
                throw new Error(
                    `Health check failed: HTTP ${res.status}`
                );
            }

            const data = await res.json();

            UI.updateConnectionStatus(true);

            return data;

        } catch (err) {

            UI.updateConnectionStatus(false);

            console.error(
                "Health check failed:",
                err
            );

            throw err;
        }
    },


    async queryRAG(question) {

        const payload = {
            q: question,
            thread_id: State.threadId
        };

        console.log(
            "Sending request to backend:",
            payload
        );

        try {

            const response = await fetch(
                `${this.baseURL}/query`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify(payload)
                }
            );

            if (!response.ok) {

                let errorMessage =
                    `HTTP ${response.status}: ${response.statusText}`;

                try {

                    const errorData =
                        await response.json();

                    if (errorData.detail) {
                        errorMessage =
                            typeof errorData.detail ===
                            "string"
                                ? errorData.detail
                                : JSON.stringify(
                                      errorData.detail
                                  );
                    }

                } catch (_) {
                    // Ignore JSON parsing errors
                }

                throw new Error(errorMessage);
            }

            const data =
                await response.json();

            console.log(
                "Backend response:",
                data
            );

            if (data.status === "error") {

                throw new Error(
                    data.answer ||
                    "Internal server error occurred"
                );
            }

            return data;

        } catch (err) {

            console.error(
                "RAG request failed:",
                err
            );

            throw err;
        }
    },


    async getGraphImage() {

        const response =
            await fetch(
                `${this.baseURL}/graph`
            );

        if (!response.ok) {

            throw new Error(
                `Failed to fetch graph: HTTP ${response.status}`
            );
        }

        const blob =
            await response.blob();

        return URL.createObjectURL(blob);
    }
};


// ==========================================
// 3. UI CONTROLLER
// ==========================================

const UI = {

    elements: {

        chatContainer:
            document.getElementById(
                "chat-container"
            ),

        messagesList:
            document.getElementById(
                "messages-list"
            ),

        welcomeScreen:
            document.getElementById(
                "welcome-screen"
            ),

        loadingIndicator:
            document.getElementById(
                "loading-indicator"
            ),

        messageInput:
            document.getElementById(
                "message-input"
            ),

        sendBtn:
            document.getElementById(
                "send-btn"
            ),

        charCounter:
            document.getElementById(
                "char-counter"
            ),

        sidebar:
            document.getElementById(
                "sidebar"
            ),

        sidebarOverlay:
            document.getElementById(
                "sidebar-overlay"
            ),

        threadList:
            document.getElementById(
                "thread-list"
            ),

        toastContainer:
            document.getElementById(
                "toast-container"
            ),

        currentThreadIdDisplay:
            document.getElementById(
                "current-thread-id"
            )
    },


    init() {

        this.applyTheme(
            State.theme
        );

        this.renderMessages();

        this.updateThreadIdDisplay();

        this.setupEventListeners();

        this.setupMarkdown();

        // Initial health check
        API.checkHealth().catch(() => {

            this.showToast(
                "Unable to reach the AI service. Check backend.",
                "error"
            );
        });
    },


    setupMarkdown() {

        if (typeof marked === "undefined") {

            console.warn(
                "Marked.js is not loaded."
            );

            return;
        }

        marked.setOptions({

            highlight: function (
                code,
                lang
            ) {

                if (
                    typeof hljs ===
                    "undefined"
                ) {
                    return code;
                }

                const language =
                    hljs.getLanguage(lang)
                        ? lang
                        : "plaintext";

                return hljs.highlight(
                    code,
                    {
                        language
                    }
                ).value;
            },

            langPrefix:
                "hljs language-"
        });
    },


    setupEventListeners() {

        // ======================================
        // Input auto-grow & validation
        // ======================================

        if (
            this.elements.messageInput
        ) {

            this.elements.messageInput
                .addEventListener(
                    "input",
                    () => {

                        this.autoGrowTextarea(
                            this.elements
                                .messageInput
                        );

                        const len =
                            this.elements
                                .messageInput
                                .value.length;

                        this.elements
                            .charCounter
                            .textContent = len;

                        this.elements
                            .sendBtn
                            .disabled =
                            len === 0 ||
                            State.isProcessing;
                    }
                );


            // Enter to send
            // Shift + Enter = newline

            this.elements.messageInput
                .addEventListener(
                    "keydown",
                    (e) => {

                        if (
                            e.key === "Enter" &&
                            !e.shiftKey
                        ) {

                            e.preventDefault();

                            this.handleSend();
                        }
                    }
                );
        }


        // ======================================
        // Send button
        // ======================================

        if (this.elements.sendBtn) {

            this.elements.sendBtn
                .addEventListener(
                    "click",
                    () => this.handleSend()
                );
        }


        // ======================================
        // Sidebar
        // ======================================

        const toggleSidebar =
            document.getElementById(
                "toggle-sidebar"
            );

        if (toggleSidebar) {

            toggleSidebar.addEventListener(
                "click",
                () =>
                    this.toggleSidebar(true)
            );
        }


        const closeSidebarMobile =
            document.getElementById(
                "close-sidebar-mobile"
            );

        if (closeSidebarMobile) {

            closeSidebarMobile
                .addEventListener(
                    "click",
                    () =>
                        this.toggleSidebar(
                            false
                        )
                );
        }


        if (
            this.elements
                .sidebarOverlay
        ) {

            this.elements
                .sidebarOverlay
                .addEventListener(
                    "click",
                    () =>
                        this.toggleSidebar(
                            false
                        )
                );
        }


        // ======================================
        // New Chat
        // ======================================

        const newChatBtn =
            document.getElementById(
                "new-chat-btn"
            );

        if (newChatBtn) {

            newChatBtn.addEventListener(
                "click",
                () => {

                    State.clear();

                    this.renderMessages();

                    this.updateThreadIdDisplay();

                    this.showToast(
                        "New conversation started",
                        "success"
                    );

                    if (
                        window.innerWidth <=
                        768
                    ) {

                        this.toggleSidebar(
                            false
                        );
                    }
                }
            );
        }


        // ======================================
        // Clear History
        // ======================================

        const clearHistoryBtn =
            document.getElementById(
                "clear-history-btn"
            );

        if (clearHistoryBtn) {

            clearHistoryBtn
                .addEventListener(
                    "click",
                    () => {

                        State.clear();

                        this.renderMessages();

                        this.updateThreadIdDisplay();

                        this.showToast(
                            "Local history cleared",
                            "success"
                        );
                    }
                );
        }


        // ======================================
        // Theme Toggle
        // ======================================

        const themeToggle =
            document.getElementById(
                "theme-toggle"
            );

        if (themeToggle) {

            themeToggle.addEventListener(
                "click",
                () => {

                    const newTheme =
                        State.theme === "dark"
                            ? "light"
                            : "dark";

                    State.theme =
                        newTheme;

                    State.save();

                    this.applyTheme(
                        newTheme
                    );

                    const themeSelect =
                        document.getElementById(
                            "theme-select"
                        );

                    if (themeSelect) {
                        themeSelect.value =
                            newTheme;
                    }
                }
            );
        }


        const themeSelect =
            document.getElementById(
                "theme-select"
            );

        if (themeSelect) {

            themeSelect.addEventListener(
                "change",
                (e) => {

                    State.theme =
                        e.target.value;

                    State.save();

                    this.applyTheme(
                        State.theme
                    );
                }
            );
        }


        // ======================================
        // Settings Modal
        // ======================================

        const settingsModal =
            document.getElementById(
                "settings-modal"
            );

        const settingsBtn =
            document.getElementById(
                "settings-btn"
            );

        if (
            settingsBtn &&
            settingsModal
        ) {

            settingsBtn.addEventListener(
                "click",
                () => {

                    settingsModal.classList
                        .remove("hidden");

                    settingsModal.setAttribute(
                        "aria-hidden",
                        "false"
                    );
                }
            );

            this.setupModalClose(
                settingsModal
            );
        }


        // ======================================
        // Graph Modal
        // ======================================

        const graphModal =
            document.getElementById(
                "graph-modal"
            );

        const viewGraphBtn =
            document.getElementById(
                "view-graph-btn"
            );

        if (
            viewGraphBtn &&
            graphModal
        ) {

            viewGraphBtn.addEventListener(
                "click",
                async () => {

                    graphModal.classList
                        .remove("hidden");

                    graphModal.setAttribute(
                        "aria-hidden",
                        "false"
                    );

                    const container =
                        document.getElementById(
                            "graph-container"
                        );

                    if (!container) {
                        return;
                    }

                    container.innerHTML =
                        "<p>Loading graph visualization...</p>";

                    try {

                        const imgUrl =
                            await API.getGraphImage();

                        container.innerHTML = `
                            <img
                                src="${imgUrl}"
                                alt="LangGraph Architecture"
                            >
                        `;

                    } catch (err) {

                        console.error(
                            "Graph loading failed:",
                            err
                        );

                        container.innerHTML =
                            `
                            <p style="color: var(--error)">
                                Failed to load graph.
                                Ensure backend is running.
                            </p>
                            `;
                    }
                }
            );

            this.setupModalClose(
                graphModal
            );
        }


        // ======================================
        // Regenerate Thread
        // ======================================

        const regenerateThreadBtn =
            document.getElementById(
                "regenerate-thread-btn"
            );

        if (
            regenerateThreadBtn
        ) {

            regenerateThreadBtn
                .addEventListener(
                    "click",
                    () => {

                        State.threadId =
                            State.generateThreadId();

                        State.save();

                        this.updateThreadIdDisplay();

                        this.showToast(
                            "New thread ID generated",
                            "success"
                        );
                    }
                );
        }


        // ======================================
        // Clear All Data
        // ======================================

        const clearAllDataBtn =
            document.getElementById(
                "clear-all-data-btn"
            );

        if (clearAllDataBtn) {

            clearAllDataBtn
                .addEventListener(
                    "click",
                    () => {

                        if (
                            confirm(
                                "Are you sure? This will delete all local conversations and settings."
                            )
                        ) {

                            localStorage.clear();

                            location.reload();
                        }
                    }
                );
        }


        // ======================================
        // Suggestion Cards
        // ======================================

        document
            .querySelectorAll(
                ".suggestion-card"
            )
            .forEach((card) => {

                card.addEventListener(
                    "click",
                    () => {

                        const query =
                            card.getAttribute(
                                "data-query"
                            );

                        if (
                            !query ||
                            !this.elements
                                .messageInput
                        ) {
                            return;
                        }

                        this.elements
                            .messageInput
                            .value = query;

                        this.elements
                            .messageInput
                            .dispatchEvent(
                                new Event(
                                    "input"
                                )
                            );

                        this.handleSend();
                    }
                );
            });


        // ======================================
        // Window Resize
        // ======================================

        window.addEventListener(
            "resize",
            () => {

                if (
                    window.innerWidth >
                    768
                ) {

                    if (
                        this.elements
                            .sidebarOverlay
                    ) {

                        this.elements
                            .sidebarOverlay
                            .classList
                            .remove(
                                "active"
                            );
                    }

                    if (
                        this.elements
                            .sidebar
                    ) {

                        this.elements
                            .sidebar
                            .classList
                            .remove(
                                "open"
                            );
                    }
                }
            }
        );
    },


    setupModalClose(modal) {

        if (!modal) {
            return;
        }

        const closeBtn =
            modal.querySelector(
                ".close-modal"
            );

        if (closeBtn) {

            closeBtn.addEventListener(
                "click",
                () => {

                    modal.classList.add(
                        "hidden"
                    );

                    modal.setAttribute(
                        "aria-hidden",
                        "true"
                    );
                }
            );
        }


        modal.addEventListener(
            "click",
            (e) => {

                if (
                    e.target === modal
                ) {

                    modal.classList.add(
                        "hidden"
                    );

                    modal.setAttribute(
                        "aria-hidden",
                        "true"
                    );
                }
            }
        );
    },


    applyTheme(theme) {

        if (theme === "system") {

            const prefersDark =
                window.matchMedia(
                    "(prefers-color-scheme: dark)"
                ).matches;

            document.documentElement
                .setAttribute(
                    "data-theme",
                    prefersDark
                        ? "dark"
                        : "light"
                );

        } else {

            document.documentElement
                .setAttribute(
                    "data-theme",
                    theme
                );
        }
    },


    toggleSidebar(
        forceOpen = null
    ) {

        const isMobile =
            window.innerWidth <= 768;

        if (isMobile) {

            if (
                forceOpen === true ||
                !this.elements
                    .sidebar
                    .classList
                    .contains("open")
            ) {

                this.elements
                    .sidebar
                    .classList
                    .add("open");

                this.elements
                    .sidebarOverlay
                    .classList
                    .add("active");

            } else {

                this.elements
                    .sidebar
                    .classList
                    .remove("open");

                this.elements
                    .sidebarOverlay
                    .classList
                    .remove(
                        "active"
                    );
            }

        } else {

            this.elements
                .sidebar
                .classList
                .toggle(
                    "collapsed"
                );
        }
    },


    autoGrowTextarea(el) {

        if (!el) {
            return;
        }

        el.style.height = "auto";

        el.style.height =
            Math.min(
                el.scrollHeight,
                200
            ) + "px";
    },


    // ======================================
    // SEND QUERY
    // ======================================

    async handleSend() {

        const input =
            this.elements.messageInput;

        if (!input) {
            return;
        }

        const query =
            input.value.trim();

        if (
            !query ||
            State.isProcessing
        ) {
            return;
        }


        // ======================================
        // Add user message
        // ======================================

        State.addMessage(
            "user",
            query
        );

        this.renderMessages();


        // ======================================
        // Clear input
        // ======================================

        input.value = "";

        input.style.height =
            "auto";

        if (
            this.elements.charCounter
        ) {

            this.elements
                .charCounter
                .textContent = "0";
        }

        if (
            this.elements.sendBtn
        ) {

            this.elements
                .sendBtn
                .disabled = true;
        }


        // ======================================
        // Show loading
        // ======================================

        State.isProcessing =
            true;

        if (
            this.elements
                .loadingIndicator
        ) {

            this.elements
                .loadingIndicator
                .classList
                .remove("hidden");
        }

        this.scrollToBottom();


        try {

            // ==================================
            // Call FastAPI backend
            // ==================================

            const response =
                await API.queryRAG(
                    query
                );


            // ==================================
            // Add assistant response
            // ==================================

            State.addMessage(
                "assistant",
                response.answer ||
                    "No response generated.",
                {
                    thought_process:
                        response.thought_process ||
                        [],

                    sources:
                        response.sources ||
                        [],

                    status:
                        response.status ||
                        "Completed"
                }
            );


            this.renderMessages();

            this.showToast(
                "Response generated",
                "success"
            );


        } catch (error) {

            console.error(
                "Query failed:",
                error
            );

            State.addMessage(
                "assistant",
                `⚠️ **Error**: ${error.message}. Please try again.`,
                {
                    status: "error"
                }
            );

            this.renderMessages();

            this.showToast(
                "Request failed",
                "error"
            );


        } finally {

            State.isProcessing =
                false;

            if (
                this.elements
                    .loadingIndicator
            ) {

                this.elements
                    .loadingIndicator
                    .classList
                    .add("hidden");
            }

            if (
                this.elements.sendBtn
            ) {

                this.elements
                    .sendBtn
                    .disabled = false;
            }

            input.focus();

            this.scrollToBottom();
        }
    },


    // ======================================
    // RENDER MESSAGES
    // ======================================

    renderMessages() {

        const {
            messagesList,
            welcomeScreen
        } = this.elements;

        if (
            !messagesList ||
            !welcomeScreen
        ) {
            return;
        }

        messagesList.innerHTML = "";


        if (
            State.messages.length === 0
        ) {

            welcomeScreen.classList
                .remove("hidden");

            return;
        }


        welcomeScreen.classList
            .add("hidden");


        State.messages.forEach(
            (msg) => {

                const msgEl =
                    document.createElement(
                        "div"
                    );

                msgEl.className =
                    `message ${msg.role}`;


                const avatar =
                    msg.role ===
                    "assistant"
                        ? "◈"
                        : "👤";


                const time =
                    new Date(
                        msg.timestamp
                    ).toLocaleTimeString(
                        [],
                        {
                            hour: "2-digit",
                            minute: "2-digit"
                        }
                    );


                let contentHtml = "";


                // ==================================
                // Assistant message
                // ==================================

                if (
                    msg.role ===
                    "assistant"
                ) {

                    // Execution timeline
                    if (
                        msg.thought_process &&
                        msg.thought_process
                            .length > 0
                    ) {

                        contentHtml +=
                            this.renderThoughtProcess(
                                msg.thought_process,
                                msg.status
                            );
                    }


                    // Markdown
                    const rawHtml =
                        typeof marked !==
                        "undefined"
                            ? marked.parse(
                                  msg.content
                              )
                            : this.escapeHtml(
                                  msg.content
                              );


                    const cleanHtml =
                        typeof DOMPurify !==
                        "undefined"
                            ? DOMPurify.sanitize(
                                  rawHtml
                              )
                            : rawHtml;


                    contentHtml += `
                        <div class="markdown-body">
                            ${cleanHtml}
                        </div>
                    `;


                    // Sources
                    if (
                        msg.sources &&
                        msg.sources.length > 0
                    ) {

                        contentHtml +=
                            this.renderSources(
                                msg.sources
                            );
                    }


                } else {

                    const rawHtml =
                        typeof marked !==
                        "undefined"
                            ? marked.parse(
                                  msg.content
                              )
                            : this.escapeHtml(
                                  msg.content
                              );


                    const cleanHtml =
                        typeof DOMPurify !==
                        "undefined"
                            ? DOMPurify.sanitize(
                                  rawHtml
                              )
                            : rawHtml;


                    contentHtml = `
                        <div class="markdown-body">
                            ${cleanHtml}
                        </div>
                    `;
                }


                // ==================================
                // Message HTML
                // ==================================

                msgEl.innerHTML = `

                    <div class="message-avatar">
                        ${avatar}
                    </div>

                    <div class="message-content">

                        <div class="message-bubble">

                            ${contentHtml}

                        </div>

                        <div class="message-meta">

                            <span>
                                ${time}
                            </span>

                            <button
                                class="copy-btn"
                                onclick="UI.copyToClipboard('${msg.id}')"
                                aria-label="Copy message"
                            >

                                <svg
                                    width="14"
                                    height="14"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="currentColor"
                                    stroke-width="2"
                                >
                                    <rect
                                        x="9"
                                        y="9"
                                        width="13"
                                        height="13"
                                        rx="2"
                                    ></rect>

                                    <path
                                        d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
                                    ></path>
                                </svg>

                                Copy

                            </button>

                        </div>

                    </div>
                `;


                messagesList.appendChild(
                    msgEl
                );
            }
        );


        // ======================================
        // Highlight code
        // ======================================

        if (
            typeof hljs !==
            "undefined"
        ) {

            document
                .querySelectorAll(
                    "pre code"
                )
                .forEach(
                    (block) => {

                        try {
                            hljs.highlightElement(
                                block
                            );
                        } catch (err) {
                            console.warn(
                                "Syntax highlighting failed:",
                                err
                            );
                        }
                    }
                );
        }


        // ======================================
        // Code block copy buttons
        // ======================================

        document
            .querySelectorAll(
                "pre"
            )
            .forEach((pre) => {

                // Prevent duplicate headers
                if (
                    pre.previousElementSibling &&
                    pre.previousElementSibling
                        .classList
                        .contains(
                            "code-block-header"
                        )
                ) {
                    return;
                }


                const code =
                    pre.querySelector(
                        "code"
                    );

                if (!code) {
                    return;
                }


                const language =
                    code.className
                        .replace(
                            "hljs language-",
                            ""
                        )
                        .replace(
                            "language-",
                            ""
                        )
                        .toUpperCase() ||
                    "CODE";


                const header =
                    document.createElement(
                        "div"
                    );

                header.className =
                    "code-block-header";


                header.innerHTML = `

                    <span>
                        ${this.escapeHtml(
                            language
                        )}
                    </span>

                    <button
                        onclick="UI.copyCode(this)"
                    >
                        Copy
                    </button>

                `;


                pre.parentNode.insertBefore(
                    header,
                    pre
                );

                header.appendChild(
                    pre
                );
            });


        this.scrollToBottom();
    },


    // ======================================
    // EXECUTION TIMELINE
    // ======================================

    renderThoughtProcess(
        process,
        status
    ) {

        const isComplete =
            status === "Completed" ||
            status === "completed";


        let html = `

            <div class="thought-process">

                <div class="thought-process-title">

                    <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                    >

                        <circle
                            cx="12"
                            cy="12"
                            r="10"
                        ></circle>

                        <polyline
                            points="12 6 12 12 16 14"
                        ></polyline>

                    </svg>

                    Execution Timeline

                </div>

                <div class="timeline">

        `;


        process.forEach(
            (step, index) => {

                const isLast =
                    index ===
                    process.length - 1;


                const stateClass =
                    isComplete
                        ? "completed"
                        : isLast
                            ? "active"
                            : "completed";


                const icon =
                    isComplete
                        ? "✓"
                        : isLast
                            ? "●"
                            : "○";


                html += `

                    <div
                        class="timeline-item ${stateClass}"
                    >

                        <span class="timeline-icon">
                            ${icon}
                        </span>

                        <span>
                            ${this.escapeHtml(
                                String(step)
                            )}
                        </span>

                    </div>

                `;
            }
        );


        html += `

                </div>

            </div>

        `;


        return html;
    },


    // ======================================
    // SOURCES
    // ======================================

    renderSources(sources) {

        const normalizedSources =
            sources.map((s) => {

                if (
                    typeof s ===
                    "string"
                ) {

                    return {
                        name: "Document",
                        content: s,
                        type: "text"
                    };
                }


                return {

                    name:
                        s.metadata?.source ||
                        s.metadata?.title ||
                        "Unknown Source",

                    content:
                        s.page_content ||
                        s.content ||
                        JSON.stringify(s),

                    type:
                        s.metadata?.type ||
                        "document"
                };
            });


        let html = `

            <div class="sources-section">

                <button
                    class="sources-toggle"
                    onclick="
                        this.nextElementSibling
                            .classList
                            .toggle('hidden')
                    "
                >

                    <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                    >

                        <polyline
                            points="6 9 12 15 18 9"
                        ></polyline>

                    </svg>

                    ${normalizedSources.length}
                    Source(s) Retrieved

                </button>

                <div class="sources-list hidden">

        `;


        normalizedSources.forEach(
            (src) => {

                const content =
                    String(
                        src.content || ""
                    );


                html += `

                    <div class="source-card">

                        <div class="source-header">

                            <span class="source-name">
                                ${this.escapeHtml(
                                    src.name
                                )}
                            </span>

                            <span class="source-type">
                                ${this.escapeHtml(
                                    src.type
                                )}
                            </span>

                        </div>

                        <div class="source-preview">

                            ${this.escapeHtml(
                                content.substring(
                                    0,
                                    150
                                )
                            )}${content.length > 150 ? "..." : ""}

                        </div>

                    </div>

                `;
            }
        );


        html += `

                </div>

            </div>

        `;


        return html;
    },


    // ======================================
    // HTML ESCAPING
    // ======================================

    escapeHtml(text) {

        const div =
            document.createElement(
                "div"
            );

        div.textContent =
            String(text ?? "");

        return div.innerHTML;
    },


    // ======================================
    // COPY MESSAGE
    // ======================================

    copyToClipboard(msgId) {

        const msg =
            State.messages.find(
                (m) =>
                    m.id === msgId
            );

        if (!msg) {
            return;
        }


        navigator.clipboard
            .writeText(msg.content)
            .then(() => {

                this.showToast(
                    "Copied to clipboard",
                    "success"
                );

            })
            .catch((err) => {

                console.error(
                    "Clipboard error:",
                    err
                );

                this.showToast(
                    "Failed to copy",
                    "error"
                );
            });
    },


    // ======================================
    // COPY CODE
    // ======================================

    copyCode(btn) {

        if (!btn) {
            return;
        }


        const header =
            btn.parentElement;

        const pre =
            header.querySelector(
                "pre"
            ) ||
            header.nextElementSibling;


        if (!pre) {
            return;
        }


        const code =
            pre.querySelector(
                "code"
            );


        if (!code) {
            return;
        }


        navigator.clipboard
            .writeText(
                code.textContent
            )
            .then(() => {

                const original =
                    btn.textContent;

                btn.textContent =
                    "Copied!";

                setTimeout(
                    () =>
                        (btn.textContent =
                            original),
                    2000
                );

                this.showToast(
                    "Code copied",
                    "success"
                );

            })
            .catch((err) => {

                console.error(
                    "Clipboard error:",
                    err
                );

                this.showToast(
                    "Failed to copy code",
                    "error"
                );
            });
    },


    // ======================================
    // SCROLL
    // ======================================

    scrollToBottom() {

        setTimeout(() => {

            if (
                this.elements
                    .chatContainer
            ) {

                this.elements
                    .chatContainer
                    .scrollTop =
                    this.elements
                        .chatContainer
                        .scrollHeight;
            }

        }, 50);
    },


    // ======================================
    // CONNECTION STATUS
    // ======================================

    updateConnectionStatus(
        isOnline
    ) {

        const el =
            document.getElementById(
                "connection-status"
            );

        if (!el) {
            return;
        }


        if (isOnline) {

            el.innerHTML =
                '<span class="dot"></span> Connected';

            el.style.color =
                "var(--success)";

        } else {

            el.innerHTML =
                '<span class="dot" style="background-color: var(--error)"></span> Disconnected';

            el.style.color =
                "var(--error)";
        }
    },


    // ======================================
    // THREAD ID
    // ======================================

    updateThreadIdDisplay() {

        if (
            this.elements
                .currentThreadIdDisplay
        ) {

            this.elements
                .currentThreadIdDisplay
                .textContent =
                State.threadId;
        }
    },


    // ======================================
    // TOAST
    // ======================================

    showToast(
        message,
        type = "info"
    ) {

        if (
            !this.elements
                .toastContainer
        ) {
            return;
        }


        const toast =
            document.createElement(
                "div"
            );

        toast.className =
            `toast ${type}`;


        const icons = {

            success: "✓",

            error: "✕",

            info: "ℹ",

            warning: "⚠"
        };


        toast.innerHTML = `

            <span>
                ${icons[type] || "ℹ"}
            </span>

            ${this.escapeHtml(
                message
            )}

        `;


        this.elements
            .toastContainer
            .appendChild(
                toast
            );


        setTimeout(() => {

            toast.style.opacity =
                "0";

            toast.style.transform =
                "translateX(100%)";


            setTimeout(
                () =>
                    toast.remove(),
                300
            );

        }, 3000);
    }
};


// ==========================================
// 4. INITIALIZE APP
// ==========================================

document.addEventListener(
    "DOMContentLoaded",
    () => {

        UI.init();

    }
);