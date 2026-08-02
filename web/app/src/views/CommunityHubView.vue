<script setup lang="ts">
import SubscriptionLock from '@/components/SubscriptionLock.vue'
import CommunityBoardView from '@/views/CommunityBoardView.vue'
import DemoResidentView from '@/views/DemoResidentView.vue'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
</script>

<template>
  <section class="community-hub-page" data-testid="community-hub">
    <div class="community-hub-intro">
      <p class="eyebrow">MY COMMUNITY・日光森林社區</p>
      <strong>住戶的社區入口</strong>
      <p>公告、生活規約、社區優惠、團購與住戶群組都在同一頁；需要查地圖時也可以直接開生活圈。</p>
      <div class="community-hub-intro-actions">
        <RouterLink class="button inline" to="/user/community/group-buys">瀏覽社區團購</RouterLink>
        <RouterLink v-if="session.isSubscriber" class="button inline" to="/user/life-circle">開啟生活圈地圖</RouterLink>
        <RouterLink v-else class="button inline" to="/user/subscription">生活圈・訂閱解鎖</RouterLink>
      </div>
    </div>

    <!-- 顯示順序把 Demo-first 社區首頁放前面；舊的群組／共同需求功能仍保留在下方。 -->
    <div v-if="session.isSubscriber" class="community-hub-layout">
      <div class="community-hub-featured">
        <DemoResidentView :embedded="true" calendar-to="/user/calendar" />
      </div>
      <div class="community-hub-tools">
        <CommunityBoardView />
      </div>
    </div>
    <!--
      免費社區：鎖住公告 Wiki／生活圈／AI，但團購必須留著——那是免費方案的全部價值，
      把整頁擋掉等於連唯一開放的功能一起擋掉。
    -->
    <template v-else>
      <header class="page-heading">
        <div><p class="eyebrow">GROUP BUYING</p><h1>社區團購</h1></div>
        <span class="page-status">免費社區</span>
      </header>

      <section class="panel community-subscription-gate" data-testid="community-subscription-gate" aria-labelledby="community-subscription-title">
        <div class="community-gate-icon" aria-hidden="true">♛</div>
        <div>
          <p class="eyebrow">FREE COMMUNITY</p>
          <h2 id="community-subscription-title">免費會員先從團購開始</h2>
          <p>你現在可以完整瀏覽商品、參加團購，也可以自己開團；社區公告與生活 Wiki、生活圈地圖與附近服務、AI 管家與社區優惠則在社區訂閱後解鎖——本頁最下方就是解鎖後的實際畫面。</p>
          <div class="community-gate-actions">
            <RouterLink class="button primary" to="/user/community/group-buys">前往團購列表</RouterLink>
            <RouterLink class="button" to="/user/subscription">查看訂閱方案</RouterLink>
          </div>
        </div>
      </section>

      <CommunityBoardView :group-buy-only="true" />

      <!--
        「🔒 社區公告與生活 Wiki」這種條列說不清楚訂閱到底換到什麼；直接把訂閱住戶
        會看到的那一頁霧面放上來，住戶自己看得懂差別（內容被設成 inert，點不到也唸不到）。
      -->
      <SubscriptionLock
        title="社區公告、生活 Wiki 與社區優惠"
        description="訂閱社區後，公告、規約問答、包裹與報修進度、社區優惠服務都會在這裡；免費社區仍可完整使用上方的社區團購。"
        :heading-level="2"
      >
        <DemoResidentView :embedded="true" calendar-to="/user/calendar" />
      </SubscriptionLock>
    </template>
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
.community-subscription-gate {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
  background: var(--peach);
}
.community-subscription-gate h2,
.community-subscription-gate p { margin-top: 0; }
.community-gate-icon { display: grid; place-items: center; width: 3rem; height: 3rem; border: 2px solid var(--ink); border-radius: 50%; background: var(--yellow, #fde68a); font-size: 1.8rem; }
.community-gate-actions { display: flex; flex-wrap: wrap; gap: .5rem; }
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
  .community-subscription-gate { grid-template-columns: 1fr; }
}
</style>
