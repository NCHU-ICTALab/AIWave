/**
 * 導覽等純呈現用資料。
 *
 * 服務目錄已移到後端（`/api/v1/services`），不再放這裡——見 ADR-0002。
 */

export const navItems = [
  { to: '/app/today', label: '今日', code: '01' },
  { to: '/app/services', label: '找服務', code: '02' },
  { to: '/app/orders', label: '訂單', code: '03' },
  { to: '/app/community', label: '社區', code: '04' },
  { to: '/app/vendor', label: '廠商', code: '05' },
  { to: '/app/platform', label: '整合', code: '06' },
]
