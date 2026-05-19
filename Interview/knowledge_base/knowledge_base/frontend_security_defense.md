# 前端安全攻防与防御体系

## 一、Web 常见攻击类型与防御
### 1. XSS（跨站脚本攻击）
- **反射型 XSS**：URL 参数注入，服务端未转义直接反射回 HTML
- **存储型 XSS**：用户输入存入数据库，其他用户访问时触发（如评论系统）
- **DOM 型 XSS**：纯前端 JavaScript 操作 `innerHTML`、`document.write` 引发
- **防御手段**：
  - 输出编码：HTML 实体转义（`<` → `&lt;`）
  - CSP（内容安全策略）：`Content-Security-Policy` 头限制脚本来源
  - `HttpOnly` Cookie：阻止 JavaScript 读取敏感 Cookie
  - 前端框架自动转义（React 的 `dangerouslySetInnerHTML` 警示）

### 2. CSRF（跨站请求伪造）
- **攻击原理**：诱导用户在已登录网站 A 的情况下访问恶意网站 B，B 携带 A 的 Cookie 发起请求
- **防御手段**：
  - **CSRF Token**：服务端生成随机 Token 置于表单隐藏域或 Header（如 `X-CSRF-Token`）
  - **SameSite Cookie**：`Strict`（完全禁止跨站携带）、`Lax`（仅顶级导航允许）、`None`（需配合 Secure）
  - **验证 Referer/Origin**：检查请求来源是否为同源

### 3. SSRF（服务器端请求伪造）
- **前端如何间接引发**：上传图片 URL 功能，若后端不校验协议和域名，可能被利用攻击内网
- **前端防护**：对用户输入的 URL 进行白名单校验（仅允许 `https://cdn.example.com` 等可信域名）

### 4. 点击劫持（Clickjacking）
- **原理**：通过 iframe 透明层诱使用户点击实际页面上的按钮
- **防御**：`X-Frame-Options: DENY` 或 `SAMEORIGIN`

## 二、前端加密与数据安全
### 1. 传输加密
- **HTTPS 强制启用**：HSTS（HTTP Strict Transport Security）头配置
- **证书验证**：浏览器如何校验证书链？中间人攻击的防范

### 2. 本地存储安全
- **敏感数据存储原则**：永远不在 `localStorage`/`sessionStorage` 存放明文密码或 Token
- **Web Crypto API**：客户端加解密（AES-GCM）实现端到端加密
- **IndexedDB 加密**：使用加密库对写入数据加密后再存储

### 3. 前端防篡改
- **Subresource Integrity (SRI)**：为引用的第三方脚本添加 `integrity` 哈希校验
- **代码混淆与反调试**：UglifyJS、Webpack Obfuscator 的局限性

## 三、用户隐私与合规
### 1. GDPR / CCPA 合规
- **Cookie 同意横幅**：获取用户授权前禁止埋设非必要追踪脚本
- **数据最小化**：前端只收集业务必需的用户信息

### 2. 无痕模式与指纹追踪对抗
- **浏览器指纹**：Canvas 指纹、WebGL 指纹、字体列表探测
- **隐私沙盒（Privacy Sandbox）**：Google 提出的 Topics API、FLEDGE

## 四、前端依赖安全
### 1. npm 供应链攻击
- **案例**：event-stream 恶意代码注入、colors 库作者删库
- **防御**：`npm audit`、`yarn audit`、使用 `socket.dev` 检测恶意包
- **锁定版本与私有 npm 仓库**：避免直接从公共仓库拉取不稳定版本

### 2. 代码静态分析
- **ESLint 安全规则插件**：`eslint-plugin-security`、`eslint-plugin-no-unsanitized`
- **正则表达式拒绝服务（ReDoS）**：检测嵌套量词导致的灾难性回溯

## 五、前端监控与应急响应
### 1. 异常捕获与上报
- **`window.onerror`**：捕获运行时错误
- **`unhandledrejection`**：未处理的 Promise 拒绝
- **React Error Boundary**：组件级错误隔离

### 2. 安全事件应急
- **前端 Token 泄露**：立即吊销 Token、通知用户修改密码
- **页面被挂暗链**：扫描服务器文件、回滚发布版本、检查 CDN 缓存