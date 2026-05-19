# Java 工程师全栈知识手册

## 一、Java 语言核心进阶
### 1. 集合框架源码解析
- HashMap 与 ConcurrentHashMap 的底层数据结构（数组+链表/红黑树）与扩容机制
- ArrayList 与 LinkedList 的性能对比与应用场景
- 并发容器：CopyOnWriteArrayList、BlockingQueue

### 2. JUC 并发编程实战
- **AQS（AbstractQueuedSynchronizer）原理**：同步队列、共享锁与独占锁
- **线程池**：ThreadPoolExecutor 七大参数与拒绝策略调优
- **CompletableFuture**：异步编排与任务组合

### 3. JVM 高级调优（承接前文 `jvm_memory_model.md`）
- **垃圾收集器选型**：G1（JDK 9+ 默认）与 ZGC 对比
- **故障排查工具**：Arthas、JProfiler、MAT 分析 OOM 内存快照
- **逃逸分析与栈上分配**：如何通过 JIT 优化减少堆内存压力

## 二、Spring 生态与微服务
### 1. Spring Framework 核心
- **IOC 容器**：Bean 生命周期（从 BeanDefinition 到销毁的完整闭环）
- **AOP 实现原理**：JDK 动态代理 vs CGLIB，切面失效场景排查
- **事务传播机制**：REQUIRES_NEW 与 NESTED 的物理事务与逻辑事务区别

### 2. Spring Boot 自动装配
- `@SpringBootApplication` 注解详解
- `spring.factories` 与自定义 Starter 开发

### 3. Spring Cloud 微服务组件
- **服务发现**：Nacos CAP 模型配置与 AP/CP 切换
- **配置中心**：配置热更新原理（RefreshScope）
- **网关**：Spring Cloud Gateway 谓词工厂与自定义全局过滤器

## 三、数据库与持久层优化
### 1. MySQL 实战优化
- **Explain 执行计划解读**：Using index、Using where、Using temporary 的应对策略
- **分库分表中间件**：ShardingSphere 数据分片算法与分布式主键生成

### 2. MyBatis 深度解析
- **一级缓存与二级缓存**：集成 Redis 实现分布式二级缓存
- **插件机制**：基于责任链模式实现 SQL 拦截与改写

## 四、消息中间件与高并发架构
### 1. RocketMQ / Kafka 核心对比
- **消息可靠性**：同步刷盘 vs 异步刷盘，Producer 重试机制
- **消息堆积处理**：增加 Consumer 实例、批量消费、消息超时丢弃策略
- **事务消息**：RocketMQ 半消息机制与回查原理

### 2. 分布式事务解决方案
- **Seata AT 模式**：两阶段提交与全局锁机制
- **TCC 与 SAGA**：柔性事务的适用场景与空回滚、悬挂问题解决

## 五、设计模式与代码重构
### 1. 常用设计模式实战
- **策略模式**：消除项目中的大量 `if-else`
- **模板方法模式**：AQS、Spring JdbcTemplate 源码中的体现
- **责任链模式**：网关过滤器链、MyBatis 插件链

### 2. 重构原则
- 重构与性能优化的平衡
- 代码坏味道：过长参数列表、依恋情结、霰弹式修改的识别与修复