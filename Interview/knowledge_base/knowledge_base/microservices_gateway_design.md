# 微服务网关设计与实践

## 一、网关核心职责与选型
### 1. 网关在微服务架构中的角色
- **统一入口**：路由转发、负载均衡
- **安全防护**：认证鉴权、黑白名单、防重放
- **流量治理**：限流熔断、灰度发布
- **协议转换**：HTTP → gRPC / Dubbo

### 2. 主流网关对比
- **Spring Cloud Gateway**：基于 WebFlux，响应式编程，与 Spring 生态无缝集成
- **Kong**：基于 OpenResty，插件丰富，高性能
- **APISIX**：云原生，支持动态路由热更新
- **Envoy**：服务网格数据面，常配合 Istio 使用

## 二、Spring Cloud Gateway 深度解析
### 1. 路由定位原理
- **RoutePredicateHandlerMapping**：根据谓词匹配路由
- **路由定义**：id、uri、predicates、filters

### 2. 谓词工厂
- **Path**：路径匹配
- **Method**：请求方法
- **Header**：Header 正则匹配
- **Query**：Query 参数匹配
- **自定义谓词**：实现 `RoutePredicateFactory`

### 3. 过滤器工厂
- **局部过滤器 vs 全局过滤器**
- **常用内置过滤器**：`AddRequestHeader`、`StripPrefix`、`RequestRateLimiter`
- **自定义过滤器**：实现 `GatewayFilterFactory` 或 `GlobalFilter`

### 4. 网关集成 Sentinel 限流
- **Sentinel 网关流控模式**：Route ID 粒度、API 分组粒度
- **热点参数限流**：针对特定用户 ID 限流

## 三、高性能网关架构设计
### 1. 基于 Netty 的响应式编程
- **Reactor 模型**：单线程 EventLoop 处理多个 Channel
- **背压支持**：防止下游服务慢导致网关内存溢出

### 2. 网关缓存策略
- **响应缓存**：对静态数据或低频变更数据缓存（如商品信息）
- **基于 Redis 的分布式缓存**

### 3. 连接池管理
- **HTTP 连接池**：复用后端连接，减少握手开销
- **连接超时与重试策略**：避免雪崩

## 四、网关安全体系
### 1. 认证与授权
- **JWT 校验**：网关层统一验签，解析用户信息透传给下游
- **OAuth2.0 集成**：作为资源服务器，与授权服务器交互

### 2. 防护机制
- **IP 黑白名单**：基于 Redis 动态更新
- **SQL 注入与 XSS 过滤**：请求参数清洗
- **防重放**：Nonce + Timestamp

### 3. HTTPS 与证书管理
- **网关终结 SSL**：后端服务 HTTP 通信降低开销
- **证书自动续期**：集成 ACME 协议（Let's Encrypt）

## 五、灰度发布与流量染色
### 1. 灰度策略实现
- **基于 Header**：`X-Version: v2` 路由到新版本服务
- **基于权重**：10% 流量导入新版本
- **基于用户 ID 哈希**：固定用户群验证新功能

### 2. 全链路灰度
- **流量标透传**：网关将灰度标识放入 Header，下游服务通过拦截器解析
- **与注册中心联动**：Nacos 元数据版本信息

## 六、网关可观测性
### 1. 访问日志与审计
- **Access Log**：记录请求来源、耗时、状态码
- **审计日志**：敏感操作留痕

### 2. 指标监控
- **QPS、RT、错误率**：按路由维度统计
- **Prometheus + Grafana** 集成

### 3. 分布式追踪
- **TraceId 生成与传递**：网关生成全局 TraceId 注入 Header
- **集成 SkyWalking / Jaeger**