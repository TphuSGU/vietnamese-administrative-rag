const API_BASE_URL = window.APP_CONFIG?.API_BASE_URL || '/api/v1';
const TOKEN_KEY = 'admin_ai_token';
const EMAIL_KEY = 'admin_ai_email';
const ROLE_KEY = 'admin_ai_role';

const WELCOME_HTML = `
    <div class="message bot-message">
        <div class="message-content">
            <p>Xin chào! Tôi có thể giúp bạn tra cứu thông tin về:</p>
            <ul>
                <li>Tổ chức chính quyền địa phương 2 cấp</li>
                <li>Cơ quan chuyên môn thuộc UBND</li>
                <li>Văn bản pháp luật và quy định liên quan</li>
            </ul>
            <p>Bạn muốn hỏi gì?</p>
        </div>
    </div>
`;

const state = {
    token: localStorage.getItem(TOKEN_KEY) || '',
    email: localStorage.getItem(EMAIL_KEY) || '',
    role: localStorage.getItem(ROLE_KEY) || '',
    currentConversationId: null,
    conversations: [],
    isLoading: false,
    authMode: 'login',
};

const els = {
    chat: document.getElementById('chat-container'),
    input: document.getElementById('user-input'),
    sendBtn: document.getElementById('send-btn'),
    sendIcon: document.getElementById('send-icon'),
    loadingIcon: document.getElementById('loading-icon'),
    sidebar: document.getElementById('sidebar'),
    sidebarToggle: document.getElementById('sidebar-toggle'),
    newChatBtn: document.getElementById('new-chat-btn'),
    conversationList: document.getElementById('conversation-list'),
    userBox: document.getElementById('user-box'),
    userEmail: document.getElementById('user-email'),
    adminLink: document.getElementById('admin-link'),
    loginBtn: document.getElementById('login-btn'),
    logoutBtn: document.getElementById('logout-btn'),
    authModal: document.getElementById('auth-modal'),
    authClose: document.getElementById('auth-close'),
    authTitle: document.getElementById('auth-title'),
    authSubtitle: document.querySelector('.modal-subtitle'),
    authForm: document.getElementById('auth-form'),
    authEmail: document.getElementById('auth-email'),
    authPassword: document.getElementById('auth-password'),
    authFullname: document.getElementById('auth-fullname'),
    fullnameField: document.getElementById('fullname-field'),
    authError: document.getElementById('auth-error'),
    authSubmit: document.getElementById('auth-submit'),
    tabLogin: document.getElementById('tab-login'),
    tabRegister: document.getElementById('tab-register'),
    feedbackBtn: document.getElementById('feedback-btn'),
    feedbackModal: document.getElementById('feedback-modal'),
    feedbackClose: document.getElementById('feedback-close'),
    feedbackForm: document.getElementById('feedback-form'),
    feedbackName: document.getElementById('feedback-name'),
    feedbackPhone: document.getElementById('feedback-phone'),
    feedbackEmail: document.getElementById('feedback-email'),
    feedbackCategory: document.getElementById('feedback-category'),
    feedbackSubject: document.getElementById('feedback-subject'),
    feedbackContent: document.getElementById('feedback-content'),
    feedbackError: document.getElementById('feedback-error'),
    feedbackSuccess: document.getElementById('feedback-success'),
    feedbackSubmit: document.getElementById('feedback-submit'),
};

function authHeaders(extra = {}) {
    const headers = { ...extra };
    if (state.token) {
        headers.Authorization = `Bearer ${state.token}`;
    }
    return headers;
}

function parseErrorDetail(payload, fallback) {
    if (!payload) return fallback;
    if (typeof payload.detail === 'string') return payload.detail;
    if (Array.isArray(payload.detail)) {
        return payload.detail
            .map((item) => `${(item.loc || []).join('.')}: ${item.msg}`)
            .join(', ');
    }
    return payload.message || fallback;
}

async function apiRequest(path, options = {}) {
    const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers: authHeaders(options.headers || {}),
    });

    if (response.status === 204) return null;

    const text = await response.text();
    let payload = null;
    if (text) {
        try {
            payload = JSON.parse(text);
        } catch {
            payload = { detail: text };
        }
    }

    if (!response.ok) {
        const error = new Error(
            parseErrorDetail(payload, `Lỗi HTTP ${response.status}`)
        );
        error.status = response.status;
        throw error;
    }

    return payload;
}

