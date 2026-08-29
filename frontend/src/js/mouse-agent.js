/**
 * 小老鼠 AI 助手 - Web Component
 * 完全自包含，融入任何页面只需：
 *   <link rel="stylesheet" href="src/styles/mouse-agent.css">
 *   <script src="src/js/mouse-agent.js"></script>
 *   <mouse-assistant></mouse-assistant>
 */
class MouseAssistant extends HTMLElement {
  constructor() {
    super();
    this._chatOpen = false;
    this._notifOpen = false;
    this._surfing = false;
    this._status = "idle";
    this._action = "待命中...";
    this._screen = "🖥️ 准备就绪，点击我聊天～";
    this._notifications = [];
    this._pollTimer = null;
    this._dragging = false;
    this._didDrag = false;
    this._expanded = false;
    this._chatHistory = [];
    this._spaceId = this.getSpaceId();
    this._sessionId = this.getSessionId(this._spaceId);
    this._spaces = [];
    this._spaceSessions = [];
  }

  connectedCallback() {
    this.render();
    this.loadChatHistory();
    this.loadSpaceData();
    this.bindEvents();
    this.startPolling();
    // 启动定时任务
    fetch("/api/agent/timer-start").catch(() => {});
    // 首次深度冲浪（页面加载后 5 秒）
    setTimeout(() => this.triggerSurf(), 5000);
  }

  disconnectedCallback() {
    if (this._pollTimer) clearInterval(this._pollTimer);
  }

  render() {
    this.innerHTML = `
      <div class="ma-wrapper">
        <div class="ma-notif-panel" id="ma-notif-panel">
          <div class="ma-notif-header">
            <span>🔔 小老鼠提醒</span>
            <div class="ma-notif-header-btns">
              <button class="ma-notif-clear" id="ma-notif-clear">清空</button>
              <button class="ma-notif-close" id="ma-notif-close">✕</button>
            </div>
          </div>
          <div class="ma-notif-list" id="ma-notif-list"></div>
        </div>

        <div class="ma-character idle" id="ma-character">
          <div class="ma-bubble" id="ma-bubble" style="display:none;">0</div>

          <div class="ma-screen" id="ma-screen">
            <div class="ma-screen-content" id="ma-screen-content">${this._screen}</div>
          </div>

          <div class="ma-pet" id="ma-pet"></div>
        </div>

        <div class="ma-chat-overlay" id="ma-chat-overlay"></div>
        <div class="ma-delete-confirm" id="ma-delete-confirm" style="display:none;">
          <div class="ma-delete-confirm-card">
            <div class="ma-delete-confirm-title" id="ma-delete-confirm-title">删除这段对话？</div>
            <div class="ma-delete-confirm-text" id="ma-delete-confirm-text">聊天记录会被删除；当前空间的长期记忆不会受影响。</div>
            <label class="ma-delete-confirm-check"><input type="checkbox" id="ma-delete-no-remind"> 本次登录不再提醒</label>
            <div class="ma-delete-confirm-actions">
              <button id="ma-delete-cancel">取消</button><button id="ma-delete-ok">删除</button>
            </div>
          </div>
        </div>
        <div class="ma-rename-space-dialog" id="ma-rename-space-dialog" style="display:none;">
          <div class="ma-rename-space-card">
            <div class="ma-delete-confirm-title">重命名记忆空间</div>
            <input id="ma-rename-space-input" maxlength="80" placeholder="输入空间名称">
            <div class="ma-delete-confirm-actions">
              <button id="ma-rename-space-cancel">取消</button><button id="ma-rename-space-ok">保存</button>
            </div>
          </div>
        </div>
        <div class="ma-chat-box" id="ma-chat-box">
          <div class="ma-resize-handle" id="ma-resize-handle" title="拖动调整宽度"></div>
          <div class="ma-chat-header">
            <span>🐭 小老鼠助手</span>
            <div class="ma-chat-header-btns">
              <button class="ma-chat-spaces" id="ma-chat-spaces" title="记忆空间与对话">📁</button>
              <button class="ma-chat-expand" id="ma-chat-expand" title="展开/收起">⤢</button>
              <button class="ma-chat-close" id="ma-chat-close">✕</button>
            </div>
          </div>
          <div class="ma-space-panel" id="ma-space-panel"></div>
          <div class="ma-chat-msgs" id="ma-chat-msgs">
            <div class="ma-msg them">
              <div class="ma-msg-label">🐭 小老鼠</div>
              你好！我是小老鼠 🐭 我每分钟都在后台忙碌着～<br>• 📅 监测宏观风险<br>• 📡 扫描股吧信息<br>• 🔬 鉴别消息真伪<br>• 📊 浏览你的自选股<br><br>点击我可以和我聊天哦！
            </div>
          </div>
          <div class="ma-chat-input-area">
            <input class="ma-chat-input" id="ma-chat-input" placeholder="问小老鼠问题..." maxlength="200">
            <button class="ma-chat-send" id="ma-chat-send">➤</button>
          </div>
        </div>
      </div>
    `;
  }

