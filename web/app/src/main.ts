import { createPinia } from 'pinia'
import { createApp } from 'vue'

// Claymorphism 字型：對齊 uupm.cc 教育平台 demo——全站 Nunito（demo 的 :root 只有它）。
// 自帶打包而非 Google Fonts CDN——部署到 CloudFront 後不多一個外部往返（ADR-0018），
// LINE WebView 離線降級時也不會缺字型。中文字自然回落 Noto Sans TC。
import '@fontsource/nunito/400.css'
import '@fontsource/nunito/600.css'
import '@fontsource/nunito/700.css'
import '@fontsource/nunito/800.css'
import '@fontsource/nunito/900.css'

import App from './App.vue'
import { createAppRouter } from './router'
import './styles/main.css'

const app = createApp(App)

app.use(createPinia())
app.use(createAppRouter())
app.mount('#app')
