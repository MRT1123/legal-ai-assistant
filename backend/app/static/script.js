/**
 * 法律智能助手 - 前端交互逻辑
 * 支持4大功能：法律问答、合同审查、文书生成、案例分析
 */

// ==================== 全局状态 ====================
let isLoading = false;
let currentSessionId = null;
let currentFeature = null;  // 当前选择的功能（qa/contract_review/document_gen/case_analysis/legal_calculator）
let selectedFile = null;     // 选中的上传文件（合同审查用）
let uploadedFileText = null; // 上传文件解析后的文本内容
let sidebarOpen = false;     // 侧边栏是否打开
let placeholderTimer = null; // placeholder 轮播定时器

// 主页 placeholder 轮播文案
const PLACEHOLDER_ROTATE = [
    '输入你的法律问题，按 Enter 发送...',
    '试试问我：公司辞退我应该赔多少钱？',
    '试试问我：帮我审查一份租赁合同',
    '试试问我：拖欠工资怎么申请仲裁？',
    '试试问我：帮我写一份律师函',
    '试试问我：交通事故赔偿怎么算？',
];

// 功能配置
const FEATURE_CONFIG = {
    qa: {
        name: '📖 法律问答',
        placeholder: '输入你的法律问题，如"公司辞退我应该赔多少？"',
        label: '📖 法律问答 · 3 Agent 协作'
    },
    contract_review: {
        name: '📋 合同审查',
        placeholder: '点击左下角 📎 上传合同文件（PDF/Word），或直接粘贴合同文本...',
        label: '📋 合同风险审查 · 4 Agent 流水线'
    },
    document_gen: {
        name: '✍️ 文书生成',
        placeholder: '描述你需要的文书，如"帮我写一份劳动仲裁申请书，公司拖欠工资3个月..."',
        label: '✍️ 法律文书生成 · 3 Agent 流水线'
    },
    case_analysis: {
        name: '📊 案例分析',
        placeholder: '描述你的案件经过，AI 将分析事实、检索法条、评估胜诉率...',
        label: '📊 案例分析 · 3 Agent 流水线'
    },
    legal_calculator: {
        name: '🔢 法律计算器',
        placeholder: '输入计算需求，如"我在公司干了3年，月薪8000，被辞退了能拿多少赔偿？"',
        label: '🔢 法律计算器 · 3 Agent 流水线'
    }
};

// ==================== DOM 元素 ====================
const welcomeScreen = document.getElementById('welcome-screen');
const chatArea = document.getElementById('chat-area');
const messageList = document.getElementById('message-list');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const featureBar = document.getElementById('current-feature-bar');
const featureLabel = document.getElementById('current-feature-label');
const sessionsList = document.getElementById('sessions-list');
const historySidebar = document.getElementById('history-sidebar');

// ==================== 功能选择 ====================

/**
 * 选择功能（从欢迎页卡片点击触发）
 */
function selectFeature(feature) {
    currentFeature = feature;
    const config = FEATURE_CONFIG[feature];
    
    // 更新输入框提示
    chatInput.placeholder = config.placeholder;
    
    // 停止主页 placeholder 轮播
    stopPlaceholderRotate();
    
    // 合同审查模式下显示文件上传按钮
    const uploadBtn = document.getElementById('upload-btn');
    uploadBtn.style.display = (feature === 'contract_review') ? 'flex' : 'none';
    
    // 更新功能标识栏
    featureLabel.textContent = config.label;
    featureBar.style.display = 'flex';
    
    // 切换到对话模式
    showChatArea();
    
    // 添加欢迎消息（用 'welcome' 类型，不触发导出按钮）
    const welcomeMsg = getFeatureWelcomeMessage(feature);
    appendMessage('assistant', welcomeMsg, 'welcome');
    
    chatInput.focus();
}

/**
 * 启动 placeholder 轮播（主页欢迎页）
 */
function startPlaceholderRotate() {
    stopPlaceholderRotate();
    let idx = 0;
    chatInput.placeholder = PLACEHOLDER_ROTATE[0];
    placeholderTimer = setInterval(() => {
        idx = (idx + 1) % PLACEHOLDER_ROTATE.length;
        chatInput.placeholder = PLACEHOLDER_ROTATE[idx];
    }, 3000);
}

/**
 * 停止 placeholder 轮播
 */
function stopPlaceholderRotate() {
    if (placeholderTimer) {
        clearInterval(placeholderTimer);
        placeholderTimer = null;
    }
}

/**
 * 返回欢迎页（切换功能）
 */
function backToWelcome() {
    currentFeature = null;
    currentSessionId = null;
    messageList.innerHTML = '';
    featureBar.style.display = 'none';
    chatArea.style.display = 'none';
    welcomeScreen.style.display = 'flex';
    chatInput.value = '';
    // 隐藏上传按钮并清理文件状态
    const uploadBtn = document.getElementById('upload-btn');
    if (uploadBtn) uploadBtn.style.display = 'none';
    selectedFile = null;
    uploadedFileText = null;
    const fileInput = document.getElementById('file-input');
    if (fileInput) fileInput.value = '';
    const uploadPreview = document.getElementById('upload-preview');
    if (uploadPreview) uploadPreview.style.display = 'none';
    // 重置输入框 placeholder 并启动轮播
    stopPlaceholderRotate();
    startPlaceholderRotate();
}

