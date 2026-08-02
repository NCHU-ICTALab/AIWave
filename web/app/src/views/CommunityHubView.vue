<script setup lang="ts">
import CommunityBoardView from '@/views/CommunityBoardView.vue'
import DemoResidentView from '@/views/DemoResidentView.vue'
</script>

<template>
  <section class="community-hub-page" data-testid="community-hub">
    <div class="community-hub-intro">
      <p class="eyebrow">MY COMMUNITY・日光森林社區</p>
      <strong>住戶的社區入口</strong>
      <p>公告、生活規約、社區優惠、團購與住戶群組都在同一頁；需要查地圖時也可以直接開生活圈。</p>
      <div class="community-hub-intro-actions"><RouterLink class="button inline" to="/user/community/group-buys">瀏覽社區團購</RouterLink><RouterLink class="button inline" to="/user/life-circle">開啟生活圈地圖</RouterLink></div>
    </div>

    <!-- 顯示順序把 Demo-first 社區首頁放前面；舊的群組／共同需求功能仍保留在下方。 -->
    <div class="community-hub-layout">
      <div class="community-hub-featured">
        <DemoResidentView :embedded="true" calendar-to="/user/calendar" />
      </div>
      <div class="community-hub-tools">
        <CommunityBoardView />
      </div>
    </div>
  </section>
</template>

<style scoped>
.community-hub-page {
  display: grid;
  gap: var(--space-5, 1.25rem);
}
.community-hub-intro {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: .35rem 1rem;
  align-items: center;
  padding: .9rem 1rem;
  border: 2px solid var(--ink);
  border-radius: var(--radius-md);
  background: var(--mint);
  box-shadow: 3px 3px 0 var(--ink);
}
.community-hub-intro .eyebrow {
  grid-column: 1 / -1;
  margin: 0;
}
.community-hub-intro strong {
  font-size: clamp(1.35rem, 3vw, 2rem);
}
.community-hub-intro p:not(.eyebrow) {
  grid-column: 1;
  margin: 0;
  color: var(--accent-ink);
}
.community-hub-intro .button {
  align-self: center;
}
.community-hub-intro-actions {
  display: flex;
  grid-column: 2;
  grid-row: 2 / span 2;
  align-self: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: .5rem;
}
.community-hub-layout {
  display: flex;
  flex-direction: column;
  gap: var(--space-5, 1.25rem);
}
.community-hub-featured {
  order: 1;
  min-width: 0;
}
.community-hub-tools {
  order: 2;
  min-width: 0;
}
@media (max-width: 700px) {
  .community-hub-intro {
    grid-template-columns: 1fr;
  }
  .community-hub-intro .button,
  .community-hub-intro-actions,
  .community-hub-intro p:not(.eyebrow) {
    grid-column: 1;
    grid-row: auto;
  }
  .community-hub-intro-actions { justify-content: flex-start; }
}
</style>
