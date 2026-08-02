<script setup lang="ts">
import { computed } from 'vue'

import { DEMO_HOUSEHOLD_ID } from '@/domain/communityDemo'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const firstName = computed(() => session.displayName.slice(0, 1))
</script>

<template>
  <section class="demo-page demo-member-page">
    <header class="demo-hero demo-hero-resident">
      <div>
        <p class="eyebrow">PERSONAL PROFILE・WANG XIAOMING</p>
        <h1>會員中心</h1>
        <p class="demo-hero-lede">這不是空白的新帳號：王小明已經使用一段時間，社區、服務、團購與提醒都留下可回看的生活脈絡。</p>
      </div>
      <div class="demo-hero-side"><span class="demo-kicker">Demo household</span><strong>最近活動：2026/07/31</strong><span>{{ DEMO_HOUSEHOLD_ID }}</span></div>
    </header>

    <section class="panel demo-panel" data-testid="member-identity" aria-labelledby="demo-profile-title">
      <div class="demo-profile-head"><div class="demo-avatar" aria-hidden="true">{{ firstName }}</div><div><p class="eyebrow">SIGNED-IN MEMBER</p><h2 id="demo-profile-title">王小明</h2><p class="demo-meta">A 棟 12F-3・夫妻＋幼兒，共 3 人・自住</p></div></div>
      <dl class="demo-profile-stats"><div><dt>加入社區</dt><dd>2024/06</dd></div><div><dt>參加團購</dt><dd>6 次</dd></div><div><dt>完成服務</dt><dd>12 筆</dd></div><div><dt>Demo 點數</dt><dd>180 點</dd></div></dl>
      <p class="demo-note">目前為競賽用模擬登入；資料只用來展示跨頁面流程，不代表正式帳戶的即時餘額。</p>
    </section>

    <section class="panel demo-panel" aria-labelledby="demo-member-entry-title">
      <div class="demo-section-heading"><div><p class="eyebrow">MY SHORTCUTS</p><h2 id="demo-member-entry-title">我的入口</h2></div><span class="demo-count-badge">4 個常用入口</span></div>
      <ul class="demo-entry-list">
        <li><span class="demo-entry-icon">🏘️</span><div><strong>我的社區</strong><span>公告、問社區、團購與住戶服務</span></div><RouterLink class="button primary" data-testid="member-community-link" to="/demo/community">前往社區 →</RouterLink></li>
        <li><span class="demo-entry-icon">🗓️</span><div><strong>我的月行事曆</strong><span>訂單、節日與主動提醒都在同一個月視圖</span></div><RouterLink class="button" data-testid="member-calendar-link" to="/demo/calendar">打開行事曆 →</RouterLink></li>
        <li><span class="demo-entry-icon">🛒</span><div><strong>社區團購</strong><span>查看進度、選規格、跟團或截止前取消</span></div><RouterLink class="button" to="/demo/resident#group-buys">看進行中團購 →</RouterLink></li>
        <li><span class="demo-entry-icon">🤖</span><div><strong>AI 管家</strong><span>把爸媽來訪、清潔、修繕整理成可編輯任務包</span></div><RouterLink class="button" to="/user/assistant">開啟 AI →</RouterLink></li>
      </ul>
    </section>

    <div class="demo-two-column">
      <section class="panel demo-panel" aria-labelledby="demo-history-title"><div class="demo-section-heading"><div><p class="eyebrow">LIFE TRAIL</p><h2 id="demo-history-title">最近使用紀錄</h2></div><span class="demo-count-badge">持續累積</span></div><ul class="demo-timeline"><li><span class="demo-timeline-dot" /><div><strong>完成冷氣清洗</strong><span class="demo-meta">7/25・社區優惠價 NT$3,500</span></div></li><li><span class="demo-timeline-dot" /><div><strong>參加台農 17 號鳳梨團購</strong><span class="demo-meta">7/29・管理室取貨</span></div></li><li><span class="demo-timeline-dot" /><div><strong>回報地下室滲水</strong><span class="demo-meta">7/27・目前已派工</span></div></li></ul></section>
      <section class="panel demo-panel" aria-labelledby="demo-next-title"><div class="demo-section-heading"><div><p class="eyebrow">NEXT REMINDER</p><h2 id="demo-next-title">下一件生活小事</h2></div><span class="status">8/8</span></div><strong>父親節</strong><p class="demo-note">首頁已收到主動提醒；你可以從月行事曆查看，也可以回社區頁繼續處理團購。</p><div class="button-row"><RouterLink class="button" to="/demo/calendar">看月曆</RouterLink><RouterLink class="button primary" to="/demo/community">回社區</RouterLink></div></section>
    </div>
  </section>
</template>

<style scoped>
.demo-profile-head { display: flex; align-items: center; gap: 1rem; }
.demo-profile-head h2 { margin: 0; }
.demo-avatar { width: 4rem; height: 4rem; display: grid; place-items: center; border: 3px solid var(--ink); border-radius: 50%; background: var(--mint); font-size: 2rem; font-weight: 900; }
.demo-profile-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .75rem; margin: 1.25rem 0 0; }
.demo-profile-stats div { padding: .75rem; border: 2px solid var(--ink); border-radius: 12px; background: var(--surface-2); }
.demo-profile-stats dt { color: var(--muted); font-size: .75rem; font-weight: 800; }
.demo-profile-stats dd { margin: .2rem 0 0; font-size: 1.2rem; font-weight: 900; }
.demo-entry-list { display: grid; gap: .7rem; margin: 0; padding: 0; list-style: none; }
.demo-entry-list li { display: flex; align-items: center; gap: .8rem; padding: .8rem; border: 2px solid var(--ink); border-radius: 14px; background: var(--surface); }
.demo-entry-list li > div { display: grid; gap: .2rem; flex: 1; min-width: 0; }
.demo-entry-list li > div span { color: var(--muted); font-size: .82rem; }
.demo-entry-icon { font-size: 1.5rem; }
@media (max-width: 700px) {
  .demo-profile-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .demo-entry-list li { align-items: flex-start; flex-wrap: wrap; }
  .demo-entry-list .button { margin-left: 2.3rem; }
}
</style>