/**
 * 开始新对话
 */
function newSession() {
    currentSessionId = null;
    messageList.innerHTML = '';
    
    // 清除侧边栏中的活跃状态
    document.querySelectorAll('.session-item.active').forEach(item => {
        item.classList.remove('active');
    });
    
    if (currentFeature) {
        // 保持当前功能，清空对话
        const welcomeMsg = getFeatureWelcomeMessage(currentFeature);
        appendMessage('assistant', welcomeMsg, 'welcome');
    } else {
        backToWelcome();
    }
    chatInput.focus();
    
    // 刷新侧边栏列表
    loadSessions();
}

/**
 * 获取功能的欢迎消息
 */
function getFeatureWelcomeMessage(feature) {
    const messages = {
        qa: '你好！我是你的 AI 法律顾问。请直接输入你的法律问题，我会检索法律知识库为你解答。\n\n**使用流程：** Router（分类）→ Agent（检索）→ Generator（生成）',
        contract_review: '你好！我是合同审查助手。你可以**上传合同文件**（支持 PDF、Word、TXT 格式），也可以直接粘贴合同文本。我将启动 4 个 AI 专家为你协作审查：\n\n1. 📋 **解析 Agent** — 提取关键条款\n2. 🔍 **风险 Agent** — 识别风险点\n3. ⚖️ **合规 Agent** — 检查合法性\n4. 📝 **报告 Agent** — 生成审查报告\n\n💡 点击输入框左侧的 📎 按钮即可上传文件。',
        document_gen: '你好！我是法律文书生成助手。请描述你需要的文书和案情，我将启动 3 个 AI 专家为你协作：\n\n1. 🎯 **需求分析 Agent** — 提取关键信息\n2. ✍️ **文书起草 Agent** — 生成文书初稿\n3. ✅ **格式审核 Agent** — 审核完善\n\n支持：仲裁申请书、起诉状、律师函、答辩状等',
        case_analysis: '你好！我是案例分析助手。请详细描述你的案件经过，我将启动 3 个 AI 专家为你分析：\n\n1. 📌 **事实梳理 Agent** — 整理时间线和证据\n2. 📚 **法条检索 Agent** — 查找相关法律\n3. 📊 **策略分析 Agent** — 评估胜诉率和策略\n\n请尽量详细描述事件经过、当事人信息、争议焦点等。',
        legal_calculator: '你好！我是法律计算助手。请描述你的计算需求，我将启动 3 个 AI 专家为你精确计算：\n\n1. 🔍 **参数解析 Agent** — 提取计算参数\n2. 🧮 **计算执行 Agent** — 精确计算（非 AI 估算）\n3. 📝 **结果审核 Agent** — 校验并出具报告\n\n**支持的计算类型：**\n- 💰 经济补偿金 / 赔偿金（N、N+1、2N）\n- 📄 合同违约金\n- 💳 逾期利息 / 滞纳金\n- 🏥 人身损害赔偿\n- 👶 抚养费 / 赡养费\n\n💡 请尽量提供具体数字（如月薪、工作年限、金额等），计算结果更精确。'
    };
    return messages[feature] || '请选择一个功能开始使用。';
}

// ==================== 发送消息 ====================

async function sendMessage() {
    // 如果有上传文件但还没解析，先上传解析
    if (selectedFile && !uploadedFileText) {
        const uploadResult = await uploadFile(selectedFile);
        if (!uploadResult) return;  // 上传失败，停止发送
        uploadedFileText = uploadResult;
    }

    // 用户输入框的文本作为补充说明（可选）
    const userInput = chatInput.value.trim();
    if (!userInput && !uploadedFileText) return;  // 既没文件也没文字，不发送
    if (isLoading) return;

    // 如果还没选功能，根据内容自动判断
    if (!currentFeature) {
        currentFeature = 'qa';
        chatInput.placeholder = FEATURE_CONFIG.qa.placeholder;
        featureLabel.textContent = FEATURE_CONFIG.qa.label;
        featureBar.style.display = 'flex';
        showChatArea();
    }

    // 用户消息气泡：有文件时显示文件名
    if (selectedFile) {
        const fileSummary = `📄 上传了文件：${selectedFile.name}`;
        const displayText = userInput ? `${fileSummary}\n💬 ${userInput}` : fileSummary;
        appendMessage('user', displayText);
    } else {
        appendMessage('user', userInput);
    }

    chatInput.value = '';
    chatInput.style.height = 'auto';

    // 清理文件状态
    selectedFile = null;
    const fileInput = document.getElementById('file-input');
    if (fileInput) fileInput.value = '';
    document.getElementById('upload-preview').style.display = 'none';

    // 调用流式 API，传入文件文本和补充说明
    await callStreamAPI(userInput, uploadedFileText);
    uploadedFileText = null;
}

function sendSuggestion(card) {
    const text = card.querySelector('.suggestion-text').textContent;
    chatInput.value = text;
    // 建议卡片默认走 QA
    if (!currentFeature) {
        selectFeature('qa');
    }
    sendMessage();
}

