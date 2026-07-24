const themeDetails = {
  grid: {
    title: '01 理性企業',
    note: '清楚、可信、方正，最適合四工作區與評審快速理解。',
    detail: '特色細節：以編號、分隔線和資訊網格呈現「平台把複雜服務整理好」。',
  },
  warm: {
    title: '02 溫暖生活',
    note: '柔和、親切、低壓力，讓個人推薦與樂齡使用者更容易接近。',
    detail: '特色細節：自然色、較短文句與柔和曲線，像可靠的生活服務櫃台。',
  },
  pulse: {
    title: '03 智慧零售',
    note: '明快、有節奏、行動導向，適合優惠、服務入口與高頻日常使用。',
    detail: '特色細節：色塊即分類、數字即導航，保留零售活力但不犧牲資訊層級。',
  },
  data: {
    title: '04 數據管家',
    note: '高密度、即時、專業，最能突出跨服務資料整合與 AI 決策能力。',
    detail: '特色細節：狀態、數字與服務流同屏，適合平台整合中心與營運工作區延伸。',
  },
  calm: {
    title: '05 精緻極簡',
    note: '克制、安靜、有質感，讓 Demo 看起來接近成熟消費產品。',
    detail: '特色細節：大量留白、細緻字級差與少量暖金，讓每個決策點有呼吸空間。',
  },
  clinical: {
    title: '06 臨床零售',
    note: '保留 03 的快速資訊節奏，套用 02 的圓角與附件的霧白、黑灰、細邊界元件系統。',
    detail: '特色細節：24px 容器、18px 操作元件、單色資訊層級與三欄服務入口；統一資訊官網只供服務研究，不參與視覺配色。',
  },
  bridge: {
    title: '07 生活指揮台',
    note: '將 Variant B「艦橋儀控」的掃描、判斷、執行節奏移植到個人生活服務，不沿用船舶內容。',
    detail: '特色細節：頂部步驟導覽、2–3px 實邊、等寬數字與青綠／琥珀狀態色；適合突出 AI 統整多服務後給出可執行決策。',
  },
  hybrid: {
    title: '08 柔和指揮台',
    note: '保留 07 的頂部流程與高密度資訊架構，換成 06 的圓角、留白與生活服務溫度。',
    detail: '特色細節：品牌色只用於操作和狀態；卡片陰影統一為低透明度中性黑，不再出現彩色投影或大面積高飽和色塊。',
  },
};

const preview = document.querySelector('#app-preview');
const stage = document.querySelector('.browser-stage');
const noteBox = document.querySelector('#direction-notes');
const colorwayPanel = document.querySelector('.colorway-panel');
const hybridPanel = document.querySelector('.hybrid-panel');
const toast = document.querySelector('.toast');
let selectedColorway = 'teal';
let selectedHybridTone = 'bridge';

document.querySelectorAll('.direction-button').forEach((button) => {
  button.addEventListener('click', () => {
    const theme = button.dataset.theme;
    document.querySelectorAll('.direction-button').forEach((item) => {
      const active = item === button;
      item.classList.toggle('is-active', active);
      item.setAttribute('aria-pressed', String(active));
    });
    const variantClass = theme === 'clinical'
      ? ` color-${selectedColorway}`
      : theme === 'hybrid' ? ` tone-${selectedHybridTone}` : '';
    preview.className = `app-viewport theme-${theme}${variantClass}`;
    colorwayPanel.hidden = theme !== 'clinical';
    hybridPanel.hidden = theme !== 'hybrid';
    const detail = themeDetails[theme];
    noteBox.innerHTML = `<p><strong>${detail.title}</strong>：${detail.note}</p><p>${detail.detail}</p>`;
  });
});

document.querySelectorAll('.hybrid-tone-button').forEach((button) => {
  button.addEventListener('click', () => {
    selectedHybridTone = button.dataset.hybridTone;
    document.querySelectorAll('.hybrid-tone-button').forEach((item) => {
      const active = item === button;
      item.classList.toggle('is-active', active);
      item.setAttribute('aria-pressed', String(active));
    });
    document.querySelector('[data-theme="hybrid"]').click();
  });
});

document.querySelectorAll('[data-colorway]').forEach((button) => {
  button.addEventListener('click', () => {
    selectedColorway = button.dataset.colorway;
    document.querySelectorAll('[data-colorway]').forEach((item) => {
      const active = item === button;
      item.classList.toggle('is-active', active);
      item.setAttribute('aria-pressed', String(active));
    });
    document.querySelector('[data-theme="clinical"]').click();
  });
});

document.querySelectorAll('button[data-device]').forEach((button) => {
  button.addEventListener('click', () => {
    const device = button.dataset.device;
    stage.dataset.device = device;
    document.querySelectorAll('button[data-device]').forEach((item) => {
      const active = item === button;
      item.classList.toggle('is-active', active);
      item.setAttribute('aria-pressed', String(active));
    });
  });
});

document.querySelector('[data-feedback]').addEventListener('click', () => {
  toast.hidden = false;
  toast.querySelector('[data-undo]').focus();
});

document.querySelector('[data-undo]').addEventListener('click', () => {
  toast.hidden = true;
  document.querySelector('[data-feedback]').focus();
});

document.querySelectorAll('a[href="#"]').forEach((link) => {
  link.addEventListener('click', (event) => event.preventDefault());
});
