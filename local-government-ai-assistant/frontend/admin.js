const API_BASE_URL = window.APP_CONFIG?.API_BASE_URL || '/api/v1';
const TOKEN_KEY = 'admin_ai_token';
const EMAIL_KEY = 'admin_ai_email';
const ROLE_KEY = 'admin_ai_role';

const state = {
    token: localStorage.getItem(TOKEN_KEY) || '',
    email: localStorage.getItem(EMAIL_KEY) || '',
    role: localStorage.getItem(ROLE_KEY) || '',
    userId: '',
    view: 'dashboard',
    documents: [],
    users: [],
    usersPage: 1,
    usersPageSize: 10,
    usersRole: 'all',
    usersSearch: '',
    usersTotal: 0,
    usersTotalPages: 1,
    usersRoleCounts: { all: 0, admin: 0, user: 0 },
    usersSearchTimer: null,
    feedback: [],
    feedbackStatus: 'all',
    feedbackPage: 1,
    feedbackPageSize: 10,
    feedbackSearch: '',
    feedbackSearchTimer: null,
    feedbackTotal: 0,
    feedbackTotalPages: 1,
    feedbackStatusCounts: { all: 0, new: 0, received: 0, processing: 0, resolved: 0, closed: 0 },
    activeFeedback: null,
    jobs: [],
    uploads: new Map(),
    toastTimer: null,
};

const els = {
    loading: document.getElementById('admin-loading'),
    denied: document.getElementById('admin-denied'),
    deniedTitle: document.getElementById('denied-title'),
    deniedMessage: document.getElementById('denied-message'),
    shell: document.getElementById('admin-shell'),
    sidebar: document.getElementById('admin-sidebar'),
    menu: document.getElementById('admin-menu'),
    email: document.getElementById('admin-email'),
    role: document.getElementById('admin-role'),
    logout: document.getElementById('admin-logout'),
    pageTitle: document.getElementById('page-title'),
    pageSubtitle: document.getElementById('page-subtitle'),
    alert: document.getElementById('admin-alert'),
    refresh: document.getElementById('admin-refresh'),
    navItems: Array.from(document.querySelectorAll('.admin-nav-item')),
    views: {
        dashboard: document.getElementById('view-dashboard'),
        documents: document.getElementById('view-documents'),
        feedback: document.getElementById('view-feedback'),
        users: document.getElementById('view-users'),
    },
    statUsers: document.getElementById('stat-users'),
    statConversations: document.getElementById('stat-conversations'),
    statMessages: document.getElementById('stat-messages'),
    statChunks: document.getElementById('stat-chunks'),
    statBm25: document.getElementById('stat-bm25'),
    statBm25Detail: document.getElementById('stat-bm25-detail'),
    statCollection: document.getElementById('stat-collection'),
    statFeedback: document.getElementById('stat-feedback'),
    statFeedbackNew: document.getElementById('stat-feedback-new'),
    dropZone: document.getElementById('drop-zone'),
    fileInput: document.getElementById('file-input'),
    uploadBtn: document.getElementById('upload-btn'),
    uploadList: document.getElementById('upload-list'),
    jobsList: document.getElementById('jobs-list'),
    refreshJobs: document.getElementById('refresh-jobs'),
    docSearch: document.getElementById('doc-search'),
    docsTbody: document.getElementById('docs-tbody'),
    docsEmpty: document.getElementById('docs-empty'),
    refreshDocs: document.getElementById('refresh-docs'),
    usersTbody: document.getElementById('users-tbody'),
    usersEmpty: document.getElementById('users-empty'),
    refreshUsers: document.getElementById('refresh-users'),
    userRoleTabs: Array.from(document.querySelectorAll('.role-tab')),
    userSearch: document.getElementById('user-search'),
    usersPageSize: document.getElementById('users-page-size'),
    usersPageInfo: document.getElementById('users-page-info'),
    usersPrev: document.getElementById('users-prev'),
    usersNext: document.getElementById('users-next'),
    feedbackTbody: document.getElementById('feedback-tbody'),
    feedbackEmpty: document.getElementById('feedback-empty'),
    feedbackSearch: document.getElementById('feedback-search'),
    feedbackStatusFilter: document.getElementById('feedback-status-filter'),
    refreshFeedback: document.getElementById('refresh-feedback'),
    feedbackPageInfo: document.getElementById('feedback-page-info'),
    feedbackPrev: document.getElementById('feedback-prev'),
    feedbackNext: document.getElementById('feedback-next'),
    feedbackModal: document.getElementById('feedback-modal'),
    feedbackModalClose: document.getElementById('feedback-modal-close'),
    feedbackDetail: document.getElementById('feedback-detail'),
    feedbackStatusForm: document.getElementById('feedback-status-form'),
    feedbackStatus: document.getElementById('feedback-status'),
    feedbackNote: document.getElementById('feedback-note'),
    feedbackModalError: document.getElementById('feedback-modal-error'),
    feedbackSave: document.getElementById('feedback-save'),
    roleCountAll: document.getElementById('role-count-all'),
    roleCountAdmin: document.getElementById('role-count-admin'),
    roleCountUser: document.getElementById('role-count-user'),
    toast: document.getElementById('toast'),
};