// ==================== 流式 API 调用 ====================

async function callStreamAPI(query, fileText = null) {
    isLoading = true;
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    // 移除之前的进度提示
    removeProgressMessage();

    try {
        const response = await fetch('/chat/stream', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                query: query,
                session_id: currentSessionId,
                task_type: currentFeature,
                file_text: fileText
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullAnswer = '';
        let queryType = '';
        let sources = [];
        let { bubble, contentDiv } = appendEmptyAssistantMessage();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            let currentEvent = '';

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    currentEvent = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                    const dataStr = line.slice(6);
                    try {
                        const data = JSON.parse(dataStr);

                        if (currentEvent === 'progress') {
                            // 显示进度提示
                            showProgressMessage(data.content);
                        } else if (currentEvent === 'metadata') {
                            if (data.query_type) {
                                queryType = data.query_type;
                                addQueryTypeTag(contentDiv, queryType);
                            }
                            if (data.task_type) {
                                queryType = data.task_type;
                            }
                        } else if (currentEvent === 'token') {
                            // 收到文本片段，移除进度提示
                            removeProgressMessage();
                            fullAnswer += data.content;
                            bubble.innerHTML = renderMarkdown(fullAnswer) + '<span class="streaming-cursor">▌</span>';
                            scrollToBottom();
                        } else if (currentEvent === 'done') {
                            removeProgressMessage();
                            sources = data.sources || [];
                            currentSessionId = data.session_id;
                            if (data.query_type) queryType = data.query_type;
                            // 对话完成后刷新侧边栏列表
                            loadSessions();
                        } else if (currentEvent === 'error') {
                            removeProgressMessage();
                            bubble.innerHTML = `<span style="color: #e74c3c;">❌ ${data.content}</span>`;
                        }
                    } catch (e) {
                        console.warn('JSON parse error:', dataStr);
                    }
                }
            }
        }

        // 流结束，最终渲染
        removeProgressMessage();
        if (fullAnswer) {
            bubble.innerHTML = renderMarkdown(fullAnswer);
        }
        if (sources.length > 0) {
            addSourcesSection(contentDiv, sources);
        }

        // 为可导出的功能添加导出按钮（文书生成、合同审查、案例分析）
        const exportableTypes = ['document_gen', 'contract_review', 'case_analysis', 'legal_calculator'];
        if (exportableTypes.includes(queryType) && fullAnswer) {
            addExportButtons(contentDiv, fullAnswer, queryType);
        }

    } catch (error) {
        removeProgressMessage();
        console.error('请求失败：', error);
        appendMessage('assistant', `❌ 请求失败：${error.message}。请确认后端服务正在运行。`);
    } finally {
        isLoading = false;
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
        chatInput.focus();
    }
}

// ==================== 进度提示 ====================

let progressEl = null;

function showProgressMessage(text) {
    removeProgressMessage();
    progressEl = document.createElement('div');
    progressEl.className = 'progress-message';
    progressEl.id = 'progress-indicator';
    progressEl.innerHTML = `
        <div style="width: 36px;"></div>
        <div class="progress-bubble">
            <span class="progress-spinner"></span>
            ${text}
        </div>
    `;
    messageList.appendChild(progressEl);
    scrollToBottom();
}

function removeProgressMessage() {
    if (progressEl) {
        progressEl.remove();
        progressEl = null;
    }
    const existing = document.getElementById('progress-indicator');
    if (existing) existing.remove();
}

// ==================== 界面操作 ====================

function showChatArea() {
    welcomeScreen.style.display = 'none';
    chatArea.style.display = 'flex';
}

function appendMessage(role, content, queryType = null, sources = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? '我' : '⚖️';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    if (role === 'assistant' && queryType) {
        addQueryTypeTag(contentDiv, queryType);
    }

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    if (role === 'assistant') {
        bubble.innerHTML = renderMarkdown(content);
    } else {
        bubble.textContent = content;
    }

    contentDiv.appendChild(bubble);

    if (sources && sources.length > 0) {
        addSourcesSection(contentDiv, sources);
    }

    // 为可导出的功能添加导出按钮
    const exportableTypes = ['document_gen', 'contract_review', 'case_analysis'];
    if (role === 'assistant' && exportableTypes.includes(queryType) && content) {
        addExportButtons(contentDiv, content, queryType);
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    messageList.appendChild(messageDiv);

    scrollToBottom();
    return { messageDiv, bubble, contentDiv };
}

function appendEmptyAssistantMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = '⚖️';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.innerHTML = '<span class="streaming-cursor">▌</span>';

    contentDiv.appendChild(bubble);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    messageList.appendChild(messageDiv);

    scrollToBottom();
    return { messageDiv, bubble, contentDiv };
}