/* ------------------------------------------------------------------------- */
/* Auth                                                                      */
/* ------------------------------------------------------------------------- */

function setAuthMode(mode) {
    state.authMode = mode;
    const isLogin = mode === 'login';
    els.authTitle.textContent = isLogin ? 'Đăng nhập' : 'Đăng ký';
    els.authSubtitle.textContent = isLogin
        ? 'Đăng nhập để lưu và xem lại lịch sử hội thoại.'
        : 'Tạo tài khoản để lưu lịch sử hội thoại.';
    els.authSubmit.textContent = isLogin ? 'Đăng nhập' : 'Tạo tài khoản';
    els.fullnameField.classList.toggle('hidden', isLogin);
    els.authPassword.autocomplete = isLogin ? 'current-password' : 'new-password';
    els.authPassword.minLength = isLogin ? 1 : 8;
    els.tabLogin.classList.toggle('active', isLogin);
    els.tabRegister.classList.toggle('active', !isLogin);
    hideAuthError();
}

function openAuthModal(mode = 'login') {
    setAuthMode(mode);
    els.authModal.classList.remove('hidden');
    els.authEmail.focus();
}

function closeAuthModal() {
    els.authModal.classList.add('hidden');
    els.authForm.reset();
    hideAuthError();
}

function showAuthError(message) {
    els.authError.textContent = message;
    els.authError.classList.remove('hidden');
}

function hideAuthError() {
    els.authError.textContent = '';
    els.authError.classList.add('hidden');
}

function setAuthUi() {
    const loggedIn = Boolean(state.token);
    els.userBox.classList.toggle('hidden', !loggedIn);
    els.loginBtn.classList.toggle('hidden', loggedIn);
    els.userEmail.textContent = state.email;
    els.adminLink.classList.toggle('hidden', state.role !== 'admin');
}

function saveSession(token, email, role) {
    state.token = token;
    state.email = email;
    state.role = role || 'user';
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(EMAIL_KEY, email);
    localStorage.setItem(ROLE_KEY, state.role);
    setAuthUi();
}

function clearSession() {
    state.token = '';
    state.email = '';
    state.role = '';
    state.currentConversationId = null;
    state.conversations = [];
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EMAIL_KEY);
    localStorage.removeItem(ROLE_KEY);
    setAuthUi();
    renderConversations();
    clearChat();
}

async function handleAuthSubmit(event) {
    event.preventDefault();
    hideAuthError();
    els.authSubmit.disabled = true;

    const email = els.authEmail.value.trim();
    const password = els.authPassword.value;
    const fullName = els.authFullname.value.trim();

    try {
        if (state.authMode === 'register') {
            await apiRequest('/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password, full_name: fullName }),
            });
        }

        const login = await apiRequest('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });

        saveSession(login.access_token, login.user.email, login.user.role);
        closeAuthModal();
        await loadConversations();
    } catch (error) {
        showAuthError(error.message);
    } finally {
        els.authSubmit.disabled = false;
    }
}

async function restoreSession() {
    if (!state.token) {
        setAuthUi();
        return;
    }

    try {
        const me = await apiRequest('/auth/me');
        state.email = me.email;
        state.role = me.role || 'user';
        localStorage.setItem(EMAIL_KEY, me.email);
        localStorage.setItem(ROLE_KEY, state.role);
        setAuthUi();
        await loadConversations();
    } catch {
        clearSession();
    }
}

/* ------------------------------------------------------------------------- */
/* Citizen feedback                                                          */
/* ------------------------------------------------------------------------- */

function openFeedbackModal() {
    els.feedbackError.classList.add('hidden');
    els.feedbackSuccess.classList.add('hidden');
    els.feedbackModal.classList.remove('hidden');
    els.feedbackSubject.focus();
}

function closeFeedbackModal() {
    els.feedbackModal.classList.add('hidden');
}