const VIEW_META = {
    dashboard: {
        title: 'Tổng quan',
        subtitle: 'Theo dõi dữ liệu và tình trạng hệ thống.',
    },
    documents: {
        title: 'Tài liệu',
        subtitle: 'Tải lên, theo dõi và xóa tài liệu khỏi kho tri thức.',
    },
    feedback: {
        title: 'Ý kiến người dân',
        subtitle: 'Tiếp nhận, xử lý và ghi chú phản ánh của người dân.',
    },
    users: {
        title: 'Người dùng',
        subtitle: 'Quản lý tài khoản và vai trò truy cập.',
    },
};

const FEEDBACK_CATEGORY_LABELS = {
    gop_y: 'Góp ý',
    phan_anh: 'Phản ánh',
    kien_nghi: 'Kiến nghị',
    hoi_dap: 'Hỏi đáp',
};

const FEEDBACK_STATUS_LABELS = {
    new: 'Mới',
    received: 'Đã tiếp nhận',
    processing: 'Đang xử lý',
    resolved: 'Đã phản hồi',
    closed: 'Đã đóng',
};

const JOB_LABELS = {
    pending: 'Đang chờ',
    processing: 'Đang xử lý',
    completed: 'Hoàn tất',
    failed: 'Thất bại',
};

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
    const headers = { ...(options.headers || {}) };
    if (state.token) headers.Authorization = `Bearer ${state.token}`;

    const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers,
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

function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EMAIL_KEY);
    localStorage.removeItem(ROLE_KEY);
    state.token = '';
    state.email = '';
    state.role = '';
}

function showDenied(title, message) {
    els.loading.classList.add('hidden');
    els.shell.classList.add('hidden');
    els.deniedTitle.textContent = title;
    els.deniedMessage.textContent = message;
    els.denied.classList.remove('hidden');
}

function showToast(message, isError = false) {
    window.clearTimeout(state.toastTimer);
    els.toast.textContent = message;
    els.toast.classList.toggle('error', isError);
    els.toast.classList.remove('hidden');
    state.toastTimer = window.setTimeout(() => {
        els.toast.classList.add('hidden');
    }, 4200);
}

function setAlert(message, isError = false) {
    if (!message) {
        els.alert.textContent = '';
        els.alert.classList.add('hidden');
        return;
    }
    els.alert.textContent = message;
    els.alert.classList.toggle('error', isError);
    els.alert.classList.remove('hidden');
}