function addQueryTypeTag(contentDiv, queryType) {
    // welcome 消息不显示标签
    if (queryType === 'welcome') return;
    // 如果已有标签则不重复添加
    if (contentDiv.querySelector('.message-type-tag')) return;

    const tagLabels = {
        'qa': '📖 法律问答',
        'general': '📖 知识解答',
        'simple': '📖 知识解答',
        'complex': '🔍 深度分析',
        'contract_review': '📋 合同审查',
        'document_gen': '✍️ 文书生成',
        'case_analysis': '📊 案例分析',
        'legal_calculator': '🔢 法律计算器'
    };

    const tagClasses = {
        'general': 'tag-general',
        'complex': 'tag-complex',
        'contract_review': 'tag-contract_review',
        'document_gen': 'tag-document_gen',
        'case_analysis': 'tag-case_analysis',
        'legal_calculator': 'tag-legal_calculator'
    };

    const tag = document.createElement('div');
    tag.className = `message-type-tag ${tagClasses[queryType] || 'tag-general'}`;
    tag.textContent = tagLabels[queryType] || queryType;

    if (contentDiv.firstChild) {
        contentDiv.insertBefore(tag, contentDiv.firstChild);
    } else {
        contentDiv.appendChild(tag);
    }
}

function addSourcesSection(contentDiv, sources) {
    if (!sources || sources.length === 0) return;

    const section = document.createElement('div');
    section.className = 'sources-section';

    const title = document.createElement('div');
    title.className = 'sources-title';
    title.innerHTML = '\ud83d\udcda \u53c2\u8003\u6cd5\u5f8b\u4f9d\u636e';
    section.appendChild(title);

    sources.forEach((source, index) => {
        const item = document.createElement('div');
        item.className = 'source-item-structured';

        const tag = document.createElement('span');
        tag.className = 'source-tag';
        const lawName = source.law_name || '';
        const article = source.article || '';
        if (lawName && article) {
            tag.innerHTML = '\u300a' + lawName + '\u300b' + article;
        } else if (lawName) {
            tag.innerHTML = '\u300a' + lawName + '\u300b';
        } else {
            tag.textContent = '\u6cd5\u5f8b\u6761\u6587 ' + (index + 1);
        }

        tag.onclick = function() {
            showArticleModalBySource(source);
        };

        item.appendChild(tag);
        section.appendChild(item);
    });

    contentDiv.appendChild(section);
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        messageList.scrollTop = messageList.scrollHeight;
    });
}

// ==================== 法条全文弹窗 ====================

function showArticleModal(element) {
    const lawName = element.getAttribute('data-law');
    const article = element.getAttribute('data-article');

    let fullContent = '';
    if (typeof sources !== 'undefined' && sources.length > 0) {
        for (let s of sources) {
            if (s.law_name === lawName && s.article === article) {
                fullContent = s.full_content || s.content || '';
                break;
            }
        }
    }

    if (!fullContent && typeof sources !== 'undefined') {
        for (let s of sources) {
            if (s.law_name && s.law_name.includes(lawName)) {
                if (!s.article || article.includes(s.article.replace(/第/, '').replace(/条/, ''))) {
                    fullContent = s.full_content || s.content || '';
                    break;
                }
            }
        }
    }

    _showModal(lawName, article, fullContent);
}

function showArticleModalBySource(source) {
    const lawName = source.law_name || '';
    const article = source.article || '';
    const fullContent = source.full_content || source.content || '';
    _showModal(lawName, article, fullContent);
}

function _showModal(lawName, article, fullContent) {
    const existing = document.querySelector('.article-modal-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'article-modal-overlay';
    overlay.onclick = function(e) {
        if (e.target === overlay) overlay.remove();
    };

    const modal = document.createElement('div');
    modal.className = 'article-modal-content';

    const header = document.createElement('div');
    header.className = 'article-modal-header';

    const titleText = document.createElement('h3');
    titleText.textContent = '《' + lawName + '》 ' + article;

    const closeBtn = document.createElement('button');
    closeBtn.className = 'article-modal-close';
    closeBtn.innerHTML = '&times;';
    closeBtn.onclick = function() { overlay.remove(); };

    header.appendChild(titleText);
    header.appendChild(closeBtn);

    const body = document.createElement('div');
    body.className = 'article-modal-body';
    body.textContent = fullContent || '暂无条文全文内容';

    modal.appendChild(header);
    modal.appendChild(body);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
}


// ==================== Markdown 渲染 ====================

function renderMarkdown(text) {
    if (!text) return '';

    // 先移除内联引用标记 [引用:xxx|yyy]（不显示在正文中）
    let cleaned = text.replace(/\[引用:[^\]]+\]/g, '');

    let html = cleaned
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');

    html = '<p>' + html + '</p>';

    html = html.replace(/(<li>.*?<\/li>(<br>)?)+/g, (match) => {
        return '<ul>' + match.replace(/<br>/g, '') + '</ul>';
    });

    return html;
}

// ==================== 输入框 ====================

function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// ==================== 页面加载 ====================

window.addEventListener('DOMContentLoaded', () => {
    // 检查登录状态
    checkAuth();
});

// ==================== 历史对话侧边栏 ====================

/**
 * 切换侧边栏显示/隐藏
 */
