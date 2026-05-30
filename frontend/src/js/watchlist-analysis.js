let carouselIndex = 0;
const STICKY_NOTE_W = 214;

async function assessAll() {
    if (watchlistStocks.length === 0) {
        document.getElementById('assessStatus').textContent = '请先添加自选股';
        return;
    }
    const btn = document.querySelector('.assess-btn');
    const status = document.getElementById('assessStatus');
    btn.disabled = true;
    const total = watchlistStocks.length;
    let done = 0;
    for (const s of watchlistStocks) {
        status.textContent = `测评中 ${done + 1}/${total}：${s.name || s.code}...`;
        try {
            const resp = await fetch(`/api/watchlist/detail/${s.code}`);
            if (!resp.ok) { const d = await resp.json(); handleAuthError(d.detail); continue; }
            if (resp.ok) {
                const data = await resp.json();
                assessmentResults[s.code] = data;
            }
        } catch (e) {
            console.warn('assessAll error', s.code, e);
        }
        done++;
    }
    status.textContent = `测评完成，共 ${Object.keys(assessmentResults).length} 只`;
    btn.disabled = false;
    renderWatchlistGrid();
    renderRatingList();
    renderStickyNotes();
}

function _starsHtml(n, cls) {
    n = Math.max(1, Math.min(5, n || 3));
    const stars = Array.from({length: 5}, (_, i) =>
        `<span class="${i < n ? 'star-on' : 'star-off'}">★</span>`
    ).join('');
    return `<span class="stars-row ${cls || ''}">${stars}</span>`;
}

function _riskStarsHtml(n) {
    n = Math.max(1, Math.min(5, n || 3));
    const colors = {1: '#ef4444', 2: '#f97316', 3: '#f59e0b', 4: '#4ade80', 5: '#22c55e'};
    const color = colors[n];
    const stars = Array.from({length: 5}, (_, i) =>
        `<span style="color:${i < n ? color : 'rgba(148,163,184,0.30)'}">★</span>`
    ).join('');
    return `<span class="stars-row" title="${n}星·${n >= 4 ? '低风险' : n <= 2 ? '高风险' : '中风险'}">${stars}</span>`;
}

function renderRatingList() {
    const container = document.getElementById('ratingListContainer');
    const entries = Object.values(assessmentResults);
    if (entries.length === 0) {
        container.innerHTML = '<div class="rating-empty">点击「一键测评」生成排行榜</div>';
        return;
    }
    const sorted = [...entries].sort((a, b) => (b.overall_stars || 0) - (a.overall_stars || 0));
    container.innerHTML = `
        <div class="rating-legend">⭐多星=低风险(绿) &nbsp; ⭐少星=高风险(红)</div>
        <table class="rating-table">
            <thead><tr>
                <th class="rating-rank">#</th>
                <th>代码</th><th>名称</th>
                <th>财报风险</th><th>舆论风险</th><th>市场风险</th><th>综合风险</th>
            </tr></thead>
            <tbody>${sorted.map((d, i) => {
                const medalCls = i < 3 ? ` rank-medal-${i + 1}` : '';
                return `
                <tr onclick="openDetail('${d.code}')" style="cursor:pointer;">
                    <td class="rating-rank"><span class="rank-medal${medalCls}">${i + 1}</span></td>
                    <td>${d.code}</td>
                    <td>${d.name || d.code}</td>
                    <td>${_riskStarsHtml(d.fundamental_stars)}</td>
                    <td>${_riskStarsHtml(d.news_stars)}</td>
                    <td>${_riskStarsHtml(d.risk_stars)}</td>
                    <td>${_riskStarsHtml(d.overall_stars)}</td>
                </tr>`;
            }).join('')}
            </tbody>
        </table>`;
}

function renderStickyNotes() {
    const container = document.getElementById('stickyNotesContainer');
    const entries = Object.values(assessmentResults);
    if (entries.length === 0) {
        container.innerHTML = '<div class="sticky-note-empty">测评后将生成风险便利贴</div>';
        const dots = document.getElementById('carouselDots');
        if (dots) dots.innerHTML = '';
        return;
    }
    carouselIndex = 0;
    container.style.transition = 'none';
    container.style.transform = 'translateX(0)';
    container.innerHTML = entries.map(d => `
        <div class="sticky-note">
            <div class="sticky-note-name">${d.name || d.code}</div>
            <div class="sticky-note-code">${d.code}</div>
            <div class="sticky-note-brief">${d.brief || '暂无 AI 解读'}</div>
            <div class="sticky-note-footer">
                <span class="sticky-note-stars">${_riskStarsHtml(d.overall_stars)}</span>
                <button class="sticky-note-btn"
                    onclick="prefillDiary('${d.code}','${(d.name||d.code).replace(/'/g,'')}')">
                    记录日记
                </button>
            </div>
        </div>`).join('');
    initCarousel(entries.length);
}

function initCarousel(count) {
    const dots = document.getElementById('carouselDots');
    if (!dots) return;
    dots.innerHTML = Array.from({length: count}, (_, i) =>
        `<span class="carousel-dot${i === 0 ? ' active' : ''}" onclick="goToSlide(${i})"></span>`
    ).join('');
    updateCarouselDisplay();
}

function updateCarouselDisplay() {
    const track = document.getElementById('stickyNotesContainer');
    if (track) {
        track.style.transition = 'transform 0.35s cubic-bezier(0.4,0,0.2,1)';
        track.style.transform = `translateX(-${carouselIndex * STICKY_NOTE_W}px)`;
    }
    document.querySelectorAll('#carouselDots .carousel-dot').forEach((d, i) =>
        d.classList.toggle('active', i === carouselIndex)
    );
    document.querySelectorAll('#stickyNotesContainer .sticky-note').forEach((n, i) =>
        n.classList.toggle('carousel-active', i === carouselIndex)
    );
}

function scrollCarousel(dir) {
    const total = document.querySelectorAll('#stickyNotesContainer .sticky-note').length;
    if (total === 0) return;
    carouselIndex = (carouselIndex + dir + total) % total;
    updateCarouselDisplay();
}

function goToSlide(index) {
    carouselIndex = index;
    updateCarouselDisplay();
}
