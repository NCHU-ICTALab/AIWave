<script setup lang="ts">
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
</script>

<template>
  <section class="member-page member-center">
    <header class="page-heading">
      <div>
        <p class="eyebrow">MEMBER</p>
        <h1>會員中心</h1>
        <p class="muted">管理自己的案件、群組範圍與資料使用方式。</p>
      </div>
      <span class="page-status">目前範圍：個人</span>
    </header>

    <section class="panel member-profile" data-testid="member-identity" aria-labelledby="profile-title">
      <div class="member-avatar" aria-hidden="true">{{ session.displayName.slice(0, 1) }}</div>
      <div>
        <p class="eyebrow">SIGNED IN</p>
        <h2 id="profile-title">{{ session.displayName }}</h2>
        <p class="muted">模擬 uniopen 身分 · {{ session.accountId ? '競賽展示會員' : '新會員' }}</p>
      </div>
    </section>

    <div class="member-action-grid">
      <RouterLink class="panel member-action" to="/user/orders">
        <span class="member-action-mark blue" aria-hidden="true">01</span>
        <span>
          <strong>訂單與案件</strong>
          <small>查看報價、服務進度、異常處理與完成紀錄</small>
        </span>
        <span class="action-arrow" aria-hidden="true">→</span>
      </RouterLink>

      <RouterLink class="panel member-action" to="/user/community">
        <span class="member-action-mark mint" aria-hidden="true">02</span>
        <span>
          <strong>群組、家庭與社區</strong>
          <small>以不同群組範圍共享任務、提醒與團購</small>
        </span>
        <span class="action-arrow" aria-hidden="true">→</span>
      </RouterLink>

      <RouterLink class="panel member-action" to="/user/points">
        <span class="member-action-mark peach" aria-hidden="true">03</span>
        <span>
          <strong>點數與優惠</strong>
          <small>查看展示錢包與目前可用的節省方案</small>
        </span>
        <span class="action-arrow" aria-hidden="true">→</span>
      </RouterLink>
    </div>

    <details class="panel privacy-disclosure">
      <summary>AI 如何使用我的資料？</summary>
      <div>
        <p>AI 只在目前登入會員與已同意的群組範圍內整理服務、消費與對話脈絡。</p>
        <ul>
          <li>讀取與導覽可以直接執行。</li>
          <li>修改設定或產生表單前會先預覽。</li>
          <li>兌換、下單、付款、取消一定要由你確認。</li>
        </ul>
        <p class="source-note">目前為競賽用模擬登入；正式串接時由身份服務與同意紀錄取代。</p>
      </div>
    </details>
  </section>
</template>