function toggleSidebar() {
    sidebarOpen = !sidebarOpen;
    historySidebar.classList.toggle('open', sidebarOpen);
    document.querySelector('.history-toggle-btn').classList.toggle('active', sidebarOpen);
    
    // 打开时刷新列表，并清空搜索
    if (sidebarOpen) {
        const searchInput = document.getElementById('sidebar-search-input');
        const clearBtn = document.getElementById('search-clear-btn');
        if (searchInput) searchInput.value = '';
        if (clearBtn) clearBtn.style.display = 'none';
        isSearchMode = false;
        currentSearchKeyword = '';
        loadSessions();
    }
}

/**
 * 从后端加载所有会话列表
 */
async function loadSessions() {
    try {
        const response = await fetch('/history/sessions', {
            headers: getAuthHeaders()
        });
        if (!response.ok) return;
        const data = await response.json();
        renderSessions(data.sessions || []);
    } catch (error) {
        console.error('加载历史会话失败:', error);
    }
}

/** 搜索防抖定时器 */
let searchTimer = null;
/** 当前是否处于搜索模式 */
let isSearchMode = false;
/** 当前搜索关键词 */
let currentSearchKeyword = '';

/**
 * 防抖搜索（输入停顿 300ms 后触发搜索）
 */
function debounceSearch() {
    const input = document.getElementById('sidebar-search-input');
    const clearBtn = document.getElementById('search-clear-btn');
    const keyword = input.value.trim();

    // 显示/隐藏清除按钮
    clearBtn.style.display = keyword ? 'flex' : 'none';

    // 清空时恢复全部列表
    if (!keyword) {
        isSearchMode = false;
        currentSearchKeyword = '';
        loadSessions();
        return;
    }

    // 防抖：300ms 内连续输入只触发最后一次
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
        searchSessions(keyword);
    }, 300);
}

/**
 * 调用后端搜索接口
 */
async function searchSessions(keyword) {
    isSearchMode = true;
    currentSearchKeyword = keyword;

    try {
        const response = await fetch(`/history/search?q=${encodeURIComponent(keyword)}`, {
            headers: getAuthHeaders()
        });
        if (!response.ok) return;
        const data = await response.json();
        renderSessions(data.sessions || [], keyword);
    } catch (error) {
        console.error('搜索失败:', error);
    }
}

/**
 * 清除搜索
 */
function clearSearch() {
    const input = document.getElementById('sidebar-search-input');
    const clearBtn = document.getElementById('search-clear-btn');
    input.value = '';
    clearBtn.style.display = 'none';
    isSearchMode = false;
    currentSearchKeyword = '';
    loadSessions();
    input.focus();
}

/**
 * 渲染会话列表到侧边栏
 * @param {Array} sessions - 会话列表
 * @param {string} searchKeyword - 搜索关键词（可选，用于高亮显示）
 */
function renderSessions(sessions, searchKeyword = '') {
    if (!sessionsList) return;
    
    if (!sessions || sessions.length === 0) {
        const emptyMsg = searchKeyword 
            ? `未找到包含"${escapeHtml(searchKeyword)}"的对话` 
            : '暂无历史对话';
        sessionsList.innerHTML = `
            <div class="sessions-empty">
                <i class="fas fa-${searchKeyword ? 'search' : 'inbox'}"></i>
                <p>${emptyMsg}</p>
            </div>
        `;
        return;
    }
    
    sessionsList.innerHTML = sessions.map(session => {
        const isActive = session.session_id === currentSessionId;
        let title = session.first_message || '新对话';
        
        // 搜索模式下高亮关键词
        if (searchKeyword) {
            const regex = new RegExp(`(${escapeRegex(searchKeyword)})`, 'gi');
            title = escapeHtml(title).replace(regex, '<mark style="background:#667eea;color:white;border-radius:2px;padding:0 2px;">$1</mark>');
        } else {
            title = escapeHtml(title);
        }
        
        const displayTitle = title.length > 60 ? title.substring(0, 60) + '...' : title;
        const time = session.last_time ? formatRelativeTime(session.last_time) : '';
        
        // 搜索模式显示匹配数量
        const matchBadge = session.match_count > 1 
            ? `<span class="session-match-count">${session.match_count}条匹配</span>` 
            : '';
        
        return `
            <div class="session-item ${isActive ? 'active' : ''}" 
                 onclick="loadSession('${session.session_id}')" 
                 data-session-id="${session.session_id}">
                <div class="session-item-content">
                    <div class="session-item-title">${displayTitle}</div>
                    <div class="session-item-meta">
                        <span class="session-item-time">${time}</span>
                        <span class="session-item-count">
                            <i class="fas fa-message" style="font-size:10px"></i> ${session.message_count || session.match_count || ''}
                        </span>
                        ${matchBadge}
                    </div>
                </div>
                <button class="session-delete-btn" onclick="event.stopPropagation(); deleteSession('${session.session_id}')" title="删除">
                    <i class="fas fa-trash-can"></i>
                </button>
            </div>
        `;
    }).join('');
}

/**
 * 加载某个历史会话的完整对话
 */
