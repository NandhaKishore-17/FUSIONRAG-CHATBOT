document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const queryInput = document.getElementById('query-input');
    const chatBox = document.getElementById('chat-box');
    const pdfUpload = document.getElementById('pdf-upload');
    const uploadStatus = document.getElementById('upload-status');
    const documentList = document.getElementById('document-list');
    const filesCount = document.getElementById('files-count');
    const marksToggle = document.getElementById('marks-toggle');
    const marksSelector = document.getElementById('marks-selector');
    const marksBtns = document.querySelectorAll('.marks-btn');
    const welcomeScreen = document.getElementById('welcome-screen');
    const sendBtn = document.getElementById('send-btn');
    const sidebar = document.getElementById('sidebar');
    const sidebarOpen = document.getElementById('sidebar-open');
    const sidebarClose = document.getElementById('sidebar-close');

    let selectedMarks = null; // null = no marks selected (normal mode)
    let marksEnabled = false;

    // Lightweight markdown renderer
    function renderMarkdown(text) {
        let html = text;
        // Escape HTML
        html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        // Headings: ### then ## (order matters)
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        // Bold
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        // Italic
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        // Unordered lists: lines starting with - 
        html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
        // Numbered lists: lines starting with 1. 2. etc
        html = html.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>');
        // Wrap consecutive <li> in <ul>
        html = html.replace(/(<li>.*?<\/li>\n?)+/gs, (match) => {
            return '<ul>' + match + '</ul>';
        });
        // Paragraphs: double newlines
        html = html.replace(/\n\n+/g, '</p><p>');
        // Single newlines (that aren't inside tags)
        html = html.replace(/\n/g, '<br>');
        // Wrap in paragraph
        html = '<p>' + html + '</p>';
        // Clean up empty paragraphs
        html = html.replace(/<p><\/p>/g, '');
        html = html.replace(/<p>\s*<(h[23])/g, '<$1');
        html = html.replace(/<\/(h[23])>\s*<\/p>/g, '</$1>');
        html = html.replace(/<p>\s*<ul>/g, '<ul>');
        html = html.replace(/<\/ul>\s*<\/p>/g, '</ul>');
        return html;
    }

    // Load initial files
    fetchFiles();

    // Sidebar toggle
    sidebarClose.addEventListener('click', () => {
        sidebar.classList.add('collapsed');
    });
    sidebarOpen.addEventListener('click', () => {
        sidebar.classList.remove('collapsed');
    });

    // Auto-resize textarea
    queryInput.addEventListener('input', () => {
        queryInput.style.height = 'auto';
        queryInput.style.height = Math.min(queryInput.scrollHeight, 160) + 'px';
    });

    // Marks toggle
    marksToggle.addEventListener('click', () => {
        marksEnabled = !marksEnabled;
        marksToggle.classList.toggle('active', marksEnabled);
        marksSelector.classList.toggle('hidden', !marksEnabled);
        if (!marksEnabled) {
            selectedMarks = null;
            marksBtns.forEach(b => b.classList.remove('active'));
        }
    });

    // Marks selector
    marksBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            marksBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedMarks = btn.dataset.marks;
        });
    });

    // Welcome chips
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            queryInput.value = chip.dataset.query;
            queryInput.dispatchEvent(new Event('input'));
            chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
        });
    });

    // Submit handler
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = queryInput.value.trim();
        if (!query) return;

        // Hide welcome screen
        if (welcomeScreen) {
            welcomeScreen.style.display = 'none';
        }

        // Show user message
        appendMessage(query, 'user', [], selectedMarks);
        queryInput.value = '';
        queryInput.style.height = 'auto';

        // Show typing
        const typingId = showTypingIndicator();

        try {
            const body = { query };
            if (marksEnabled && selectedMarks) {
                body.marks = selectedMarks;
            }

            const response = await fetch('/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            removeElement(typingId);

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                appendMessage(`Error: ${errData.error || 'Server error'}`, 'bot');
                return;
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();
                if (data.error) {
                    appendMessage(`Error: ${data.error}`, 'bot');
                } else {
                    appendMessage(data.answer, 'bot', data.sources || []);
                }
                return;
            }

            // SSE streaming
            const msgRow = createBotMessageRow();
            chatBox.appendChild(msgRow);
            const p = msgRow.querySelector('.message-body p');
            let fullText = '';
            let sourcesData = [];

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (let line of lines) {
                    line = line.trim();
                    if (line.startsWith('data: ')) {
                        const dataStr = line.substring(6).trim();
                        if (dataStr === '[DONE]') continue;

                        try {
                            const data = JSON.parse(dataStr);
                            if (data.type === 'sources') {
                                sourcesData = data.sources || [];
                            } else if (data.type === 'token') {
                                fullText += data.content;
                                // Use the container div instead of p for markdown
                                const bodyEl = msgRow.querySelector('.message-body');
                                bodyEl.innerHTML = renderMarkdown(fullText);
                                chatBox.scrollTop = chatBox.scrollHeight;
                            } else if (data.error) {
                                p.innerHTML = `Error: ${data.error}`;
                            }
                        } catch (e) {
                            console.error("SSE parse error:", e, dataStr);
                        }
                    }
                }
            }

            // Append sources after stream complete
            if (sourcesData.length > 0) {
                const body = msgRow.querySelector('.message-body');
                const sourcesDiv = document.createElement('div');
                sourcesDiv.className = 'sources';
                sourcesDiv.innerHTML = `
                    <strong><i class="fa-solid fa-book-open"></i> Sources</strong>
                    <ul>
                        ${sourcesData.map(s => `<li>${s}</li>`).join('')}
                    </ul>
                `;
                body.appendChild(sourcesDiv);
                chatBox.scrollTop = chatBox.scrollHeight;
            }

        } catch (error) {
            removeElement(typingId);
            appendMessage(`Connection error: ${error.message}`, 'bot');
        }
    });

    // Upload
    pdfUpload.addEventListener('change', async (e) => {
        if (!e.target.files.length) return;

        const file = e.target.files[0];
        const formData = new FormData();
        formData.append('file', file);

        uploadStatus.textContent = 'Processing PDF...';
        uploadStatus.style.color = 'var(--text-muted)';

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.error) {
                uploadStatus.textContent = `Error: ${data.error}`;
                uploadStatus.style.color = 'var(--danger)';
            } else {
                uploadStatus.textContent = '✓ Added to vector database';
                uploadStatus.style.color = 'var(--success)';
                fetchFiles();
            }
        } catch (error) {
            uploadStatus.textContent = `Upload failed: ${error.message}`;
            uploadStatus.style.color = 'var(--danger)';
        }

        setTimeout(() => {
            uploadStatus.textContent = '';
            uploadStatus.style.color = 'var(--text-muted)';
        }, 4000);
    });

    // Fetch files
    async function fetchFiles() {
        try {
            const response = await fetch('/files');
            const data = await response.json();
            documentList.innerHTML = '';

            filesCount.textContent = data.files.length;

            if (data.files.length === 0) {
                documentList.innerHTML = '<li style="color:var(--text-muted);font-size:0.82rem;">No documents yet</li>';
                return;
            }

            data.files.forEach(file => {
                const li = document.createElement('li');
                li.innerHTML = `
                    <i class="fa-solid fa-file-pdf"></i>
                    <span class="file-name">${file}</span>
                    <button class="delete-btn" title="Delete ${file}"><i class="fa-solid fa-trash"></i></button>
                `;

                const deleteBtn = li.querySelector('.delete-btn');
                let confirmPending = false;

                deleteBtn.addEventListener('click', async () => {
                    if (!confirmPending) {
                        confirmPending = true;
                        deleteBtn.innerHTML = '<i class="fa-solid fa-check"></i>';
                        deleteBtn.title = 'Click again to confirm';
                        deleteBtn.style.color = 'var(--danger)';
                        deleteBtn.style.background = 'var(--danger-bg)';
                        deleteBtn.style.opacity = '1';

                        setTimeout(() => {
                            if (confirmPending) {
                                confirmPending = false;
                                deleteBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
                                deleteBtn.title = `Delete ${file}`;
                                deleteBtn.style.color = '';
                                deleteBtn.style.background = '';
                                deleteBtn.style.opacity = '';
                            }
                        }, 3000);
                        return;
                    }

                    try {
                        const res = await fetch('/delete', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ filename: file })
                        });
                        const result = await res.json();
                        if (result.error) {
                            alert('Error: ' + result.error);
                        } else {
                            fetchFiles();
                        }
                    } catch (err) {
                        alert('Delete failed: ' + err.message);
                    }
                });

                documentList.appendChild(li);
            });
        } catch (error) {
            console.error('Failed to fetch files', error);
        }
    }

    // Append a message
    function appendMessage(text, sender, sources = [], marks = null) {
        const row = document.createElement('div');
        row.classList.add('message-row', `${sender}-row`);

        const isUser = sender === 'user';
        const avatarIcon = isUser ? 'N' : '<i class="fa-solid fa-bolt"></i>';

        let badgeHTML = '';
        if (isUser && marks) {
            badgeHTML = `<span class="marks-badge">${marks}M</span>`;
        }

        let sourcesHTML = '';
        if (sources && sources.length > 0) {
            sourcesHTML = `
                <div class="sources">
                    <strong><i class="fa-solid fa-book-open"></i> Sources</strong>
                    <ul>
                        ${sources.map(s => `<li>${s}</li>`).join('')}
                    </ul>
                </div>
            `;
        }

        const renderedText = isUser ? text.replace(/\n/g, '<br>') : renderMarkdown(text);

        row.innerHTML = `
            <div class="message-inner">
                <div class="message-avatar">${avatarIcon}</div>
                <div class="message-body">
                    ${isUser ? `<p>${badgeHTML}${renderedText}</p>` : renderedText}
                    ${sourcesHTML}
                </div>
            </div>
        `;

        chatBox.appendChild(row);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function createBotMessageRow() {
        const row = document.createElement('div');
        row.classList.add('message-row', 'bot-row');
        row.innerHTML = `
            <div class="message-inner">
                <div class="message-avatar"><i class="fa-solid fa-bolt"></i></div>
                <div class="message-body">
                    <p></p>
                </div>
            </div>
        `;
        return row;
    }

    function showTypingIndicator() {
        const id = 'typing-' + Date.now();
        const row = document.createElement('div');
        row.id = id;
        row.classList.add('message-row', 'bot-row');
        row.innerHTML = `
            <div class="message-inner">
                <div class="message-avatar"><i class="fa-solid fa-bolt"></i></div>
                <div class="message-body">
                    <div class="typing-indicator">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                </div>
            </div>
        `;
        chatBox.appendChild(row);
        chatBox.scrollTop = chatBox.scrollHeight;
        return id;
    }

    function removeElement(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    // Enter to send, Shift+Enter for newline
    queryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
        }
    });
});
