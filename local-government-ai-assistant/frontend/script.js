const API_BASE_URL = 'http://localhost:8000/api/v1';

let isLoading = false;

async function sendMessage() {
    const input = document.getElementById('user-input');
    const query = input.value.trim();
    
    // Validate empty
    if (!query || isLoading) return;
    
    // Validate length (10-500 chars to match backend)
    if (query.length < 10) {
        addMessage(
            '❌ Câu hỏi quá ngắn. Vui lòng nhập ít nhất 10 ký tự.',
            'bot',
            true
        );
        return;
    }
    
    if (query.length > 500) {
        addMessage(
            '❌ Câu hỏi quá dài. Vui lòng nhập tối đa 500 ký tự.',
            'bot',
            true
        );
        return;
    }
    
    // Add user message to chat
    addMessage(query, 'user');
    
    // Clear input
    input.value = '';
    
    // Set loading state
    setLoading(true);
    
    try {
        // Call API
        const response = await fetch(`${API_BASE_URL}/chat/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query,
                k: 5
            })
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('API Error Response:', errorText);
            
            try {
                const error = JSON.parse(errorText);
                console.error('Parsed error:', error);
                
                // Handle Pydantic validation errors (422)
                if (response.status === 422 && error.detail) {
                    if (Array.isArray(error.detail)) {
                        // Pydantic validation error format
                        const messages = error.detail.map(err => 
                            `${err.loc.join('.')}: ${err.msg}`
                        ).join(', ');
                        throw new Error(`Lỗi validation: ${messages}`);
                    }
                    throw new Error(error.detail);
                }
                
                throw new Error(error.detail || error.message || 'Lỗi không xác định');
            } catch (parseError) {
                throw new Error(`Lỗi kết nối: ${errorText}`);
            }
        }
        
        const data = await response.json();
        
        // Add bot response
        addBotMessage(data);
        
    } catch (error) {
        console.error('Error:', error);
        addMessage(
            `❌ Xin lỗi, đã có lỗi xảy ra: ${error.message}. Vui lòng thử lại sau.`,
            'bot',
            true
        );
    } finally {
        setLoading(false);
    }
}

function addMessage(text, sender, isError = false) {
    const chatContainer = document.getElementById('chat-container');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message ${isError ? 'error-message' : ''}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = `<p>${escapeHtml(text)}</p>`;
    
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function addBotMessage(data) {
    const chatContainer = document.getElementById('chat-container');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Answer
    contentDiv.innerHTML = `<p>${escapeHtml(data.answer)}</p>`;
    
    // Sources (if any)
    if (data.source_chunks && data.source_chunks.length > 0) {
        const sourcesDiv = document.createElement('div');
        sourcesDiv.className = 'sources';
        sourcesDiv.innerHTML = `
            <strong>📚 Nguồn tham khảo:</strong><br>
            ${data.source_chunks.map((chunk, i) => 
                `${i+1}. ${escapeHtml(chunk.text.substring(0, 100))}...`
            ).join('<br>')}
        `;
        contentDiv.appendChild(sourcesDiv);
    }
    
    // Metadata
    const metaDiv = document.createElement('div');
    metaDiv.className = 'metadata';
    metaDiv.textContent = `⏱️ ${data.processing_time.toFixed(2)}s • 🤖 ${data.model}`;
    contentDiv.appendChild(metaDiv);
    
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function setLoading(loading) {
    isLoading = loading;
    const sendBtn = document.getElementById('send-btn');
    const sendIcon = document.getElementById('send-icon');
    const loadingIcon = document.getElementById('loading-icon');
    const input = document.getElementById('user-input');
    
    sendBtn.disabled = loading;
    input.disabled = loading;
    
    if (loading) {
        sendIcon.style.display = 'none';
        loadingIcon.style.display = 'inline';
    } else {
        sendIcon.style.display = 'inline';
        loadingIcon.style.display = 'none';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Allow Enter to send (Shift+Enter for new line)
document.getElementById('user-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