async function loadSession(sessionId) {
    try {
        const response = await fetch(`/history/${sessionId}`, {
            headers: getAuthHeaders()
        });
        if (!response.ok) {
            alert('加载对话记录失败');
            return;
        }
        
        const data = await response.json();
        const messages = data.messages || [];
        
        if (messages.length === 0) return;
        
        // 设置当前会话 ID
        currentSessionId = sessionId;
        
        // 从第一条消息推断功能类型
        const firstAssistantMsg = messages.find(m => m.role === 'assistant' && m.query_type);
        if (firstAssistantMsg && firstAssistantMsg.query_type) {
            currentFeature = firstAssistantMsg.query_type;
            const config = FEATURE_CONFIG[currentFeature];
            if (config) {
                chatInput.placeholder = config.placeholder;
                featureLabel.textContent = config.label;
                featureBar.style.display = 'flex';
                // 合同审查显示上传按钮
                const uploadBtn = document.getElementById('upload-btn');
                uploadBtn.style.display = (currentFeature === 'contract_review') ? 'flex' : 'none';
            }
        }
        
        // 切换到对话视图
        showChatArea();
        messageList.innerHTML = '';
        
        // 逐条渲染历史消息
        messages.forEach(msg => {
            if (msg.role === 'user') {
                appendMessage('user', msg.content);
            } else if (msg.role === 'assistant') {
                let sources = null;
                if (msg.sources) {
                    try {
                        sources = JSON.parse(msg.sources);
                    } catch (e) {
                        sources = null;
                    }
                }
                appendMessage('assistant', msg.content, msg.query_type || null, sources);
            }
        });
        
        scrollToBottom();
        
        // 更新侧边栏活跃状态
        document.querySelectorAll('.session-item').forEach(item => {
            item.classList.toggle('active', item.dataset.sessionId === sessionId);
        });
        
    } catch (error) {
        console.error('加载会话失败:', error);
        alert('加载对话记录失败');
    }
}

/**
 * 删除一个历史会话
 */
async function deleteSession(sessionId) {
    if (!confirm('确定要删除这个对话吗？此操作不可恢复。')) return;
    
    try {
        const response = await fetch(`/history/${sessionId}`, { method: 'DELETE', headers: getAuthHeaders() });
        if (!response.ok) {
            alert('删除失败');
            return;
        }
        
        // 如果删除的是当前会话，清空对话区
        if (sessionId === currentSessionId) {
            currentSessionId = null;
            backToWelcome();
        }
        
        // 刷新列表
        loadSessions();
        
    } catch (error) {
        console.error('删除会话失败:', error);
        alert('删除失败');
    }
}

/**
 * 将时间戳转为友好的相对时间显示
 */