function handleApiError(error) {
    if (error.status === 401) {
        clearSession();
        showDenied(
            'Phiên đăng nhập đã hết hạn',
            'Vui lòng đăng nhập lại bằng tài khoản quản trị.'
        );
        return;
    }
    if (error.status === 403) {
        showDenied(
            'Không có quyền quản trị',
            'Tài khoản hiện tại không được phép truy cập trang này.'
        );
        return;
    }
    setAlert(error.message, true);
    showToast(error.message, true);
}

function formatDate(value) {
    if (!value) return '--';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString('vi-VN');
}

function statusBadge(status, label = null) {
    const badge = document.createElement('span');
    badge.className = `badge ${status}`;
    badge.textContent = label || JOB_LABELS[status] || status;
    return badge;
}

function emptyRow(tbody, columns, message) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = columns;
    cell.className = 'empty-state';
    cell.textContent = message;
    row.appendChild(cell);
    tbody.appendChild(row);
}

async function boot() {
    if (!state.token) {
        showDenied(
            'Cần đăng nhập',
            'Bạn cần đăng nhập bằng tài khoản quản trị để xem trang này.'
        );
        return;
    }

    try {
        const me = await apiRequest('/auth/me');
        if (me.role !== 'admin') {
            showDenied(
                'Không có quyền quản trị',
                'Tài khoản hiện tại chỉ có quyền sử dụng chat.'
            );
            return;
        }

        state.userId = me.id;
        state.email = me.email;
        state.role = me.role;
        els.email.textContent = me.email;
        els.role.textContent = me.role === 'admin' ? 'Quản trị viên' : me.role;
        els.loading.classList.add('hidden');
        els.shell.classList.remove('hidden');
        await loadDashboard();
    } catch (error) {
        if (error.status === 401) clearSession();
        showDenied(
            'Không thể xác thực',
            error.status === 401
                ? 'Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.'
                : error.message
        );
    }
}

async function loadDashboard() {
    setAlert('');
    try {
        const [adminStats, docStats] = await Promise.all([
            apiRequest('/admin/stats'),
            apiRequest('/documents/stats'),
        ]);

        els.statUsers.textContent = adminStats.users;
        els.statConversations.textContent = adminStats.conversations;
        els.statMessages.textContent = adminStats.messages;
        els.statChunks.textContent = adminStats.document_chunks;
        els.statFeedback.textContent = adminStats.feedback ?? 0;
        els.statFeedbackNew.textContent = adminStats.feedback_new ?? 0;
        els.statCollection.textContent = docStats.collection || '--';
        els.statBm25.textContent = docStats.bm25_indexed ? 'Sẵn sàng' : 'Chưa có';
        els.statBm25Detail.textContent = docStats.bm25_indexed
            ? `${docStats.bm25_corpus_size} chunk đã index`
            : 'Chỉ mục từ khóa chưa sẵn sàng';

        await loadJobs();
    } catch (error) {
        handleApiError(error);
    }
}

async function loadJobs() {
    try {
        state.jobs = await apiRequest('/documents/jobs');
        renderJobs();
    } catch (error) {
        if (error.status === 401 || error.status === 403) {
            handleApiError(error);
            return;
        }
        els.jobsList.replaceChildren();
        const message = document.createElement('p');
        message.className = 'empty-state';
        message.textContent = `Không tải được job: ${error.message}`;
        els.jobsList.appendChild(message);
    }
}

function renderJobs() {
    els.jobsList.replaceChildren();

    if (!state.jobs.length) {
        const empty = document.createElement('p');
        empty.className = 'empty-state';
        empty.textContent = 'Chưa có job nào trong phiên này.';
        els.jobsList.appendChild(empty);
        return;
    }

    for (const job of state.jobs.slice(0, 12)) {
        els.jobsList.appendChild(createJobRow(job));
    }
}

