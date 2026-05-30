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
  }

  connectedCallback() {
    this.render();
    this.loadChatHistory();
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
        <div class="ma-chat-box" id="ma-chat-box">
          <div class="ma-chat-header">
            <span>🐭 小老鼠助手</span>
            <div class="ma-chat-header-btns">
              <button class="ma-chat-expand" id="ma-chat-expand" title="展开/收起">⤢</button>
              <button class="ma-chat-close" id="ma-chat-close">✕</button>
            </div>
          </div>
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
    this.$("#ma-chat-expand").addEventListener("click", () => this.toggleExpand());
    this.$("#ma-chat-overlay").addEventListener("click", () => this.closeChat());
    this.$("#ma-chat-send").addEventListener("click", () => this.sendChat());
    this.$("#ma-chat-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") this.sendChat();
    });
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
      const resp = await fetch("/api/agent/surf-sync");
      const data = await resp.json();
      if (data.screen) this.updateScreen(data.screen);
      this._action = data.action || "";
      if (data.notifications) {
        data.notifications.forEach(n => {
          if (!this._notifications.find(x => x.id === n.id)) {
            this._notifications.push(n);
          }
        });
        this.updateNotifPanel();
        this.updateBubble();
      }
    } catch (err) {
      this.updateScreen("⚠️ 冲浪遇到一点小问题\n下次再试试～");
    }
    this.setSurfingState(false);
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
    this.$("#ma-chat-overlay").classList.remove("open");
    this.$("#ma-chat-expand").textContent = "⤢";
  }

  toggleExpand() {
    this._expanded = !this._expanded;
    const box = this.$("#ma-chat-box");
    const overlay = this.$("#ma-chat-overlay");
    const btn = this.$("#ma-chat-expand");
    if (this._expanded) {
      box.classList.add("expanded");
      overlay.classList.remove("open");
      btn.textContent = "⤡";
    } else {
      box.classList.remove("expanded");
      overlay.classList.add("open");
      btn.textContent = "⤢";
    }
  }

  async sendChat() {
    const input = this.$("#ma-chat-input");
    const msgs = this.$("#ma-chat-msgs");
    const q = input.value.trim();
    if (!q) return;

    input.value = "";
    const sendBtn = this.$("#ma-chat-send");
    sendBtn.disabled = true;

    msgs.innerHTML += `<div class="ma-msg me"><div class="ma-msg-label">你</div>${this.escapeHtml(q)}</div>`;
    msgs.scrollTop = msgs.scrollHeight;
    msgs.innerHTML += `<div class="ma-msg them" id="ma-thinking"><div class="ma-msg-label">🐭 小老鼠</div>思考中...</div>`;

    try {
      const resp = await fetch("/api/agent/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await resp.json();
      const thinking = this.$("#ma-thinking");
      if (thinking) thinking.remove();
      msgs.innerHTML += `<div class="ma-msg them"><div class="ma-msg-label">🐭 小老鼠</div>${this.escapeHtml(data.reply || "嗯...让我想想")}</div>`;
      this.saveChatHistory();
    } catch (err) {
      const thinking = this.$("#ma-thinking");
      if (thinking) thinking.remove();
      msgs.innerHTML += `<div class="ma-msg them"><div class="ma-msg-label">🐭 小老鼠</div>哎呀，网络出了点问题，等下再问我吧～</div>`;
      this.saveChatHistory();
    }
    msgs.scrollTop = msgs.scrollHeight;
    sendBtn.disabled = false;
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, "<br>");
  }

  // ── 聊天历史持久化（保存最近 30 轮） ───────────────────

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
      localStorage.setItem("mouse_chat_history", JSON.stringify(history));
    } catch (e) {}
  }

  loadChatHistory() {
    let history = [];
    try {
      const raw = localStorage.getItem("mouse_chat_history");
      if (raw) history = JSON.parse(raw);
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