function showFeedbackError(message) {
    els.feedbackSuccess.classList.add('hidden');
    els.feedbackError.textContent = message;
    els.feedbackError.classList.remove('hidden');
}

function showFeedbackSuccess(message) {
    els.feedbackError.classList.add('hidden');
    els.feedbackSuccess.textContent = message;
    els.feedbackSuccess.classList.remove('hidden');
}

async function handleFeedbackSubmit(event) {
    event.preventDefault();
    const subject = els.feedbackSubject.value.trim();
    const content = els.feedbackContent.value.trim();

    if (subject.length < 3) {
        showFeedbackError('Tiêu đề cần ít nhất 3 ký tự.');
        return;
    }
    if (content.length < 10) {
        showFeedbackError('Nội dung cần ít nhất 10 ký tự.');
        return;
    }

    els.feedbackSubmit.disabled = true;
    els.feedbackSubmit.textContent = 'Đang gửi...';
    els.feedbackError.classList.add('hidden');
    els.feedbackSuccess.classList.add('hidden');

    try {
        await apiRequest('/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                full_name: els.feedbackName.value.trim(),
                phone: els.feedbackPhone.value.trim(),
                email: els.feedbackEmail.value.trim(),
                category: els.feedbackCategory.value,
                subject,
                content,
            }),
        });
        els.feedbackForm.reset();
        showFeedbackSuccess('Đã gửi ý kiến. Cán bộ phường sẽ tiếp nhận và xử lý.');
        window.setTimeout(closeFeedbackModal, 1600);
    } catch (error) {
        showFeedbackError(error.message);
    } finally {
        els.feedbackSubmit.disabled = false;
        els.feedbackSubmit.textContent = 'Gửi ý kiến';
    }
}

/* ------------------------------------------------------------------------- */
/* Conversations                                                             */
/* ------------------------------------------------------------------------- */

async function loadConversations() {
    if (!state.token) {
        renderConversations();
        return;
    }

    try {
        state.conversations = await apiRequest('/conversations');
        renderConversations();
    } catch (error) {
        if (error.status === 401) clearSession();
        console.error('Không tải được lịch sử:', error);
    }
}

function renderConversations() {
    els.conversationList.replaceChildren();

    if (!state.token) {
        const empty = document.createElement('p');
        empty.className = 'sidebar-empty';
        empty.textContent = 'Đăng nhập để xem lịch sử hội thoại.';
        els.conversationList.appendChild(empty);
        return;
    }

    if (!state.conversations.length) {
        const empty = document.createElement('p');
        empty.className = 'sidebar-empty';
        empty.textContent = 'Chưa có cuộc hội thoại nào.';
        els.conversationList.appendChild(empty);
        return;
    }

    for (const conversation of state.conversations) {
        const row = document.createElement('div');
        row.className = 'conversation-row';

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'conversation-item';
        if (conversation.id === state.currentConversationId) {
            button.classList.add('active');
        }

        const title = document.createElement('span');
        title.className = 'conversation-title';
        title.textContent = conversation.title || 'Cuộc hội thoại';

        const meta = document.createElement('span');
        meta.className = 'conversation-meta';
        meta.textContent = `${conversation.message_count} tin nhắn`;

        button.append(title, meta);
        button.addEventListener('click', () => loadConversation(conversation.id));

        const actions = document.createElement('div');
        actions.className = 'conversation-actions';

        const renameBtn = document.createElement('button');
        renameBtn.type = 'button';
        renameBtn.className = 'conversation-action';
        renameBtn.textContent = 'Sửa';
        renameBtn.title = 'Đổi tên hội thoại';
        renameBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            renameConversation(conversation);
        });

        const deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'conversation-action danger';
        deleteBtn.textContent = 'Xóa';
        deleteBtn.title = 'Xóa hội thoại';
        deleteBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            deleteConversation(conversation);
        });

        actions.append(renameBtn, deleteBtn);
        row.append(button, actions);
        els.conversationList.appendChild(row);
    }
}