function formatRelativeTime(timeStr) {
    if (!timeStr) return '';
    
    const date = new Date(timeStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMin = Math.floor(diffMs / 60000);
    const diffHour = Math.floor(diffMs / 3600000);
    const diffDay = Math.floor(diffMs / 86400000);
    
    if (diffMin < 1) return '刚刚';
    if (diffMin < 60) return `${diffMin} 分钟前`;
    if (diffHour < 24) return `${diffHour} 小时前`;
    if (diffDay < 7) return `${diffDay} 天前`;
    
    // 超过7天显示具体日期
    const month = date.getMonth() + 1;
    const day = date.getDate();
    return `${month}月${day}日`;
}

/**
 * HTML 转义，防止 XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 正则表达式特殊字符转义（用于搜索关键词高亮）
 */
function escapeRegex(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * HTML 转义，防止 XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== 文件上传处理 ====================

/**
 * 为可导出的 AI 回复添加导出按钮（文书生成/合同审查/案例分析）
 */
function addExportButtons(contentDiv, content, queryType) {
    // 功能名映射
    const titleMap = {
        'document_gen': '法律文书',
        'contract_review': '合同审查报告',
        'case_analysis': '案例分析报告'
    };
    const title = titleMap[queryType] || '法律文书';

    const exportBar = document.createElement('div');
    exportBar.className = 'export-bar';
    exportBar.innerHTML = `
        <span class="export-bar-label"><i class="fas fa-download"></i> 一键导出：</span>
        <button class="export-btn export-word" onclick="exportDocument(this, 'word')">
            <i class="fas fa-file-word"></i> 导出 Word
        </button>
        <button class="export-btn export-pdf" onclick="exportDocument(this, 'pdf')">
            <i class="fas fa-file-pdf"></i> 导出 PDF
        </button>
    `;
    // 把内容存在按钮的 data 属性里，点击时读取
    exportBar.dataset.content = content;
    exportBar.dataset.title = title;
    contentDiv.appendChild(exportBar);
}

/**
 * 点击导出按钮，调用后端导出接口下载文件
 */
async function exportDocument(btn, format) {
    // 找到父级 exportBar，读取内容
    const exportBar = btn.closest('.export-bar');
    const content = exportBar.dataset.content;
    const title = exportBar.dataset.title;

    if (!content) {
        alert('导出内容为空，请重新生成。');
        return;
    }

    // 按钮显示加载状态
    const originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> 导出中...`;

    try {
        const response = await fetch('/export/document', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                content: content,
                title: title,
                format: format
            })
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `导出失败（HTTP ${response.status}）`);
        }

        // 下载文件
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        // 从 Content-Disposition 中取文件名，取不到就用默认名
        const disposition = response.headers.get('Content-Disposition');
        let filename = `${title}.${format === 'word' ? 'docx' : 'pdf'}`;
        if (disposition) {
            const match = disposition.match(/filename\*?=(?:UTF-8'')?([^;\s]+)/i);
            if (match) filename = decodeURIComponent(match[1]);
        }
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        btn.innerHTML = `<i class="fas fa-check"></i> 已导出`;
        setTimeout(() => { btn.innerHTML = originalHTML; btn.disabled = false; }, 2000);

    } catch (error) {
        console.error('导出失败：', error);
        btn.innerHTML = `<i class="fas fa-exclamation-triangle"></i> 失败`;
        setTimeout(() => { btn.innerHTML = originalHTML; btn.disabled = false; }, 2000);
    }
}


/**
 * 处理文件选择（点击上传按钮或拖拽后触发）
 */
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    // 检查文件类型
    const allowedTypes = ['.pdf', '.docx', '.txt', '.md'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!allowedTypes.includes(ext)) {
        alert(`不支持的文件类型：${ext}\n\n支持的格式：${allowedTypes.join('、')}`);
        return;
    }

    // 检查文件大小（10MB 限制）
    if (file.size > 10 * 1024 * 1024) {
        alert('文件大小不能超过 10MB');
        return;
    }

    selectedFile = file;
    uploadedFileText = null;  // 重置之前的解析结果

    // 显示文件预览
    const preview = document.getElementById('upload-preview');
    const nameEl = document.getElementById('upload-preview-name');
    const sizeEl = document.getElementById('upload-preview-size');

    nameEl.textContent = file.name;
    sizeEl.textContent = formatFileSize(file.size);
    preview.style.display = 'flex';

    // 更新输入框提示
    chatInput.placeholder = '文件已选择，点击发送开始审查（可输入补充说明）...';
}

/**
 * 移除已选中的文件
 */
function removeFile() {
    selectedFile = null;
    uploadedFileText = null;
    const fileInput = document.getElementById('file-input');
    if (fileInput) fileInput.value = '';
    document.getElementById('upload-preview').style.display = 'none';

    // 恢复默认提示文字
    if (currentFeature === 'contract_review') {
        chatInput.placeholder = FEATURE_CONFIG.contract_review.placeholder;
    }
}

/**
 * 上传文件到后端，返回解析后的文本
 */
async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        // 显示上传中状态
        showProgressMessage('📄 正在上传并解析文件...');

        const response = await fetch('/upload/file', {
            method: 'POST',
            headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {},
            body: formData
        });

        removeProgressMessage();

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `上传失败（HTTP ${response.status}）`);
        }

        const data = await response.json();
        console.log(`✅ 文件解析成功：${data.text_length} 字`);
        return data.text_content;

    } catch (error) {
        removeProgressMessage();
        console.error('文件上传失败：', error);
        appendMessage('assistant', `❌ 文件上传失败：${error.message}`);
        removeFile();  // 清除失败的文件选择
        isLoading = false;
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
        return null;  // 返回 null 表示失败
    }
}

/**
 * 格式化文件大小显示
 */
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ==================== 认证系统 ====================

/** 当前登录 Token */
let authToken = localStorage.getItem('auth_token') || null;
/** 当前登录邮箱 */
let authEmail = localStorage.getItem('auth_email') || null;

/**
 * 获取请求头（带上 JWT Token）
 */
function getAuthHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }
    return headers;
}

/**
 * 检查登录状态，决定显示登录页还是主应用
 */
function checkAuth() {
    const authPage = document.getElementById('auth-page');
    const appContainer = document.getElementById('app-container');

    if (authToken) {
        // 已登录 → 显示主应用
        authPage.style.display = 'none';
        appContainer.style.display = 'flex';
        chatInput.focus();
        loadSessions();
    } else {
        // 未登录 → 显示登录页
        authPage.style.display = 'flex';
        appContainer.style.display = 'none';
    }
}

/**
 * 切换登录/注册/忘记密码视图
 */
function switchAuthView(view) {
    // 隐藏所有表单
    document.getElementById('auth-login').style.display = 'none';
    document.getElementById('auth-register').style.display = 'none';
    document.getElementById('auth-forgot').style.display = 'none';

    // 清除所有错误/成功提示
    document.querySelectorAll('.auth-error, .auth-success').forEach(el => {
        el.style.display = 'none';
        el.textContent = '';
    });

    // 显示目标表单
    document.getElementById(`auth-${view}`).style.display = 'block';
}

/**
 * 显示错误提示
 */
function showAuthError(elementId, message) {
    const el = document.getElementById(elementId);
    el.textContent = message;
    el.style.display = 'block';
}

/**
 * 显示成功提示
 */
function showAuthSuccess(elementId, message) {
    const el = document.getElementById(elementId);
    el.textContent = message;
    el.style.display = 'block';
}

/**
 * 发送验证码（注册 或 重置密码）
 */
async function sendCode(purpose) {
    const emailInput = purpose === 'register'
        ? document.getElementById('register-email')
        : document.getElementById('forgot-email');
    const email = emailInput.value.trim();

    if (!email) {
        const errorId = purpose === 'register' ? 'register-error' : 'forgot-error';
        showAuthError(errorId, '请输入邮箱地址');
        return;
    }

    // 邮箱格式简单校验
    if (!email.includes('@') || !email.includes('.')) {
        const errorId = purpose === 'register' ? 'register-error' : 'forgot-error';
        showAuthError(errorId, '请输入有效的邮箱地址');
        return;
    }

    const btnId = purpose === 'register' ? 'register-send-code-btn' : 'forgot-send-code-btn';
    const btn = document.getElementById(btnId);
    const errorId = purpose === 'register' ? 'register-error' : 'forgot-error';

    try {
        btn.disabled = true;
        btn.textContent = '发送中...';

        const response = await fetch('/auth/send-code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, purpose })
        });

        // 安全解析 JSON（后端 500 时返回纯文本，不能直接 .json()）
        let data;
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            data = await response.json();
        }
        if (!response.ok) {
            throw new Error((data && data.detail) || `服务器错误（${response.status}），请查看后端控制台`);
        }

        // 启动倒计时
        startCountdown(btn);

    } catch (error) {
        showAuthError(errorId, error.message);
        btn.disabled = false;
        btn.textContent = '获取验证码';
    }
}

/**
 * 验证码按钮倒计时（60秒）
 */
function startCountdown(btn) {
    let seconds = 60;
    btn.disabled = true;
    btn.textContent = `${seconds}s`;

    const timer = setInterval(() => {
        seconds--;
        btn.textContent = `${seconds}s`;
        if (seconds <= 0) {
            clearInterval(timer);
            btn.disabled = false;
            btn.textContent = '获取验证码';
        }
    }, 1000);
}

/**
 * 处理登录
 */
async function handleLogin() {
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;

    if (!email || !password) {
        showAuthError('login-error', '请输入邮箱和密码');
        return;
    }

    try {
        const response = await fetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        let data;
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            data = await response.json();
        }
        if (!response.ok) {
            throw new Error((data && data.detail) || `服务器错误（${response.status}），请查看后端控制台`);
        }

        // 保存 Token
        authToken = data.access_token;
        authEmail = data.email;
        localStorage.setItem('auth_token', authToken);
        localStorage.setItem('auth_email', authEmail);

        // 切换到主应用
        checkAuth();

    } catch (error) {
        showAuthError('login-error', error.message);
    }
}

/**
 * 处理注册
 */
async function handleRegister() {
    const email = document.getElementById('register-email').value.trim();
    const password = document.getElementById('register-password').value;
    const code = document.getElementById('register-code').value.trim();

    if (!email || !password || !code) {
        showAuthError('register-error', '请填写所有字段');
        return;
    }

    if (password.length < 6) {
        showAuthError('register-error', '密码长度不能少于6位');
        return;
    }

    try {
        const response = await fetch('/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password, code })
        });

        let data;
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            data = await response.json();
        }
        if (!response.ok) {
            throw new Error((data && data.detail) || `服务器错误（${response.status}），请查看后端控制台`);
        }

        // 注册成功
        showAuthSuccess('register-success', '注册成功！3秒后跳转到登录页...');
        document.getElementById('register-error').style.display = 'none';

        // 3秒后跳转到登录页
        setTimeout(() => {
            switchAuthView('login');
            // 自动填入邮箱
            document.getElementById('login-email').value = email;
            document.getElementById('login-password').focus();
        }, 3000);

    } catch (error) {
        showAuthError('register-error', error.message);
    }
}

/**
 * 处理重置密码
 */
async function handleResetPassword() {
    const email = document.getElementById('forgot-email').value.trim();
    const code = document.getElementById('forgot-code').value.trim();
    const newPassword = document.getElementById('forgot-new-password').value;

    if (!email || !code || !newPassword) {
        showAuthError('forgot-error', '请填写所有字段');
        return;
    }

    if (newPassword.length < 6) {
        showAuthError('forgot-error', '密码长度不能少于6位');
        return;
    }

    try {
        const response = await fetch('/auth/reset-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, code, new_password: newPassword })
        });

        let data;
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            data = await response.json();
        }
        if (!response.ok) {
            throw new Error((data && data.detail) || `服务器错误（${response.status}），请查看后端控制台`);
        }

        // 重置成功
        showAuthSuccess('forgot-success', '密码重置成功！3秒后跳转到登录页...');
        document.getElementById('forgot-error').style.display = 'none';

        // 3秒后跳转到登录页
        setTimeout(() => {
            switchAuthView('login');
            document.getElementById('login-email').value = email;
            document.getElementById('login-password').focus();
        }, 3000);

    } catch (error) {
        showAuthError('forgot-error', error.message);
    }
}

/**
 * 退出登录
 */
function handleLogout() {
    if (!confirm('确定要退出登录吗？')) return;

    authToken = null;
    authEmail = null;
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_email');

    // 清空聊天状态
    currentSessionId = null;
    currentFeature = null;
    messageList.innerHTML = '';
    chatInput.value = '';

    // 切换回登录页
    checkAuth();
}