function createJobRow(job) {
    const row = document.createElement('div');
    row.className = 'job-row';

    const main = document.createElement('div');
    main.className = 'job-main';

    const name = document.createElement('span');
    name.className = 'job-name';
    name.textContent = job.filename || job.document_id || 'Tài liệu';

    const meta = document.createElement('span');
    meta.className = 'job-meta';
    const parts = [formatDate(job.created_at)];
    if (job.chunk_count) parts.push(`${job.chunk_count} chunk`);
    if (job.error_message) parts.push(job.error_message);
    meta.textContent = parts.join(' • ');

    main.append(name, meta);

    if (job.status === 'pending' || job.status === 'processing') {
        const progress = document.createElement('div');
        progress.className = 'job-progress';
        progress.appendChild(document.createElement('span'));
        main.appendChild(progress);
    }

    row.append(main, statusBadge(job.status));
    return row;
}

function renderUploads() {
    els.uploadList.replaceChildren();

    if (!state.uploads.size) return;

    for (const job of state.uploads.values()) {
        els.uploadList.appendChild(createJobRow(job));
    }
}

async function uploadFile(file) {
    if (!file) return;

    const allowed = ['.pdf', '.docx', '.txt'];
    const lowerName = file.name.toLowerCase();
    const extension = allowed.find((item) => lowerName.endsWith(item));
    if (!extension) {
        showToast('Chỉ hỗ trợ PDF, DOCX hoặc TXT.', true);
        return;
    }
    if (file.size > 50 * 1024 * 1024) {
        showToast('Tệp vượt quá giới hạn 50MB.', true);
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const accepted = await apiRequest('/documents', {
            method: 'POST',
            body: formData,
        });

        const job = {
            job_id: accepted.job_id,
            document_id: accepted.document_id,
            filename: accepted.filename,
            status: accepted.status || 'pending',
            chunk_count: 0,
            error_message: null,
            created_at: new Date().toISOString(),
            completed_at: null,
        };
        state.uploads.set(job.job_id, job);
        renderUploads();
        showToast(`Đã nhận tệp ${job.filename}. Đang xử lý...`);
        await pollUpload(job.job_id);
    } catch (error) {
        handleApiError(error);
    }
}

async function pollUpload(jobId) {
    while (state.uploads.has(jobId)) {
        await wait(1500);

        try {
            const job = await apiRequest(`/documents/${jobId}`);
            state.uploads.set(jobId, job);
            renderUploads();

            if (job.status === 'completed') {
                showToast(`Đã index xong ${job.filename} (${job.chunk_count} chunk).`);
                await Promise.all([loadDashboard(), loadDocuments()]);
                window.setTimeout(() => {
                    state.uploads.delete(jobId);
                    renderUploads();
                }, 3500);
                return;
            }

            if (job.status === 'failed') {
                showToast(
                    `Index thất bại: ${job.error_message || job.filename}`,
                    true
                );
                await loadJobs();
                window.setTimeout(() => {
                    state.uploads.delete(jobId);
                    renderUploads();
                }, 8000);
                return;
            }
        } catch (error) {
            state.uploads.delete(jobId);
            renderUploads();
            handleApiError(error);
            return;
        }
    }
}