  $(id) { return this.querySelector(id); }

  agentFetch(url, options = {}) {
    const authHeaders = typeof getAuthHeaders === "function" ? getAuthHeaders() : {};
    return fetch(url, { ...options, headers: { ...authHeaders, ...(options.headers || {}) } });
  }

  getSpaceId() {
    try { return localStorage.getItem("riskmouse_agent_space_id") || ""; }
    catch (e) { return ""; }
  }

  getSessionId(spaceId) {
    if (!spaceId) return "";
    const key = "riskmouse_agent_sessions";
    try {
      const sessions = JSON.parse(localStorage.getItem(key) || "{}");
      let value = sessions[spaceId];
      if (!value) {
        value = window.crypto?.randomUUID?.() || `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      }
      sessions[spaceId] = value;
      localStorage.setItem(key, JSON.stringify(sessions));
      return value;
    } catch (e) {
      return "";
    }
  }

  async loadSpaceData() {
    try {
      const response = await this.agentFetch("/api/agent/spaces");
      const data = await response.json();
      this._spaces = data.spaces || [];
      if (this._spaces.length && !this._spaces.some(space => space.space_id === this._spaceId)) {
        this._spaceId = this._spaces[0].space_id;
        this._sessionId = this.getSessionId(this._spaceId);
      }
      await this.loadSpaceSessions();
      this.renderSpacePanel();
    } catch (error) {
      console.warn("无法加载记忆空间", error);
    }
  }

  async loadSpaceSessions() {
    if (!this._spaceId) {
      this._spaceSessions = [];
      return;
    }
    try {
      const response = await this.agentFetch(`/api/agent/spaces/${encodeURIComponent(this._spaceId)}/sessions`);
      const data = await response.json();
      this._spaceSessions = data.sessions || [];
    } catch (error) {
      this._spaceSessions = [];
    }
  }

  toggleSpacePanel() {
    const panel = this.$("#ma-space-panel");
    const isOpen = panel.classList.toggle("open");
    this.$("#ma-chat-spaces").classList.toggle("active", isOpen);
    if (panel.classList.contains("open")) this.loadSpaceData();
  }

  renderSpacePanel() {
    const panel = this.$("#ma-space-panel");
    if (!panel) return;
    const currentSpace = this._spaces.find(space => space.space_id === this._spaceId);
    const spaceButtons = this._spaces.map(space => `
      <div class="ma-space-row ${space.space_id === this._spaceId ? "active" : ""}">
        <button class="ma-space-item ${space.space_id === this._spaceId ? "active" : ""}" data-space-id="${this.escapeHtml(space.space_id)}">
          📁 ${this.escapeHtml(space.name)} <small>${space.session_count || 0}</small>
        </button>
        <button class="ma-space-rename" data-rename-space="${this.escapeHtml(space.space_id)}" title="重命名空间">✎</button>
        <button class="ma-space-delete" data-delete-space="${this.escapeHtml(space.space_id)}" title="删除空间">✕</button>
      </div>`).join("") || '<div class="ma-space-empty">暂无空间</div>';
    const sessions = this._spaceSessions.map(session => `
      <div class="ma-session-row ${session.session_id === this._sessionId ? "active" : ""}">
        <button class="ma-session-item ${session.session_id === this._sessionId ? "active" : ""}" data-session-id="${this.escapeHtml(session.session_id)}">
          💬 ${this.escapeHtml(session.title || "新对话")}
        </button>
        <button class="ma-session-delete" data-delete-session="${this.escapeHtml(session.session_id)}" title="删除这段对话">✕</button>
      </div>`).join("") || '<div class="ma-space-empty">这个空间还没有对话</div>';
    panel.innerHTML = `
      <div class="ma-space-title">记忆空间 <button id="ma-space-create">＋ 新空间</button></div>
      <div class="ma-space-list">${spaceButtons}</div>
      <div class="ma-session-title">${this.escapeHtml(currentSpace?.name || "未选择空间")} · 对话 ${currentSpace ? '<button id="ma-session-create">＋ 新对话</button>' : ''}</div>
      <div class="ma-session-list">${sessions}</div>`;
    panel.querySelectorAll("[data-space-id]").forEach(button => {
      button.addEventListener("click", () => this.selectSpace(button.dataset.spaceId));
    });
    panel.querySelectorAll("[data-rename-space]").forEach(button => {
      button.addEventListener("click", () => this.renameSpace(button.dataset.renameSpace));
    });
    panel.querySelectorAll("[data-delete-space]").forEach(button => {
      button.addEventListener("click", () => this.deleteSpace(button.dataset.deleteSpace));
    });
    panel.querySelectorAll("[data-session-id]").forEach(button => {
      button.addEventListener("click", () => this.selectConversation(button.dataset.sessionId));
    });
    panel.querySelectorAll("[data-delete-session]").forEach(button => {
      button.addEventListener("click", () => this.deleteConversation(button.dataset.deleteSession));
    });
    panel.querySelector("#ma-space-create")?.addEventListener("click", () => this.createSpace());
    panel.querySelector("#ma-session-create")?.addEventListener("click", () => this.createConversation());
  }

  async createSpace() {
    const response = await this.agentFetch("/api/agent/spaces", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}),
    });
    const data = await response.json();
    if (!response.ok || !data.space) return alert(data.message || "创建空间失败");
    await this.loadSpaceData();
    await this.selectSpace(data.space.space_id, true);
  }

  async renameSpace(spaceId) {
    const space = this._spaces.find(item => item.space_id === spaceId);
    const name = await this.promptRenameSpace(space?.name || "");
    if (name === null || !name.trim()) return;
    const response = await this.agentFetch(`/api/agent/spaces/${encodeURIComponent(spaceId)}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
    });
    const data = await response.json();
    if (!response.ok || !data.space) return alert(data.message || "重命名失败");
    await this.loadSpaceData();
  }

