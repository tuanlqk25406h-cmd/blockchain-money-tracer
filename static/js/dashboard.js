/* Local-only dashboard interactions. All records come from the Flask app's bundled JSON. */
(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const state = {
    payload: null,
    selectedWalletId: null,
    walletFilterEnabled: false,
    filterText: "",
    traced: false,
  };

  const positions = {
    "WALLET-A": [92, 255],
    "WALLET-B": [260, 145],
    "WALLET-C": [260, 365],
    "WALLET-D": [438, 82],
    "WALLET-E": [438, 190],
    "WALLET-F": [438, 320],
    "WALLET-G": [438, 430],
    "WALLET-H": [635, 258],
    "EXCHANGE-A": [845, 104],
    "SERVICE-X": [845, 258],
    "EXCHANGE-B": [845, 425],
  };

  const SVG_NS = "http://www.w3.org/2000/svg";

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character]);
  }

  function formatAmount(value, asset = "USDT") {
    const number = Number(value);
    const formatted = new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 4,
    }).format(Number.isFinite(number) ? number : 0);
    return `${formatted} ${asset}`;
  }

  function formatTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value || "—";
    return new Intl.DateTimeFormat("vi-VN", {
      hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    }).format(date);
  }

  function setStatus(message, kind = "normal") {
    const status = byId("status-message");
    status.textContent = message;
    status.classList.toggle("status-error", kind === "error");
    status.classList.toggle("status-success", kind === "success");
  }

  async function loadOverview() {
    try {
      const response = await fetch("/api/overview", { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("Không tải được thông tin kịch bản.");
      const overview = await response.json();
      byId("metric-tracked").innerHTML = `${escapeHtml(overview.initial_amount)} <span>${escapeHtml(overview.asset)}</span>`;
      byId("metric-transactions").textContent = overview.transaction_count;
      setStatus("Sẵn sàng phân tích kịch bản cố định 100 USDT.");
    } catch (error) {
      setStatus(error.message || "Không thể tải dữ liệu mô phỏng.", "error");
    }
  }

  async function startTrace() {
    const button = byId("start-trace");
    button.disabled = true;
    button.classList.add("is-loading");
    button.innerHTML = '<span class="spinner" aria-hidden="true"></span> Tracing…';
    setStatus("Đang lần theo giao dịch và tính toán tín hiệu rủi ro…");

    try {
      const response = await fetch("/api/trace", {
        method: "POST",
        headers: { Accept: "application/json" },
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Không thể hoàn tất truy vết.");
      }

      state.payload = payload;
      state.traced = true;
      state.selectedWalletId = "SERVICE-X";
      state.walletFilterEnabled = false;
      byId("metric-tracked").innerHTML = `${escapeHtml(payload.summary.tracked_terminal_amount)} <span>${escapeHtml(payload.scenario.asset)}</span>`;
      byId("metric-wallets").textContent = payload.summary.wallet_count;
      byId("metric-transactions").textContent = payload.summary.transaction_count;
      byId("metric-high-risk").textContent = payload.summary.high_risk_wallet_count;
      byId("graph-state").textContent = "TRACE COMPLETE";
      byId("graph-footnote").textContent = `${payload.summary.path_count} đường phân bổ nguồn tới điểm cuối`;
      byId("disclaimer-text").textContent = payload.disclaimer;
      renderGraph();
      renderTerminalSummary();
      renderTransactionTable();
      renderWalletDetails("SERVICE-X");
      setConservationState(payload.summary.conservation_passed);
      setStatus("Truy vết hoàn tất. Chọn một nút trên đồ thị để kiểm tra ví và các cảnh báo.", "success");
    } catch (error) {
      setStatus(error.message || "Đã xảy ra lỗi khi truy vết.", "error");
    } finally {
      button.disabled = false;
      button.classList.remove("is-loading");
      button.innerHTML = '<span aria-hidden="true">▶</span> Start Trace';
    }
  }

  function createSvgElement(tag, attributes = {}) {
    const element = document.createElementNS(SVG_NS, tag);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
    return element;
  }

  function addSvgText(parent, x, y, content, className, anchor = "middle") {
    const text = createSvgElement("text", {
      x, y, class: className, "text-anchor": anchor,
    });
    text.textContent = content;
    parent.appendChild(text);
    return text;
  }

  function createNodeMap() {
    const mapped = new Map();
    state.payload.graph.nodes.forEach((node) => {
      const [x, y] = positions[node.id] || [500, 250];
      mapped.set(node.id, { ...node, x, y });
    });
    return mapped;
  }

  function renderGraph() {
    const container = byId("graph-container");
    if (!state.payload) return;

    const svg = createSvgElement("svg", {
      viewBox: "0 0 960 510",
      class: "transaction-graph",
      role: "img",
      "aria-label": "Đồ thị có hướng của các ví và giao dịch mô phỏng",
    });
    const defs = createSvgElement("defs");
    const marker = createSvgElement("marker", {
      id: "edge-arrow", markerWidth: 8, markerHeight: 8,
      refX: 6, refY: 3, orient: "auto", markerUnits: "strokeWidth",
    });
    marker.appendChild(createSvgElement("path", { d: "M0,0 L0,6 L6,3 z", class: "arrow-head" }));
    defs.appendChild(marker);
    svg.appendChild(defs);

    const nodeMap = createNodeMap();
    const edgeLayer = createSvgElement("g", { class: "edge-layer" });
    const labelLayer = createSvgElement("g", { class: "edge-label-layer" });
    const nodeLayer = createSvgElement("g", { class: "node-layer" });
    const activePathTransactions = new Set();
    const selected = nodeMap.get(state.selectedWalletId);
    if (selected) {
      state.payload.trace.paths.forEach((path) => {
        if (path.wallet_path.includes(selected.id)) {
          path.transaction_ids.forEach((transactionId) => activePathTransactions.add(transactionId));
        }
      });
    }

    state.payload.graph.edges.forEach((edge) => {
      const from = nodeMap.get(edge.source);
      const to = nodeMap.get(edge.target);
      if (!from || !to) return;

      const dx = to.x - from.x;
      const dy = to.y - from.y;
      const distance = Math.max(Math.hypot(dx, dy), 1);
      const fromRadius = 60;
      const toRadius = 62;
      const x1 = from.x + dx / distance * fromRadius;
      const y1 = from.y + dy / distance * fromRadius;
      const x2 = to.x - dx / distance * toRadius;
      const y2 = to.y - dy / distance * toRadius;
      const isOnPath = activePathTransactions.has(edge.transaction_id);
      const isSelectedEdge = state.selectedWalletId &&
        (edge.source === state.selectedWalletId || edge.target === state.selectedWalletId);
      const line = createSvgElement("line", {
        x1, y1, x2, y2,
        class: `transaction-edge${isOnPath ? " edge-on-path" : ""}${isSelectedEdge ? " edge-connected" : ""}`,
        "marker-end": "url(#edge-arrow)",
      });
      const title = createSvgElement("title");
      title.textContent = `${edge.transaction_id}: ${edge.source} → ${edge.target}, ${formatAmount(edge.amount, edge.asset)}`;
      line.appendChild(title);
      edgeLayer.appendChild(line);

      const midX = (x1 + x2) / 2;
      const midY = (y1 + y2) / 2;
      const pill = createSvgElement("rect", {
        x: midX - 24, y: midY - 11, width: 48, height: 20, rx: 6,
        class: `edge-label-bg${isOnPath ? " edge-label-bg-active" : ""}`,
      });
      labelLayer.appendChild(pill);
      addSvgText(labelLayer, midX, midY + 3.5, String(edge.amount), "edge-label");
    });

    state.payload.graph.nodes.forEach((node) => {
      const entry = nodeMap.get(node.id);
      const group = createSvgElement("g", {
        class: `wallet-node node-${node.kind}${node.risk_tags?.length ? " node-has-risk-tag" : ""}${node.id === state.selectedWalletId ? " node-selected" : ""}`,
        tabindex: 0,
        role: "button",
        "aria-label": `${node.label}, risk score ${node.score}`,
        "data-wallet-id": node.id,
      });
      const rect = createSvgElement("rect", {
        x: entry.x - 58, y: entry.y - 27, width: 116, height: 54, rx: 11,
        class: "wallet-node-rect",
      });
      group.appendChild(rect);
      addSvgText(group, entry.x, entry.y - 2, node.label.replace(" (simulated)", "").replace(" (synthetic risk label)", ""), "wallet-node-label");
      addSvgText(group, entry.x, entry.y + 15, `RISK ${node.score} · ${node.risk_level.toUpperCase()}`, "wallet-node-score");
      group.addEventListener("click", () => selectWallet(node.id));
      group.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectWallet(node.id);
        }
      });
      nodeLayer.appendChild(group);
    });

    svg.appendChild(edgeLayer);
    svg.appendChild(labelLayer);
    svg.appendChild(nodeLayer);
    container.replaceChildren(svg);
  }

  function selectWallet(walletId) {
    if (!state.payload) return;
    state.selectedWalletId = walletId;
    state.walletFilterEnabled = true;
    renderGraph();
    renderWalletDetails(walletId);
    renderTransactionTable();
  }

  function renderWalletDetails(walletId) {
    const node = state.payload?.graph.nodes.find((item) => item.id === walletId);
    if (!node) return;
    const incoming = state.payload.graph.edges.filter((edge) => edge.target === walletId);
    const outgoing = state.payload.graph.edges.filter((edge) => edge.source === walletId);
    const riskClass = node.risk_level === "high" ? "high" : node.risk_level === "medium" ? "medium" : "low";
    byId("selected-risk-badge").className = `risk-badge risk-${riskClass}`;
    byId("selected-risk-badge").textContent = `SCORE ${node.score}`;

    const riskSignals = node.risk_signals.length
      ? node.risk_signals.map((signal) => `
          <li class="signal-item">
            <div class="signal-header"><strong>${escapeHtml(signal.label)}</strong><span>+${escapeHtml(signal.points)}</span></div>
            <p>${escapeHtml(signal.reason)}</p>
          </li>`).join("")
      : '<li class="no-signals">Không có tín hiệu theo các luật demo đang bật.</li>';

    const tagNote = node.risk_tags?.length
      ? `<p class="synthetic-tag-note">Nhãn thực thể là dữ liệu giả lập, không đại diện đối tượng thật.</p>`
      : "";

    byId("wallet-details").innerHTML = `
      <div class="wallet-detail-top">
        <div class="wallet-avatar avatar-${escapeHtml(node.kind)}">${escapeHtml(node.label.replace(/[^a-zA-Z0-9 ]/g, "").split(" ").map((part) => part[0] || "").join("").slice(0, 2) || "W")}</div>
        <div class="wallet-title-block"><h3>${escapeHtml(node.label)}</h3><code>${escapeHtml(node.id)}</code></div>
      </div>
      <div class="wallet-facts">
        <div><span>Shortest hop</span><strong>${node.shortest_path_depth ?? "—"}</strong></div>
        <div><span>Incoming TX</span><strong>${incoming.length}</strong></div>
        <div><span>Outgoing TX</span><strong>${outgoing.length}</strong></div>
      </div>
      ${tagNote}
      <div class="signals-section">
        <div class="subsection-title"><h4>Risk indicators</h4><span>${node.risk_signals.length} signal(s)</span></div>
        <ul class="signal-list">${riskSignals}</ul>
      </div>
      <div class="wallet-flow-section">
        <div class="subsection-title"><h4>Related transactions</h4><span>${incoming.length + outgoing.length} record(s)</span></div>
        <div class="related-tx-list">
          ${[...incoming.map((edge) => ({ ...edge, direction: "IN", other: edge.source })),
            ...outgoing.map((edge) => ({ ...edge, direction: "OUT", other: edge.target }))]
            .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
            .map((edge) => `<div class="related-tx"><span class="tx-direction ${edge.direction === "IN" ? "tx-in" : "tx-out"}">${edge.direction}</span><div><code>${escapeHtml(edge.transaction_id)}</code><small>${escapeHtml(edge.other)}</small></div><strong>${escapeHtml(formatAmount(edge.amount, edge.asset))}</strong></div>`).join("") || '<p class="no-signals">Không có giao dịch liên quan.</p>'}
        </div>
      </div>
    `;
  }

  function renderTerminalSummary() {
    const summary = state.payload.summary;
    const balances = summary.terminal_balances;
    const labels = new Map(state.payload.graph.nodes.map((node) => [node.id, node.label]));
    byId("terminal-summary").innerHTML = Object.entries(balances).map(([walletId, amount]) => {
      const isFlagged = state.payload.graph.nodes.find((node) => node.id === walletId)?.risk_tags?.length > 0;
      return `
        <button type="button" class="terminal-card${isFlagged ? " terminal-card-flagged" : ""}" data-terminal-id="${escapeHtml(walletId)}">
          <span class="terminal-card-top"><span>${escapeHtml(labels.get(walletId) || walletId)}</span><span class="terminal-marker">${isFlagged ? "FLAGGED" : "ENDPOINT"}</span></span>
          <strong>${escapeHtml(formatAmount(amount, state.payload.scenario.asset))}</strong>
          <small>${escapeHtml(walletId)}</small>
        </button>`;
    }).join("");
    byId("terminal-summary").querySelectorAll("[data-terminal-id]").forEach((button) => {
      button.addEventListener("click", () => selectWallet(button.dataset.terminalId));
    });
  }

  function renderTransactionTable() {
    if (!state.payload) return;
    const query = state.filterText.trim().toLowerCase();
    const selectedId = state.selectedWalletId;
    const edges = state.payload.graph.edges.filter((edge) => {
      const walletMatch = !state.walletFilterEnabled || !selectedId || edge.source === selectedId || edge.target === selectedId;
      const queryMatch = !query || [
        edge.transaction_id, edge.source, edge.target, edge.amount, edge.timestamp,
      ].some((value) => String(value).toLowerCase().includes(query));
      return walletMatch && queryMatch;
    });
    const body = byId("transactions-body");
    if (!edges.length) {
      body.innerHTML = '<tr><td colspan="5" class="table-empty">Không có giao dịch phù hợp với bộ lọc.</td></tr>';
      return;
    }
    body.innerHTML = edges.map((edge) => `
      <tr>
        <td><code>${escapeHtml(edge.transaction_id)}</code></td>
        <td><span class="table-wallet">${escapeHtml(edge.source)}</span></td>
        <td><span class="table-wallet">${escapeHtml(edge.target)}</span></td>
        <td class="amount-cell">${escapeHtml(formatAmount(edge.amount, edge.asset))}</td>
        <td class="time-cell">${escapeHtml(formatTime(edge.timestamp))}</td>
      </tr>`).join("");
  }

  function setConservationState(passed) {
    const badge = byId("conservation-badge");
    badge.className = `conservation-badge ${passed ? "passed" : "failed"}`;
    badge.textContent = passed ? "✓ 100 USDT CONSERVED" : "⚠ CONSERVATION FAILED";
    byId("metric-tracked-note").textContent = passed
      ? "Tổng dòng tiền ở điểm cuối khớp nguồn"
      : "Cần kiểm tra lại kịch bản dòng tiền";
  }

  function resetTrace() {
    state.payload = null;
    state.selectedWalletId = null;
    state.walletFilterEnabled = false;
    state.filterText = "";
    state.traced = false;
    byId("transaction-filter").value = "";
    byId("metric-wallets").textContent = "—";
    byId("metric-transactions").textContent = "15";
    byId("metric-high-risk").textContent = "—";
    byId("metric-tracked").innerHTML = '100 <span>USDT</span>';
    byId("metric-tracked-note").textContent = "Giá trị nguồn đã cấu hình";
    byId("graph-state").textContent = "AWAITING TRACE";
    byId("graph-footnote").textContent = "Các cạnh sẽ hiện số tiền sau khi truy vết";
    byId("selected-risk-badge").className = "risk-badge risk-none";
    byId("selected-risk-badge").textContent = "NO SCORE";
    byId("wallet-details").innerHTML = '<div class="detail-placeholder"><span class="placeholder-icon">◎</span><strong>Select a wallet node</strong><p>Sau khi truy vết, nhấn vào một ví trên đồ thị để xem các giao dịch liên quan và lý do cảnh báo.</p></div>';
    byId("terminal-summary").innerHTML = '<div class="empty-result">Kết quả các điểm cuối sẽ xuất hiện sau khi chạy truy vết.</div>';
    byId("transactions-body").innerHTML = '<tr><td colspan="5" class="table-empty">Chưa có kết quả truy vết.</td></tr>';
    byId("conservation-badge").className = "conservation-badge pending";
    byId("conservation-badge").textContent = "CONSERVATION NOT RUN";
    byId("disclaimer-text").textContent = "Mọi ví và giao dịch đều là dữ liệu mô phỏng. Risk Score là điểm ưu tiên xem xét, không phải xác suất phạm tội hay kết luận pháp lý. FIFO là giả định dạy học để phân bổ dòng tiền khi có hội tụ.";
    byId("graph-container").innerHTML = '<div class="graph-empty"><div class="empty-network" aria-hidden="true"><span class="empty-node e1">A</span><span class="empty-node e2">B</span><span class="empty-node e3">C</span><span class="empty-node e4">?</span><span class="empty-edge ee1"></span><span class="empty-edge ee2"></span><span class="empty-edge ee3"></span></div><h3>Ready to trace the source</h3><p>Nhấn <strong>Start Trace</strong> để tính toán đường đi và tải mạng giao dịch.</p></div>';
    setStatus("Đã đặt lại giao diện. Kịch bản cố định 100 USDT vẫn sẵn sàng.", "normal");
  }

  byId("start-trace").addEventListener("click", startTrace);
  byId("reset-trace").addEventListener("click", resetTrace);
  byId("transaction-filter").addEventListener("input", (event) => {
    state.filterText = event.target.value;
    if (state.traced) renderTransactionTable();
  });

  loadOverview();
})();
