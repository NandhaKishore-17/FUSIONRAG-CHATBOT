document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const queryInput = document.getElementById('query-input');
    const chatBox = document.getElementById('chat-box');
    const uploadForm = document.getElementById('upload-form');
    const pdfUpload = document.getElementById('pdf-upload');
    const uploadStatus = document.getElementById('upload-status');
    const documentList = document.getElementById('document-list');
    const marksBtns = document.querySelectorAll('.marks-btn');

    let selectedMarks = '2'; // Default

    // Load initial files
    fetchFiles();

    // Marks selector logic
    marksBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            marksBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedMarks = btn.dataset.marks;
        });
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = queryInput.value.trim();
        if (!query) return;

        // Add user message with marks badge
        appendMessage(query, 'user', [], selectedMarks);
        queryInput.value = '';

        // Add typing indicator
        const typingId = showTypingIndicator();

        try {
            const response = await fetch('/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, marks: selectedMarks })
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
                    appendMessage(data.answer, 'bot', data.sources);
                }
                return;
            }

            const msgDiv = document.createElement('div');
            msgDiv.classList.add('message', 'bot-message');
            msgDiv.innerHTML = `<div class="message-content"><p></p></div>`;
            chatBox.appendChild(msgDiv);
            
            const p = msgDiv.querySelector('p');
            let fullText = '';
            let sourcesHTML = '';

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
                                if (data.sources && data.sources.length > 0) {
                                    sourcesHTML = `
                                        <div class="sources">
                                            <strong>Sources:</strong>
                                            <ul>
                                                ${data.sources.map(s => `<li>- ${s}</li>`).join('')}
                                            </ul>
                                        </div>
                                    `;
                                }
                            } else if (data.type === 'token') {
                                fullText += data.content;
                                p.innerHTML = fullText.replace(/\n/g, '<br>');
                                chatBox.scrollTop = chatBox.scrollHeight;
                            } else if (data.error) {
                                p.innerHTML = `Error: ${data.error}`;
                            }
                        } catch (e) {
                            console.error("Error parsing SSE:", e, dataStr);
                        }
                    }
                }
            }
            if (sourcesHTML) {
                msgDiv.querySelector('.message-content').innerHTML += sourcesHTML;
                chatBox.scrollTop = chatBox.scrollHeight;
            }

        } catch (error) {
            removeElement(typingId);
            appendMessage(`Connection error: ${error.message}`, 'bot');
        }
    });

    pdfUpload.addEventListener('change', async (e) => {
        if (!e.target.files.length) return;
        
        const file = e.target.files[0];
        const formData = new FormData();
        formData.append('file', file);

        uploadStatus.textContent = 'Uploading and processing PDF (this may take a minute)...';
        
        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (data.error) {
                uploadStatus.textContent = `Error: ${data.error}`;
                uploadStatus.style.color = '#ef4444';
            } else {
                uploadStatus.textContent = 'Successfully added to Vector Database!';
                uploadStatus.style.color = '#10b981';
                fetchFiles(); // Refresh list
            }
        } catch (error) {
            uploadStatus.textContent = `Upload failed: ${error.message}`;
            uploadStatus.style.color = '#ef4444';
        }
        
        setTimeout(() => { uploadStatus.textContent = ''; uploadStatus.style.color = 'var(--text-muted)'; }, 5000);
    });

    async function fetchFiles() {
        try {
            const response = await fetch('/files');
            const data = await response.json();
            documentList.innerHTML = '';
            
            if (data.files.length === 0) {
                documentList.innerHTML = '<li>No PDFs indexed yet.</li>';
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
                        // First click: show confirm state
                        confirmPending = true;
                        deleteBtn.innerHTML = '<i class="fa-solid fa-check"></i>';
                        deleteBtn.title = 'Click again to confirm';
                        deleteBtn.style.color = '#ef4444';
                        deleteBtn.style.background = 'rgba(239, 68, 68, 0.15)';
                        
                        // Reset after 3 seconds if not confirmed
                        setTimeout(() => {
                            if (confirmPending) {
                                confirmPending = false;
                                deleteBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
                                deleteBtn.title = `Delete ${file}`;
                                deleteBtn.style.color = '';
                                deleteBtn.style.background = '';
                            }
                        }, 3000);
                        return;
                    }
                    
                    // Second click: actually delete
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
                            fetchFiles(); // Refresh
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

    function appendMessage(text, sender, sources = [], marks = null) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', `${sender}-message`);
        
        let badgeHTML = '';
        if (sender === 'user' && marks) {
            badgeHTML = `<span class="marks-badge">${marks} Marks</span>`;
        }
        
        let contentHTML = `<p>${badgeHTML}${text.replace(/\n/g, '<br>')}</p>`;
        
        if (sources && sources.length > 0) {
            contentHTML += `
                <div class="sources">
                    <strong>Sources:</strong>
                    <ul>
                        ${sources.map(s => `<li>- ${s}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        
        msgDiv.innerHTML = `
            <div class="message-content">
                ${contentHTML}
            </div>
        `;
        
        chatBox.appendChild(msgDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function showTypingIndicator() {
        const id = 'typing-' + Date.now();
        const msgDiv = document.createElement('div');
        msgDiv.id = id;
        msgDiv.classList.add('message', 'bot-message');
        msgDiv.innerHTML = `
            <div class="message-content">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        chatBox.appendChild(msgDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
        return id;
    }

    function removeElement(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }
});