  async deleteSpace(spaceId) {
    const space = this._spaces.find(item => item.space_id === spaceId);
    const message = `删除“${space?.name || "这个空间"}”？该空间内的全部对话和长期记忆都会被删除，无法恢复。`;
    if (!await this.confirmDeletion("删除记忆空间？", message)) return;
    const response = await this.agentFetch(`/api/agent/spaces/${encodeURIComponent(spaceId)}`, { method: "DELETE" });
    const data = await response.json();
    if (!response.ok || !data.ok) return alert(data.message || "删除空间失败");
    await this.loadSpaceData();
    if (this._spaceId === spaceId) {
      if (this._spaces.length) await this.selectSpace(this._spaces[0].space_id);
      else {
        this._spaceId = "";
        this._sessionId = "";
        try { localStorage.removeItem("riskmouse_agent_space_id"); } catch (e) {}
        this.clearChatView();
        this.renderSpacePanel();
      }
    }
  }

  promptRenameSpace(currentName) {
    return new Promise(resolve => {
      const dialog = this.$("#ma-rename-space-dialog");
      const input = this.$("#ma-rename-space-input");
      const finish = value => { dialog.style.display = "none"; resolve(value); };
      input.value = currentName;
      dialog.style.display = "flex";
      input.focus();
      input.select();
      this.$("#ma-rename-space-cancel").onclick = () => finish(null);
      this.$("#ma-rename-space-ok").onclick = () => finish(input.value.trim());
      input.onkeydown = event => {
        if (event.key === "Enter") finish(input.value.trim());
        if (event.key === "Escape") finish(null);
      };
    });
  }

  async selectSpace(spaceId, createNew = false) {
    this._spaceId = spaceId;
    try { localStorage.setItem("riskmouse_agent_space_id", spaceId); } catch (e) {}
    this._sessionId = this.getSessionId(spaceId);
    if (createNew) await this.createConversation();
    else {
      await this.loadSpaceSessions();
      const latest = this._spaceSessions[0];
      if (latest) this._sessionId = latest.session_id;
      this.clearChatView();
      await this.loadChatHistory();
      this.renderSpacePanel();
    }
  }