function wait(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function loadDocuments() {
    try {
        state.documents = await apiRequest('/documents');
        renderDocuments();
    } catch (error) {
        handleApiError(error);
    }
}

function renderDocuments() {
    const query = els.docSearch.value.trim().toLowerCase();
    const rows = state.documents.filter((doc) => {
        if (!query) return true;
        return (
            (doc.filename || '').toLowerCase().includes(query) ||
            (doc.document_id || '').toLowerCase().includes(query)
        );
    });

    els.docsTbody.replaceChildren();
    els.docsEmpty.classList.toggle('hidden', rows.length > 0);

    if (!rows.length) {
        if (state.documents.length) {
            emptyRow(els.docsTbody, 5, 'Không tìm thấy tài liệu phù hợp.');
        }
        return;
    }

    for (const doc of rows) {
        const row = document.createElement('tr');

        const nameCell = document.createElement('td');
        const name = document.createElement('span');
        name.className = 'doc-name';
        name.textContent = doc.filename || 'Không có tên';
        nameCell.appendChild(name);

        const idCell = document.createElement('td');
        const id = document.createElement('span');
        id.className = 'doc-id';
        id.textContent = doc.document_id || '--';
        idCell.appendChild(id);

        const chunkCell = document.createElement('td');
        chunkCell.textContent = doc.chunk_count ?? 0;

        const statusCell = document.createElement('td');
        statusCell.appendChild(statusBadge('completed', 'Đã index'));

        const actionCell = document.createElement('td');
        const deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'row-action';
        deleteBtn.textContent = 'Xóa';
        deleteBtn.addEventListener('click', () => deleteDocument(doc, deleteBtn));
        actionCell.appendChild(deleteBtn);

        row.append(nameCell, idCell, chunkCell, statusCell, actionCell);
        els.docsTbody.appendChild(row);
    }
}

async function deleteDocument(doc, button) {
    const confirmed = window.confirm(
        `Xóa tài liệu "${doc.filename}"? Toàn bộ chunk và chỉ mục BM25 sẽ được cập nhật lại.`
    );
    if (!confirmed) return;

    button.disabled = true;
    button.textContent = 'Đang xóa...';

    try {
        const result = await apiRequest(
            `/documents/${encodeURIComponent(doc.document_id)}`,
            { method: 'DELETE' }
        );
        showToast(`Đã xóa ${result.deleted_chunks} chunk của ${doc.filename}.`);
        await Promise.all([loadDocuments(), loadDashboard()]);
    } catch (error) {
        button.disabled = false;
        button.textContent = 'Xóa';
        handleApiError(error);
    }
}

async function loadUsers() {
    const params = new URLSearchParams({
        role: state.usersRole,
        page: String(state.usersPage),
        page_size: String(state.usersPageSize),
    });
    if (state.usersSearch) params.set('search', state.usersSearch);

    try {
        const data = await apiRequest(`/users?${params.toString()}`);
        if (state.usersPage > data.total_pages) {
            state.usersPage = data.total_pages;
            return loadUsers();
        }

        state.users = data.items || [];
        state.usersTotal = data.total;
        state.usersTotalPages = data.total_pages;
        state.usersRoleCounts = data.role_counts || { all: 0, admin: 0, user: 0 };
        renderUsers();
        renderUserPagination();
    } catch (error) {
        handleApiError(error);
    }
}

function renderUserRoleTabs() {
    els.roleCountAll.textContent = state.usersRoleCounts.all;
    els.roleCountAdmin.textContent = state.usersRoleCounts.admin;
    els.roleCountUser.textContent = state.usersRoleCounts.user;

    for (const tab of els.userRoleTabs) {
        const active = tab.dataset.role === state.usersRole;
        tab.classList.toggle('active', active);
        tab.setAttribute('aria-selected', String(active));
    }
}

function renderUsers() {
    renderUserRoleTabs();
    els.usersTbody.replaceChildren();
    els.usersEmpty.classList.toggle('hidden', state.users.length > 0);

    if (!state.users.length) {
        const roleLabels = {
            all: 'người dùng',
            admin: 'quản trị viên',
            user: 'người dùng',
        };
        els.usersEmpty.textContent = state.usersSearch
            ? 'Không tìm thấy người dùng phù hợp.'
            : `Chưa có ${roleLabels[state.usersRole]} nào.`;
        return;
    }

    for (const user of state.users) {
        const row = document.createElement('tr');

        const emailCell = document.createElement('td');
        emailCell.textContent = user.email;

        const nameCell = document.createElement('td');
        nameCell.textContent = user.full_name || '--';

        const roleCell = document.createElement('td');
        const select = document.createElement('select');
        select.setAttribute('aria-label', `Vai trò của ${user.email}`);
        for (const role of ['user', 'admin']) {
            const option = document.createElement('option');
            option.value = role;
            option.textContent = role === 'admin' ? 'Quản trị viên' : 'Người dùng';
            option.selected = user.role === role;
            select.appendChild(option);
        }
        const isSelf = user.id === state.userId;
        select.disabled = isSelf;
        if (isSelf) select.title = 'Không thể tự đổi vai trò của chính mình';
        select.addEventListener('change', () => updateUserRole(user, select));
        roleCell.appendChild(select);

        const statusCell = document.createElement('td');
        statusCell.appendChild(
            statusBadge(user.is_active ? 'active' : 'locked', user.is_active ? 'Hoạt động' : 'Đã khóa')
        );

        row.append(emailCell, nameCell, roleCell, statusCell);
        els.usersTbody.appendChild(row);
    }
}

function renderUserPagination() {
    els.usersPageInfo.textContent =
        `Trang ${state.usersPage}/${state.usersTotalPages} • ${state.usersTotal} người dùng`;
    els.usersPrev.disabled = state.usersPage <= 1;
    els.usersNext.disabled = state.usersPage >= state.usersTotalPages;
}

async function updateUserRole(user, select) {
    const previous = user.role;
    const next = select.value;
    select.disabled = true;

    try {
        const updated = await apiRequest(`/users/${user.id}/role`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role: next }),
        });
        showToast(`Đã đổi vai trò của ${user.email} thành ${updated.role}.`);
        await loadUsers();
    } catch (error) {
        select.value = previous;
        select.disabled = user.id === state.userId;
        handleApiError(error);
    }
}

