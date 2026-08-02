import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  DEMO_HOUSEHOLD_ID,
  type DemoCommunityAnswer,
  type DemoCommitteeDashboard,
  type DemoGroupBuy,
  type DemoOrder,
  type DemoResidentDashboard,
  type DemoSubscriptionSummary,
  type DemoUnansweredQuestion,
  type JoinGroupBuyInput,
  type PublishDemoGroupBuyInput,
  type UpdateDemoGroupBuyInput,
} from '@/domain/communityDemo'
import { communityDemoService } from '@/services/communityDemoService'

export const useCommunityDemoStore = defineStore('community-demo', () => {
  const residentDashboard = ref<DemoResidentDashboard | null>(null)
  const committeeDashboard = ref<DemoCommitteeDashboard | null>(null)
  const subscription = ref<DemoSubscriptionSummary | null>(null)
  const lastAnswer = ref<DemoCommunityAnswer | null>(null)
  const lastResetAt = ref(0)

  const activeGroupBuys = computed(() => residentDashboard.value?.activeGroupBuys ?? [])
  const myOrders = computed<DemoOrder[]>(() => (
    residentDashboard.value ? communityDemoService.listMyOrders(residentDashboard.value.resident.householdId) : []
  ))

  function loadResident(householdId = DEMO_HOUSEHOLD_ID) {
    residentDashboard.value = communityDemoService.getResidentDashboard(householdId)
  }

  function loadCommittee() {
    committeeDashboard.value = communityDemoService.getCommitteeDashboard()
    subscription.value = communityDemoService.getSubscriptionSummary()
  }

  function listAnnouncements() {
    return communityDemoService.listAnnouncements()
  }

  function askCommunity(query: string, householdId = DEMO_HOUSEHOLD_ID) {
    lastAnswer.value = communityDemoService.askCommunity(query, householdId)
    loadResident(householdId)
    loadCommittee()
    return lastAnswer.value
  }

  function reportUnanswered(query: string, householdId = DEMO_HOUSEHOLD_ID) {
    const item = communityDemoService.reportUnanswered(query, householdId)
    loadCommittee()
    return item
  }

  function getGroupBuy(id: string): DemoGroupBuy | null {
    return communityDemoService.getGroupBuy(id)
  }

  function publishDemoGroupBuy(input?: PublishDemoGroupBuyInput) {
    const group = communityDemoService.publishDemoGroupBuy(input)
    loadResident()
    loadCommittee()
    return group
  }

  function updateGroupBuy(groupBuyId: string, input: UpdateDemoGroupBuyInput) {
    const group = communityDemoService.updateGroupBuy(groupBuyId, input)
    loadResident()
    loadCommittee()
    return group
  }

  function closeGroupBuy(groupBuyId: string) {
    const group = communityDemoService.closeGroupBuy(groupBuyId)
    loadResident()
    loadCommittee()
    return group
  }

  function reopenGroupBuy(groupBuyId: string) {
    const group = communityDemoService.reopenGroupBuy(groupBuyId)
    loadResident()
    loadCommittee()
    return group
  }

  function joinGroupBuy(input: JoinGroupBuyInput) {
    const group = communityDemoService.joinGroupBuy(input)
    loadResident(input.householdId)
    loadCommittee()
    return group
  }

  function cancelGroupBuy(groupBuyId: string, householdId = DEMO_HOUSEHOLD_ID) {
    const group = communityDemoService.cancelGroupBuy(groupBuyId, householdId)
    loadResident(householdId)
    loadCommittee()
    return group
  }

  function markUnansweredForWiki(id: string): DemoUnansweredQuestion | null {
    const item = communityDemoService.markUnansweredForWiki(id)
    loadCommittee()
    return item
  }

  function getSubscriptionSummary() {
    subscription.value = communityDemoService.getSubscriptionSummary()
    return subscription.value
  }

  function resetDemo() {
    communityDemoService.resetDemo()
    residentDashboard.value = null
    committeeDashboard.value = null
    subscription.value = null
    lastAnswer.value = null
    lastResetAt.value += 1
    loadResident()
    loadCommittee()
  }

  return {
    activeGroupBuys,
    askCommunity,
    cancelGroupBuy,
    closeGroupBuy,
    committeeDashboard,
    getGroupBuy,
    getSubscriptionSummary,
    joinGroupBuy,
    lastAnswer,
    lastResetAt,
    listAnnouncements,
    loadCommittee,
    loadResident,
    markUnansweredForWiki,
    myOrders,
    publishDemoGroupBuy,
    reopenGroupBuy,
    reportUnanswered,
    resetDemo,
    residentDashboard,
    subscription,
    updateGroupBuy,
  }
})