  async createConversation() {
    if (!this._spaces.some(space => space.space_id === this._spaceId)) {
      return;
    }
    try {
      const response = await this.agentFetch(`/api/agent/spaces/${encodeURIComponent(this._spaceId)}/sessions`, { method: "POST" });
      const data = await response.json();
      if (!response.ok || !data.session) throw new Error(data.message || "创建对话失败");
      this._sessionId = data.session.session_id;
      const sessions = JSON.parse(localStorage.getItem("riskmouse_agent_sessions") || "{}");
      sessions[this._spaceId] = this._sessionId;
      localStorage.setItem("riskmouse_agent_sessions", JSON.stringify(sessions));
      this.clearChatView();
      await this.loadSpaceData();
    } catch (error) {
      alert(error.message || "创建对话失败");
    }
  }

  async selectConversation(sessionId) {
    this._sessionId = sessionId;
    try {
      const sessions = JSON.parse(localStorage.getItem("riskmouse_agent_sessions") || "{}");
      sessions[this._spaceId] = sessionId;
      localStorage.setItem("riskmouse_agent_sessions", JSON.stringify(sessions));
    } catch (e) {}
    this.clearChatView();
    await this.loadChatHistory();
    this.renderSpacePanel();
  }

  async deleteConversation(sessionId) {
    if (!await this.confirmDeleteConversation()) return;
    try {
      const response = await this.agentFetch(`/api/agent/spaces/${encodeURIComponent(this._spaceId)}/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || "删除失败");
      await this.loadSpaceSessions();
      if (this._sessionId === sessionId) {
        if (this._spaceSessions[0]) await this.selectConversation(this._spaceSessions[0].session_id);
        else await this.createConversation();
      } else {
        this.renderSpacePanel();
      }
    } catch (error) {
      alert(error.message || "删除对话失败");
    }
  }

  confirmDeleteConversation() {
    return this.confirmDeletion("删除这段对话？", "聊天记录会被删除；当前空间的长期记忆不会受影响。");
  }

  confirmDeletion(title, text) {
    try {
      // sessionStorage 仅在本次浏览器登录期间有效；关闭浏览器后会自动恢复提醒。
      if (sessionStorage.getItem("riskmouse_skip_delete_confirm") === "true") return Promise.resolve(true);
    } catch (e) {}
    return new Promise(resolve => {
      const modal = this.$("#ma-delete-confirm");
      const checkbox = this.$("#ma-delete-no-remind");
      this.$("#ma-delete-confirm-title").textContent = title;
      this.$("#ma-delete-confirm-text").textContent = text;
      const finish = approved => {
        modal.style.display = "none";
        if (approved && checkbox.checked) {
          try { sessionStorage.setItem("riskmouse_skip_delete_confirm", "true"); } catch (e) {}
        }
        resolve(approved);
      };
      checkbox.checked = false;
      modal.style.display = "flex";
      this.$("#ma-delete-cancel").onclick = () => finish(false);
      this.$("#ma-delete-ok").onclick = () => finish(true);
    });
  }

  clearChatView() {
    const msgs = this.$("#ma-chat-msgs");
    if (msgs) msgs.innerHTML = '<div class="ma-msg them"><div class="ma-msg-label">🐭 小老鼠</div>这是一个新对话。当前空间的记忆会保留，其他空间的记忆不会带入。</div>';
  }

  bindEvents() {
    this.$("#ma-character").addEventListener("click", (e) => {
      if (this._didDrag) { this._didDrag = false; return; }
      if (e.target.closest(".ma-bubble")) {
        this.toggleNotifPanel();
        return;
      }
      this.openChat();
    });

    this.$("#ma-chat-close").addEventListener("click", () => this.closeChat());
    this.$("#ma-chat-spaces").addEventListener("click", () => this.toggleSpacePanel());
    this.$("#ma-chat-expand").addEventListener("click", () => this.toggleExpand());
    this.$("#ma-chat-overlay").addEventListener("click", () => this.closeChat());
    this.$("#ma-chat-send").addEventListener("click", () => this.sendChat());
    this.$("#ma-chat-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") this.sendChat();
    });
    this.bindResize();
    this.$("#ma-notif-clear").addEventListener("click", () => {
      fetch("/api/agent/notifications/clear", { method: "POST" });
      this._notifications = [];
      this._notifOpen = false;
      const panel = this.$("#ma-notif-panel");
      if (panel) {
        panel.classList.remove("open");
        panel.style.display = "none";
      }
      this.updateNotifPanel();
      this.updateBubble();
    });
    this.$("#ma-notif-close").addEventListener("click", () => this.closeNotifPanel());

    this.bindDrag();
  }

  bindDrag() {
    const wrapper = this.querySelector(".ma-wrapper");
    const handle = this.$("#ma-character");
    let startX, startY, startLeft, startTop;

    const onMouseMove = (e) => {
      if (!this._dragging) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) this._didDrag = true;
      const newLeft = Math.max(0, Math.min(window.innerWidth  - wrapper.offsetWidth,  startLeft + dx));
      const newTop  = Math.max(0, Math.min(window.innerHeight - wrapper.offsetHeight, startTop  + dy));
      wrapper.style.left = newLeft + "px";
      wrapper.style.top  = newTop  + "px";
    };

    const onMouseUp = () => {
      if (!this._dragging) return;
      this._dragging = false;
      wrapper.classList.remove("dragging");
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };

    handle.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      this._dragging = true;
      this._didDrag  = false;
      wrapper.classList.add("dragging");

      const rect = wrapper.getBoundingClientRect();
      startLeft = rect.left;
      startTop  = rect.top;
      wrapper.style.left   = startLeft + "px";
      wrapper.style.top    = startTop  + "px";
      wrapper.style.right  = "auto";
      wrapper.style.bottom = "auto";
      startX = e.clientX;
      startY = e.clientY;

      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup",   onMouseUp);
    });
  }

  // ── 屏幕更新（支持多行） ──────────────────────────────────

  updateScreen(text) {
    this._screen = text;
    const el = this.$("#ma-screen-content");
    if (!el) return;
    // 多行文本用 <br> 渲染，模拟终端
    el.innerHTML = text.split("\n").map(line => {
      const escaped = line.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      return escaped || "&nbsp;";
    }).join("<br>");
    el.scrollTop = el.scrollHeight;
  }

  updateBubble() {
    const bubble = this.$("#ma-bubble");
    if (!bubble) return;
    const unread = this._notifications.length;
    if (unread > 0) {
      bubble.style.display = "flex";
      bubble.textContent = unread > 99 ? "99+" : unread;
    } else {
      bubble.style.display = "none";
    }
  }

  updateNotifPanel() {
    const list = this.$("#ma-notif-list");
    if (!list) return;
    if (this._notifications.length === 0) {
      list.innerHTML = '<div style="padding:20px;text-align:center;color:#999;font-size:12px;">暂无提醒</div>';
      return;
    }
    list.innerHTML = this._notifications.slice().reverse().map(n => `
      <div class="ma-notif-item ${n.level || 'info'}">
        <div class="ma-notif-title">${n.title}</div>
        <div class="ma-notif-content">${n.content}</div>
        <div class="ma-notif-time">${n.time || ''}</div>
      </div>
    `).join("");
  }

  setSurfingState(surfing) {
    this._surfing = surfing;
    const ch = this.$("#ma-character");
    if (!ch) return;
    ch.classList.toggle("surfing", surfing);
    ch.classList.toggle("idle", !surfing);
  }

  setPetState(state) {
    const ch = this.$("#ma-character");
    if (!ch) return;
    ch.classList.remove("idle", "surfing", "thinking", "alert");
    ch.classList.add(state);
  }

  // ── 网上冲浪 ──────────────────────────────────────────────

  async triggerSurf() {
    if (this._surfing) return;
    this.setSurfingState(true);
    this.updateScreen("🌊 小老鼠开始网上冲浪...\n📡 扫描宏观数据和股吧中...");

    try {
      const resp = await fetch("/api/agent/surf", { method: "POST" });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "巡检启动失败");
      if (data.run_id) {
        await this.waitForSurfWorkflow(data.run_id);
      }
    } catch (err) {
      console.error("RiskMouse patrol failed", err);
      this.updateScreen(`⚠️ 巡检失败：${err.message || "未知错误"}`);
    }
    this.setSurfingState(false);
  }

  bindResize() {
    const handle = this.$("#ma-resize-handle");
    const box = this.$("#ma-chat-box");
    if (!handle || !box) return;
    handle.addEventListener("pointerdown", event => {
      if (!this._expanded) return;
      event.preventDefault();
      handle.setPointerCapture?.(event.pointerId);
      const resize = moveEvent => {
        const minWidth = 320;
        const maxWidth = Math.min(920, window.innerWidth - 80);
        const width = Math.max(minWidth, Math.min(maxWidth, window.innerWidth - moveEvent.clientX));
        box.style.width = `${width}px`;
        try { localStorage.setItem("riskmouse_expanded_chat_width", String(Math.round(width))); } catch (e) {}
      };
      const stop = () => {
        document.removeEventListener("pointermove", resize);
        document.removeEventListener("pointerup", stop);
      };
      document.addEventListener("pointermove", resize);
      document.addEventListener("pointerup", stop);
    });
  }

  async waitForSurfWorkflow(runId) {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      await new Promise(resolve => setTimeout(resolve, 1500));
      const response = await fetch(`/api/agent/runs/${runId}`);
      const run = await response.json();
      if (!response.ok) throw new Error(run.detail || "无法获取巡检状态");
      const task = run.tasks?.patrol;
      this.updateScreen(`🌊 全局巡检 ${task?.status || run.status}\n${task?.duration_ms ? `耗时 ${task.duration_ms}ms` : "正在执行…"}`);
      if (["succeeded", "partial", "failed"].includes(run.status)) {
        const status = await fetch("/api/agent/status").then(r => r.json());
        if (status.screen) this.updateScreen(status.screen);
        return;
      }
    }
    throw new Error("巡检等待超时");
  }

  // ── 轮询 ──────────────────────────────────────────────────

  startPolling() {
    this._pollTimer = setInterval(() => {
      fetch("/api/agent/status")
        .then(r => r.json())
        .then(data => {
          if (data.notifications) {
            data.notifications.forEach(n => {
              if (!this._notifications.find(x => x.id === n.id)) {
                this._notifications.push(n);
              }
            });
            this.updateNotifPanel();
            this.updateBubble();
          }
          if (data.screen && !this._surfing) {
            this.updateScreen(data.screen);
          }
          this._action = data.action || "";
          this._status = data.status || "idle";
          if (!this._surfing) {
            this.setPetState(data.status === "surfing" ? "surfing" : "idle");
          }
        })
        .catch(() => {});
    }, 3000); // 3秒轮询，更实时
  }

  toggleNotifPanel() {
    this._notifOpen = !this._notifOpen;
    const panel = this.$("#ma-notif-panel");
    if (!panel) return;
    if (this._notifOpen) {
      panel.classList.add("open");
      panel.style.display = "";
    } else {
      panel.classList.remove("open");
      panel.style.display = "none";
    }
  }

  closeNotifPanel() {
    this._notifOpen = false;
    const panel = this.$("#ma-notif-panel");
    if (!panel) return;
    panel.classList.remove("open");
    panel.style.display = "none";
  }

  // ── 聊天 ──────────────────────────────────────────────────

  openChat() {
    this._chatOpen = true;
    this.$("#ma-chat-box").classList.add("open");
    if (!this._expanded) {
      this.$("#ma-chat-overlay").classList.add("open");
    }
    this.$("#ma-chat-input").focus();
  }

  closeChat() {
    this._chatOpen = false;
    this._expanded = false;
    this.$("#ma-chat-box").classList.remove("open", "expanded");
    this.$("#ma-chat-box").style.width = "";
    this.$("#ma-chat-overlay").classList.remove("open");
    this.$("#ma-space-panel").classList.remove("open");
    this.$("#ma-chat-spaces").classList.remove("active");
    this.$("#ma-chat-expand").textContent = "⤢";
  }

  toggleExpand() {
    this._expanded = !this._expanded;
    const box = this.$("#ma-chat-box");
    const overlay = this.$("#ma-chat-overlay");
    const btn = this.$("#ma-chat-expand");
    if (this._expanded) {
      try {
        const savedWidth = Number(localStorage.getItem("riskmouse_expanded_chat_width"));
        box.style.width = savedWidth >= 320 ? `${savedWidth}px` : "";
      } catch (e) {}
      box.classList.add("expanded");
      overlay.classList.remove("open");
      btn.textContent = "⤡";
    } else {
      box.classList.remove("expanded");
      box.style.width = "";
      overlay.classList.add("open");
      btn.textContent = "⤢";
    }
  }

  async sendChat() {
    const input = this.$("#ma-chat-input");
    const msgs = this.$("#ma-chat-msgs");
    const q = input.value.trim();
    if (!q) return;
    if (!this._spaces.some(space => space.space_id === this._spaceId)) {
      input.value = "";
      msgs.innerHTML += '<div class="ma-msg them"><div class="ma-msg-label">🐭 小老鼠</div>请先在 📁 中创建一个记忆空间，再开始对话。</div>';
      msgs.scrollTop = msgs.scrollHeight;
      return;
    }

    input.value = "";
    const sendBtn = this.$("#ma-chat-send");
    sendBtn.disabled = true;

    msgs.innerHTML += `<div class="ma-msg me"><div class="ma-msg-label">你</div>${this.escapeHtml(q)}</div>`;
    msgs.scrollTop = msgs.scrollHeight;
    msgs.innerHTML += `<div class="ma-msg them" id="ma-thinking"><div class="ma-msg-label">🐭 小老鼠</div>思考中...</div>`;

    try {
      const resp = await this.agentFetch("/api/agent/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, session_id: this._sessionId, space_id: this._spaceId }),
      });
      if (!resp.ok) {
        throw new Error(`服务返回 HTTP ${resp.status}`);
      }
      const data = await resp.json();
      const thinking = this.$("#ma-thinking");
      if (thinking) thinking.remove();
      msgs.innerHTML += `<div class="ma-msg them"><div class="ma-msg-label">🐭 小老鼠</div>${this.escapeHtml(data.reply || "嗯...让我想想")}</div>`;
      this.saveChatHistory();
    } catch (err) {
      console.error("RiskMouse chat failed", err);
      const thinking = this.$("#ma-thinking");
      if (thinking) thinking.remove();
      msgs.innerHTML += `<div class="ma-msg them"><div class="ma-msg-label">🐭 小老鼠</div>连接失败：${this.escapeHtml(err.message || "未知错误")}。请确认本地服务正在运行。</div>`;
      this.saveChatHistory();
    }
    msgs.scrollTop = msgs.scrollHeight;
    sendBtn.disabled = false;
    // 首条消息写入后立即刷新侧栏，让“新对话”同步变成自动提取的主题。
    this.loadSpaceSessions().then(() => this.renderSpacePanel());
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, "<br>");
  }

  // ── 对话历史：按当前会话隔离，服务端是权威来源 ─────────────

  saveChatHistory() {
    const msgs = this.$("#ma-chat-msgs");
    if (!msgs) return;
    const items = msgs.querySelectorAll(".ma-msg");
    const history = [];
    items.forEach(el => {
      const label = el.querySelector(".ma-msg-label");
      const textEl = el.cloneNode(true);
      const labelEl = textEl.querySelector(".ma-msg-label");
      if (labelEl) labelEl.remove();
      const text = textEl.textContent.trim();
      if (text) {
        history.push({
          role: label && label.textContent.includes("你") ? "user" : "bot",
          text: text,
        });
      }
    });
    // 保留最近 60 条（30 轮对话）
    if (history.length > 60) {
      history.splice(0, history.length - 60);
    }
    try {
      localStorage.setItem(`mouse_chat_history_${this._sessionId}`, JSON.stringify(history));
    } catch (e) {}
  }

  async loadChatHistory() {
    // 未登录时不加载任何本地回退记录，避免退出账号后仍展示上一位用户的对话。
    if (!this._sessionId || !localStorage.getItem("token")) return;
    let history = [];
    try {
      const response = await this.agentFetch(`/api/agent/memory/session/${encodeURIComponent(this._sessionId)}`);
      const data = await response.json();
      if (response.ok && data.messages?.length) {
        history = data.messages.map(item => ({ role: item.role === "user" ? "user" : "bot", text: item.content }));
      } else {
        const raw = localStorage.getItem(`mouse_chat_history_${this._sessionId}`);
        if (raw) history = JSON.parse(raw);
      }
    } catch (e) {}
    const msgs = this.$("#ma-chat-msgs");
    if (!msgs || history.length === 0) return;
    // 清空默认欢迎语，替换为历史记录
    msgs.innerHTML = history.map(item => `
      <div class="ma-msg ${item.role === 'user' ? 'me' : 'them'}">
        <div class="ma-msg-label">${item.role === 'user' ? '你' : '🐭 小老鼠'}</div>
        ${item.text}
      </div>
    `).join("");
    msgs.scrollTop = msgs.scrollHeight;
  }
}

customElements.define("mouse-assistant", MouseAssistant);