async function loadFeedback() {
    const params = new URLSearchParams({
        status: state.feedbackStatus,
        page: String(state.feedbackPage),
        page_size: String(state.feedbackPageSize),
    });
    if (state.feedbackSearch) params.set('search', state.feedbackSearch);

    try {
        const data = await apiRequest(`/feedback?${params.toString()}`);
        if (state.feedbackPage > data.total_pages) {
            state.feedbackPage = data.total_pages;
            return loadFeedback();
        }
        state.feedback = data.items || [];
        state.feedbackTotal = data.total;
        state.feedbackTotalPages = data.total_pages;
        state.feedbackStatusCounts = data.status_counts || state.feedbackStatusCounts;
        renderFeedback();
        renderFeedbackPagination();
    } catch (error) {
        handleApiError(error);
    }
}

function renderFeedback() {
    els.feedbackTbody.replaceChildren();
    els.feedbackEmpty.classList.toggle('hidden', state.feedback.length > 0);

    if (!state.feedback.length) {
        els.feedbackEmpty.textContent = state.feedbackSearch
            ? 'Không tìm thấy ý kiến phù hợp.'
            : 'Chưa có ý kiến nào.';
        return;
    }

    for (const item of state.feedback) {
        const row = document.createElement('tr');

        const dateCell = document.createElement('td');
        dateCell.textContent = formatDate(item.created_at);

        const senderCell = document.createElement('td');
        const sender = document.createElement('div');
        sender.className = 'feedback-sender';
        sender.textContent = item.full_name || 'Ẩn danh';
        const contact = document.createElement('small');
        contact.textContent = [item.phone, item.email].filter(Boolean).join(' • ') || 'Không để lại liên hệ';
        senderCell.append(sender, contact);

        const subjectCell = document.createElement('td');
        const subject = document.createElement('div');
        subject.className = 'feedback-subject';
        subject.textContent = item.subject;
        const preview = document.createElement('small');
        preview.textContent = (item.content || '').slice(0, 90);
        subjectCell.append(subject, preview);

        const categoryCell = document.createElement('td');
        categoryCell.textContent = FEEDBACK_CATEGORY_LABELS[item.category] || item.category;

        const statusCell = document.createElement('td');
        statusCell.appendChild(
            statusBadge(item.status, FEEDBACK_STATUS_LABELS[item.status] || item.status)
        );

        const actionCell = document.createElement('td');
        const action = document.createElement('button');
        action.type = 'button';
        action.className = 'row-action';
        action.textContent = 'Xử lý';
        action.addEventListener('click', () => openFeedbackModal(item));
        actionCell.appendChild(action);

        row.append(dateCell, senderCell, subjectCell, categoryCell, statusCell, actionCell);
        els.feedbackTbody.appendChild(row);
    }
}

