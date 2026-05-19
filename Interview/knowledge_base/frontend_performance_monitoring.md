# 前端性能监控与核心 Web Vitals 优化

## 一、Web 性能核心指标（Core Web Vitals）
### 1. LCP（Largest Contentful Paint）
- **定义**：视口内最大可见内容（图片、视频、文本块）的渲染时间
- **优化目标**：≤ 2.5 秒
- **影响因素**：服务器响应时间、资源加载阻塞、渲染阻塞

### 2. INP（Interaction to Next Paint）
- **定义**：替代 FID，衡量用户交互（点击、按键）到浏览器绘制下一帧的延迟
- **优化目标**：≤ 200 毫秒（90% 分位）
- **根源**：长任务阻塞主线程、事件处理函数耗时过长

### 3. CLS（Cumulative Layout Shift）
- **定义**：页面生命周期内意外布局偏移的累积分数
- **优化目标**：≤ 0.1
- **常见原因**：无尺寸的图片/视频、动态注入内容、Web Font 加载

## 二、性能数据采集方案
### 1. 基于 Web API 采集
- **Navigation Timing**：DNS、TCP、SSL、请求响应各阶段耗时
- **Resource Timing**：所有资源加载瀑布流
- **Paint Timing**：FP、FCP
- **Layout Instability API**：CLS 计算

### 2. 使用 PerformanceObserver
- **长任务监控**：`PerformanceObserver` 监听 `longtask` 类型
- **资源加载错误**：监听 `resource` 类型并筛选失败条目

### 3. 自定义测速打点
- **User Timing API**：`performance.mark` 与 `performance.measure`
- **框架生命周期埋点**：React 组件渲染耗时、Vue 路由跳转耗时

### 4. 数据上报策略
- **`sendBeacon`**：页面卸载时可靠上报
- **批量上报**：减少请求次数
- **采样率**：全量采集 vs 1% 采样

## 三、LCP 专项优化
### 1. 服务器与 CDN 优化
- **TTFB 优化**：后端缓存、边缘计算、HTTP/2 Server Push
- **CDN 预热**：将 LCP 资源提前缓存到边缘节点

### 2. 关键资源预加载
- **`<link rel="preload">`**：声明式预加载 LCP 图片或字体
- **`fetchpriority="high"`**：提升资源优先级

### 3. 渲染路径优化
- **移除渲染阻塞资源**：内联关键 CSS、异步加载非关键 CSS
- **避免 JS 阻塞解析**：`async` / `defer`

## 四、INP 专项优化
### 1. 避免长任务
- **任务拆分**：将复杂计算拆分为多个小任务，使用 `setTimeout` 或 `scheduler.yield`
- **Web Worker**：将非 UI 计算移到 Worker 线程

### 2. 事件处理优化
- **防抖与节流**：`scroll`、`resize` 等高频事件
- **`isInputPending`**：检查是否有待处理的输入事件，主动让出主线程

### 3. React 渲染优化
- **`useTransition`**：标记非紧急更新
- **`useDeferredValue`**：延迟渲染大列表

## 五、CLS 专项优化
### 1. 为媒体元素预留空间
- **`width` / `height` 属性**：现代浏览器根据此计算宽高比
- **`aspect-ratio` CSS 属性**

### 2. 动态内容的插入策略
- **避免在现有内容上方插入**：新内容应添加到底部或用户交互后
- **骨架屏占位**：防止数据加载完成后布局突变

### 3. Web Font 加载优化
- **`font-display: optional`**：避免字体切换导致偏移
- **预连接字体源**：`<link rel="preconnect">`

## 六、性能监控平台搭建
### 1. 数据存储与聚合
- **时序数据库**：InfluxDB / Prometheus
- **聚合指标**：P50、P75、P95、P99

### 2. 可视化与告警
- **Grafana 看板**：按页面、地域、设备维度下钻
- **告警规则**：核心指标恶化立即通知

### 3. 与业务指标关联
- **跳出率与 LCP 关系**：LCP 每增加 1 秒，转化率下降 X%