async function renameConversation(conversation) {
    const nextTitle = window.prompt(
        'Tên mới cho cuộc hội thoại:',
        conversation.title || 'Cuộc hội thoại'
    );
    if (nextTitle === null) return;

    const title = nextTitle.trim();
    if (!title) {
        addMessage('Tên hội thoại không được để trống.', 'bot', true);
        return;
    }
    if (title.length > 255) {
        addMessage('Tên hội thoại tối đa 255 ký tự.', 'bot', true);
        return;
    }

    try {
        const updated = await apiRequest(`/conversations/${conversation.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title }),
        });
        const target = state.conversations.find((item) => item.id === conversation.id);
        if (target) target.title = updated.title;
        renderConversations();
    } catch (error) {
        addMessage(`Không đổi được tên hội thoại: ${error.message}`, 'bot', true);
    }
}

async function deleteConversation(conversation) {
    const confirmed = window.confirm(
        `Xóa hội thoại "${conversation.title || 'Cuộc hội thoại'}"? Hành động này không thể hoàn tác.`
    );
    if (!confirmed) return;

    try {
        await apiRequest(`/conversations/${conversation.id}`, { method: 'DELETE' });
        if (state.currentConversationId === conversation.id) {
            newChat();
        }
        state.conversations = state.conversations.filter(
            (item) => item.id !== conversation.id
        );
        renderConversations();
    } catch (error) {
        addMessage(`Không xóa được hội thoại: ${error.message}`, 'bot', true);
    }
}

async function loadConversation(conversationId) {
    try {
        const detail = await apiRequest(`/conversations/${conversationId}`);
        state.currentConversationId = conversationId;
        renderConversations();
        clearChat();

        if (!detail.messages.length) {
            return;
        }

        for (const message of detail.messages) {
            if (message.role === 'user') {
                addMessage(message.content, 'user');
            } else {
                addBotMessage({
                    answer: message.content,
                    model: null,
                    processing_time: null,
                    created_at: message.created_at,
                });
            }
        }

        closeSidebarOnMobile();
    } catch (error) {
        addMessage(`❌ Không tải được hội thoại: ${error.message}`, 'bot', true);
    }
}

function newChat() {
    state.currentConversationId = null;
    renderConversations();
    clearChat();
    closeSidebarOnMobile();
    els.input.focus();
}

/* ------------------------------------------------------------------------- */
/* Chat                                                                      */
/* ------------------------------------------------------------------------- */

function clearChat() {
    els.chat.innerHTML = WELCOME_HTML;
}

function scrollToBottom() {
    els.chat.scrollTop = els.chat.scrollHeight;
}

function addMessage(text, sender, isError = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message${isError ? ' error-message' : ''}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    const paragraph = document.createElement('p');
    paragraph.textContent = text;
    contentDiv.appendChild(paragraph);

    messageDiv.appendChild(contentDiv);
    els.chat.appendChild(messageDiv);
    scrollToBottom();
}

/* ------------------------------------------------------------------------- */
/* Source card (Phase 9): 1 nguồn đầu tiên — citation + badge, không URL.    */
/* ------------------------------------------------------------------------- */

function formatIsoDate(iso) {
    const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
    return parts ? `${parts[3]}/${parts[2]}/${parts[1]}` : (iso || '');
}

function sourceBadgeLabel(src) {
    if (src.doc_type === 'Thủ tục hành chính') return 'TTHC';
    if (src.doc_type === 'Lịch làm việc') return 'Lịch làm việc';
    if (src.doc_scope === 'local') return 'Văn bản phường';
    if (src.doc_scope === 'hcmc') return 'Văn bản TP.HCM';
    if (src.doc_scope === 'central') return 'Trung ương';
    return 'Nguồn';
}

function buildSourceCard(src) {
    const card = document.createElement('div');
    card.className = 'source-card';

    const badge = document.createElement('span');
    badge.className = 'source-badge';
    badge.textContent = sourceBadgeLabel(src);
    card.appendChild(badge);

    const citation = document.createElement('p');
    citation.className = 'source-citation';
    citation.textContent = src.citation || src.doc_number || 'Nguồn tham khảo';
    card.appendChild(citation);

    const meta = [];
    if (src.issued_date) meta.push(`ban hành ${formatIsoDate(src.issued_date)}`);
    if (src.issuer) meta.push(src.issuer);
    if (meta.length) {
        const metaDiv = document.createElement('div');
        metaDiv.className = 'source-meta';
        metaDiv.textContent = meta.join(' • ');
        card.appendChild(metaDiv);
    }
    return card;
}

function addBotMessage(data) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    const paragraph = document.createElement('p');
    paragraph.textContent = data.answer || 'Không có câu trả lời.';
    contentDiv.appendChild(paragraph);

    const source = Array.isArray(data.source_chunks) ? data.source_chunks[0] : null;
    if (source && (source.citation || source.doc_number)) {
        contentDiv.appendChild(buildSourceCard(source));
    }

    if (data.model || data.processing_time != null || data.created_at) {
        const metaDiv = document.createElement('div');
        metaDiv.className = 'metadata';
        const parts = [];
        if (data.processing_time != null) {
            parts.push(`⏱️ ${Number(data.processing_time).toFixed(2)}s`);
        }
        if (data.model) parts.push(`🤖 ${data.model}`);
        if (data.created_at) {
            parts.push(new Date(data.created_at).toLocaleString('vi-VN'));
        }
        metaDiv.textContent = parts.join(' • ');
        contentDiv.appendChild(metaDiv);
    }

    messageDiv.appendChild(contentDiv);
    els.chat.appendChild(messageDiv);
    scrollToBottom();
}

function setLoading(loading) {
    state.isLoading = loading;
    els.sendBtn.disabled = loading;
    els.input.disabled = loading;
    els.sendIcon.classList.toggle('hidden', loading);
    els.loadingIcon.classList.toggle('hidden', !loading);
}

async function sendMessage() {
    const query = els.input.value.trim();
    if (!query || state.isLoading) return;

    if (query.length < 10) {
        addMessage('❌ Câu hỏi quá ngắn. Vui lòng nhập ít nhất 10 ký tự.', 'bot', true);
        return;
    }

    addMessage(query, 'user');
    els.input.value = '';
    setLoading(true);

    try {
        const body = { query, k: 5 };
        if (state.token && state.currentConversationId) {
            body.conversation_id = state.currentConversationId;
        }

        const data = await apiRequest('/chat/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        addBotMessage(data);

        if (state.token && data.conversation_id) {
            const isNew = state.currentConversationId !== data.conversation_id;
            state.currentConversationId = data.conversation_id;
            if (isNew) {
                await loadConversations();
            } else {
                renderConversations();
            }
        }
    } catch (error) {
        if (error.status === 401 && state.token) {
            clearSession();
            addMessage('❌ Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.', 'bot', true);
        } else {
            addMessage(`❌ Xin lỗi, đã có lỗi xảy ra: ${error.message}`, 'bot', true);
        }
    } finally {
        setLoading(false);
        els.input.focus();
    }
}

/* ------------------------------------------------------------------------- */
/* Events                                                                    */
/* ------------------------------------------------------------------------- */

function closeSidebarOnMobile() {
    if (window.matchMedia('(max-width: 800px)').matches) {
        els.sidebar.classList.remove('open');
    }
}

els.sendBtn.addEventListener('click', sendMessage);
els.input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

els.loginBtn.addEventListener('click', () => openAuthModal('login'));
els.authClose.addEventListener('click', closeAuthModal);
els.authModal.addEventListener('click', (event) => {
    if (event.target === els.authModal) closeAuthModal();
});
els.tabLogin.addEventListener('click', () => setAuthMode('login'));
els.tabRegister.addEventListener('click', () => setAuthMode('register'));
els.authForm.addEventListener('submit', handleAuthSubmit);
els.logoutBtn.addEventListener('click', clearSession);
els.newChatBtn.addEventListener('click', newChat);
els.sidebarToggle.addEventListener('click', () => els.sidebar.classList.toggle('open'));
els.feedbackBtn.addEventListener('click', openFeedbackModal);
els.feedbackClose.addEventListener('click', closeFeedbackModal);
els.feedbackModal.addEventListener('click', (event) => {
    if (event.target === els.feedbackModal) closeFeedbackModal();
});
els.feedbackForm.addEventListener('submit', handleFeedbackSubmit);

restoreSession();