function renderFeedbackPagination() {
    els.feedbackPageInfo.textContent =
        `Trang ${state.feedbackPage}/${state.feedbackTotalPages} • ${state.feedbackTotal} ý kiến`;
    els.feedbackPrev.disabled = state.feedbackPage <= 1;
    els.feedbackNext.disabled = state.feedbackPage >= state.feedbackTotalPages;
}

function feedbackDetailRow(label, value) {
    const row = document.createElement('div');
    row.className = 'feedback-detail-row';
    const term = document.createElement('span');
    term.textContent = label;
    const content = document.createElement('strong');
    content.textContent = value || '--';
    row.append(term, content);
    return row;
}

function openFeedbackModal(item) {
    state.activeFeedback = item;
    els.feedbackDetail.replaceChildren(
        feedbackDetailRow('Người gửi', item.full_name || 'Ẩn danh'),
        feedbackDetailRow('Liên hệ', [item.phone, item.email].filter(Boolean).join(' • ')),
        feedbackDetailRow('Loại', FEEDBACK_CATEGORY_LABELS[item.category] || item.category),
        feedbackDetailRow('Tiêu đề', item.subject),
        feedbackDetailRow('Nội dung', item.content),
        feedbackDetailRow('Ngày gửi', formatDate(item.created_at)),
    );
    els.feedbackStatus.value = item.status;
    els.feedbackNote.value = item.admin_note || '';
    els.feedbackModalError.classList.add('hidden');
    els.feedbackModal.classList.remove('hidden');
}

function closeFeedbackModal() {
    els.feedbackModal.classList.add('hidden');
    state.activeFeedback = null;
}

