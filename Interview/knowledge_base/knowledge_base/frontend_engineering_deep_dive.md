# 现代前端工程化与性能优化体系

## 一、浏览器与渲染原理进阶
### 1. 浏览器架构解密
- **多进程架构**：浏览器主进程、渲染进程、GPU 进程、网络进程的分工
- **Chromium 渲染流水线**：从 HTML 字节流到屏幕像素的完整拆解（承接 `browser_rendering.md`）

### 2. 关键渲染路径深度优化
- **Long Task 与 TBT**：如何通过 Web Worker 释放主线程
- **合成层优化**：哪些 CSS 属性会触发 Layer 爆炸？`will-change` 的正确与错误用法

## 二、JavaScript 深度解析
### 1. V8 引擎工作原理
- **隐藏类与内联缓存**：为什么 `delete obj.key` 会拖慢速度？
- **垃圾回收机制**：新生代 Scavenge 算法与老年代标记清除的 Stop-The-World 现象

### 2. 异步编程深度（承接 `js_event_loop.md`）
- **事件循环与帧渲染**：`requestAnimationFrame` 与 `requestIdleCallback` 的执行时机
- **微任务陷阱**：如何通过 `queueMicrotask` 控制流程，避免渲染卡顿

## 三、主流框架原理与设计模式
### 1. React 核心机制
- **Fiber 架构**：可中断的异步渲染与时间切片实现原理
- **Hooks 源码解析**：链表存储、闭包陷阱的成因与 `useEvent` 提案
- **状态管理**：Redux 中间件实现（柯里化与 `compose` 函数）

### 2. Vue 核心机制
- **响应式系统**：Proxy vs Object.defineProperty，`ref` 与 `reactive` 实现差异
- **编译器**：模板解析为 AST 并生成 Render 函数的过程
- **Diff 算法对比**：Vue 3 静态标记与 React 的 Diff 策略差异

## 四、前端工程化与构建工具
### 1. Webpack 核心流程
- **Tapable 事件流机制**：Compiler 与 Compilation 对象生命周期
- **Loader 与 Plugin 开发**：实现自定义语法转换与产物优化

### 2. 新一代构建工具 Vite
- **ESBuild 依赖预构建**：解决 CommonJS 转 ESM 问题
- **热更新**：基于 ESM 的精确模块边界更新

## 五、前端性能监控体系
### 1. 核心指标采集
- **Web Vitals**：LCP、FID、INP（替代 FID 的响应性指标）优化策略
- **自定义测速打点**：`PerformanceObserver` 捕获资源加载瀑布流

### 2. 错误监控与稳定性
- **Sentry 原理**：基于 `window.onerror` 与 `unhandledrejection` 的异常捕获链路
- **SourceMap 上传与堆栈反解**：保障线上报错可读性