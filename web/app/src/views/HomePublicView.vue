<script setup lang="ts">
// 公開首頁(spec 15 §9.1、方向 A 原型 home-public.html):
// 未登入者先看懂產品價值;右上角登入入口。不顯示任何個人資料。
// 品牌標記走 bundler import;`public/` 路徑在 vitest 解析不到（見 App.vue 的說明）。
import brandMark from '@/assets/aiwave.ico'
const scenes = [
  { name: '食・餐廳訂位', desc: '21PLUS 合作餐廳線上訂位' },
  { name: '醫・處方箋領藥', desc: '處方箋辨識與康是美門市領藥(辨識展示,非醫療建議)' },
  { name: '住・清潔修繕', desc: 'DUSKIN 樂清、王子水電到府服務' },
  { name: '行・洗車與宅配', desc: '速邁樂精緻洗車、黑貓宅急便' },
  { name: '預・預購購物', desc: '7-ELEVEN i 預購與門市取貨' },
  { name: '樂・渡假訂房', desc: '統一渡假村馬武督/谷關線上訂房' },
]

const pillars = [
  { title: '同一份資料,三種操作方式', body: '手動網頁、AI 管家與廠商後台操作的是同一筆訂單與狀態;不會有兩套帳。' },
  { title: '真實時段,不是隨機媒合', body: '你從廠商實際提供的據點、方案與空檔中選擇,價格與點數折抵在下單前算清楚。' },
  { title: '全程可追蹤、可恢復', body: '每筆訂單有進度時間軸、通知與行事曆同步;取消、退款與失敗重試都有明確路徑。' },
]
</script>

<template>
  <a class="skip-link" href="#main-content">跳至主要內容</a>
  <header class="public-header">
    <span class="wordmark">
      <img class="wordmark-mark" :src="brandMark" alt="" width="32" height="32" aria-hidden="true" />
      <span>社區小統</span>
    </span>
    <RouterLink class="button primary" to="/login" data-testid="public-sign-in">登入</RouterLink>
  </header>

  <main id="main-content" class="public-main" tabindex="-1">
    <section class="public-hero">
      <div>
        <h1>一個地方,搞定生活裡每一件要辦的事</h1>
        <p class="login-lede">
          訂位、清潔修繕、寄件、購物與社區服務放進同一條可追蹤的任務流程。
          你可以完全手動操作,也可以交給 AI 管家協助——兩邊看到的是同一份訂單、點數與行事曆。
        </p>
        <div class="public-cta-row">
          <RouterLink class="button primary" to="/login">立即登入體驗</RouterLink>
          <a class="button" href="#scenes">看看能做什麼</a>
        </div>
        <p class="muted public-note">競賽展示版本;商家、價格與訂單皆為展示資料(partner-demo-v5 seed)。</p>
      </div>
    </section>

    <section id="scenes" class="public-section" aria-labelledby="scenes-title">
      <h2 id="scenes-title">六大生活場景</h2>
      <ul class="public-scenes">
        <li v-for="scene in scenes" :key="scene.name" class="panel public-scene">
          <strong>{{ scene.name }}</strong>
          <span class="muted">{{ scene.desc }}</span>
        </li>
      </ul>
    </section>

    <section class="public-section" aria-labelledby="why-title">
      <h2 id="why-title">為什麼不是又一個服務型錄</h2>
      <div class="public-pillars">
        <article v-for="pillar in pillars" :key="pillar.title" class="panel">
          <h3>{{ pillar.title }}</h3>
          <p class="muted">{{ pillar.body }}</p>
        </article>
      </div>
    </section>
  </main>

  <footer class="public-footer">
    <p class="muted">2026 雲湧智生黑客松競賽作品;品牌名稱僅用於競賽展示情境。</p>
  </footer>
</template>

<style scoped>
.public-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) clamp(1rem, 4vw, 3rem);
  background: var(--surface);
  border-bottom: var(--border-chunky) solid var(--ink);
}
.public-main {
  max-width: 72rem;
  margin: 0 auto;
  padding: var(--space-5) clamp(1rem, 4vw, 3rem) var(--space-7);
}
.public-hero {
  padding-block: var(--space-6) var(--space-5);
  max-width: 46rem;
}
.public-cta-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-block: var(--space-4);
}
.public-note {
  font-size: var(--text-sm);
}
.public-section {
  margin-top: var(--space-6);
}
.public-scenes {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: var(--space-4);
}
.public-scene {
  display: grid;
  gap: var(--space-1);
}
.public-pillars {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  gap: var(--space-4);
}
.public-footer {
  border-top: var(--border-chunky) solid var(--ink);
  background: var(--surface);
  padding: var(--space-4) clamp(1rem, 4vw, 3rem);
}
</style>