async function saveFeedback(event) {
    event.preventDefault();
    if (!state.activeFeedback) return;

    els.feedbackSave.disabled = true;
    els.feedbackSave.textContent = 'Đang lưu...';
    els.feedbackModalError.classList.add('hidden');

    try {
        const updated = await apiRequest(`/feedback/${state.activeFeedback.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                status: els.feedbackStatus.value,
                admin_note: els.feedbackNote.value.trim(),
            }),
        });
        showToast(`Đã cập nhật ý kiến: ${FEEDBACK_STATUS_LABELS[updated.status] || updated.status}.`);
        closeFeedbackModal();
        await Promise.all([loadFeedback(), loadDashboard()]);
    } catch (error) {
        els.feedbackModalError.textContent = error.message;
        els.feedbackModalError.classList.remove('hidden');
    } finally {
        els.feedbackSave.disabled = false;
        els.feedbackSave.textContent = 'Lưu xử lý';
    }
}

function switchView(view) {
    if (!VIEW_META[view]) return;
    state.view = view;

    for (const item of els.navItems) {
        item.classList.toggle('active', item.dataset.view === view);
    }
    for (const [name, section] of Object.entries(els.views)) {
        section.classList.toggle('hidden', name !== view);
    }

    els.pageTitle.textContent = VIEW_META[view].title;
    els.pageSubtitle.textContent = VIEW_META[view].subtitle;
    els.sidebar.classList.remove('open');
    setAlert('');

    if (view === 'dashboard') loadDashboard();
    if (view === 'documents') Promise.all([loadDocuments(), loadDashboard()]);
    if (view === 'feedback') loadFeedback();
    if (view === 'users') loadUsers();
}

function refreshCurrentView() {
    if (state.view === 'dashboard') loadDashboard();
    if (state.view === 'documents') Promise.all([loadDocuments(), loadDashboard()]);
    if (state.view === 'feedback') loadFeedback();
    if (state.view === 'users') loadUsers();
}

els.menu.addEventListener('click', () => els.sidebar.classList.toggle('open'));
els.logout.addEventListener('click', () => {
    clearSession();
    window.location.href = 'index.html';
});
els.refresh.addEventListener('click', refreshCurrentView);
els.refreshJobs.addEventListener('click', loadJobs);
els.refreshDocs.addEventListener('click', loadDocuments);
els.refreshUsers.addEventListener('click', loadUsers);
els.refreshFeedback.addEventListener('click', loadFeedback);
els.docSearch.addEventListener('input', renderDocuments);

els.feedbackSearch.addEventListener('input', () => {
    window.clearTimeout(state.feedbackSearchTimer);
    state.feedbackSearchTimer = window.setTimeout(() => {
        state.feedbackSearch = els.feedbackSearch.value.trim();
        state.feedbackPage = 1;
        loadFeedback();
    }, 300);
});

els.feedbackStatusFilter.addEventListener('change', () => {
    state.feedbackStatus = els.feedbackStatusFilter.value;
    state.feedbackPage = 1;
    loadFeedback();
});

els.feedbackPrev.addEventListener('click', () => {
    if (state.feedbackPage <= 1) return;
    state.feedbackPage -= 1;
    loadFeedback();
});

els.feedbackNext.addEventListener('click', () => {
    if (state.feedbackPage >= state.feedbackTotalPages) return;
    state.feedbackPage += 1;
    loadFeedback();
});

els.feedbackModalClose.addEventListener('click', closeFeedbackModal);
els.feedbackModal.addEventListener('click', (event) => {
    if (event.target === els.feedbackModal) closeFeedbackModal();
});
els.feedbackStatusForm.addEventListener('submit', saveFeedback);

for (const tab of els.userRoleTabs) {
    tab.addEventListener('click', () => {
        state.usersRole = tab.dataset.role;
        state.usersPage = 1;
        loadUsers();
    });
}

els.userSearch.addEventListener('input', () => {
    window.clearTimeout(state.usersSearchTimer);
    state.usersSearchTimer = window.setTimeout(() => {
        state.usersSearch = els.userSearch.value.trim();
        state.usersPage = 1;
        loadUsers();
    }, 300);
});

els.usersPageSize.addEventListener('change', () => {
    state.usersPageSize = Number(els.usersPageSize.value) || 10;
    state.usersPage = 1;
    loadUsers();
});

els.usersPrev.addEventListener('click', () => {
    if (state.usersPage <= 1) return;
    state.usersPage -= 1;
    loadUsers();
});

els.usersNext.addEventListener('click', () => {
    if (state.usersPage >= state.usersTotalPages) return;
    state.usersPage += 1;
    loadUsers();
});

for (const item of els.navItems) {
    item.addEventListener('click', () => switchView(item.dataset.view));
}

els.dropZone.addEventListener('click', () => els.fileInput.click());
els.dropZone.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        els.fileInput.click();
    }
});
els.fileInput.addEventListener('change', () => {
    const file = els.fileInput.files?.[0];
    els.fileInput.value = '';
    uploadFile(file);
});
els.uploadBtn.addEventListener('click', () => els.fileInput.click());

for (const eventName of ['dragenter', 'dragover']) {
    els.dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        els.dropZone.classList.add('dragover');
    });
}
for (const eventName of ['dragleave', 'drop']) {
    els.dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        els.dropZone.classList.remove('dragover');
    });
}
els.dropZone.addEventListener('drop', (event) => {
    const file = event.dataTransfer?.files?.[0];
    uploadFile(file);
});

boot();
