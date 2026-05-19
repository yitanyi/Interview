# Java 并发编程深度解析：AQS、线程池与 JUC 工具

## 一、并发编程基础与挑战
### 1. 可见性、原子性与有序性
- **缓存一致性协议（MESI）**：如何保证多核 CPU 下变量的可见性？
- **指令重排序与内存屏障**：volatile 关键字的内存语义
- **Happens-Before 原则**：从 JMM 层面理解并发程序的可预测性

### 2. Java 内存模型（JMM）深入
- **主内存与工作内存抽象**：8 种原子操作（lock、unlock、read、load、use、assign、store、write）
- **final 域的重排序规则**：构造函数逸出问题及解决方案

## 二、AbstractQueuedSynchronizer（AQS）源码剖析
### 1. AQS 核心数据结构
- **CLH 队列变体**：双向链表 + 状态位 + 线程阻塞/唤醒
- **state 变量**：独占模式（1/0）、共享模式（资源数）
- **Node 节点状态**：CANCELLED、SIGNAL、CONDITION、PROPAGATE

### 2. 独占锁获取与释放流程（以 ReentrantLock 非公平锁为例）
- **`acquire` 方法**：tryAcquire → addWaiter → acquireQueued
- **`release` 方法**：tryRelease → unparkSuccessor
- **可重入实现**：state 计数递增，当前线程持有判断

### 3. 共享锁获取与释放（以 Semaphore 为例）
- **`acquireShared` 与 `releaseShared`**：传播机制与唤醒链

### 4. Condition 条件队列
- **等待与通知模型**：await → 加入条件队列并释放锁；signal → 节点转移至同步队列
- **与 Object wait/notify 的区别**：支持多个条件、精确唤醒

## 三、线程池 ThreadPoolExecutor 原理与调优
### 1. 线程池生命周期
- **ctl 变量**：高 3 位存储运行状态（RUNNING、SHUTDOWN、STOP、TIDYING、TERMINATED），低 29 位存储工作线程数
- **状态转换流程**：调用 shutdown() 与 shutdownNow() 的区别

### 2. 任务执行流程
- **核心流程**：小于 corePoolSize → 新增线程；队列未满 → 入队；队列满且小于 maxPoolSize → 新增线程；否则拒绝策略
- **Worker 线程设计**：继承 AQS 实现独占不可重入锁，防止任务执行时被中断

### 3. 阻塞队列选择策略
- **ArrayBlockingQueue**：有界、FIFO、一把锁（put/take 互斥）
- **LinkedBlockingQueue**：可指定容量、两把锁（putLock 与 takeLock）
- **SynchronousQueue**：无容量、配对交换
- **DelayedWorkQueue**：定时任务线程池专用，二叉堆结构

### 4. 拒绝策略应用场景
- **AbortPolicy**：抛异常，适合关键任务
- **CallerRunsPolicy**：调用者线程执行，减缓压力
- **DiscardPolicy**：静默丢弃，适合日志上报等非核心
- **DiscardOldestPolicy**：丢弃最早任务，适合新任务优先场景

### 5. 监控与动态调整
- **获取线程池指标**：getActiveCount()、getQueue().size()、getCompletedTaskCount()
- **动态调整核心参数**：setCorePoolSize()、setMaximumPoolSize()

## 四、JUC 并发工具类实战
### 1. CountDownLatch、CyclicBarrier、Semaphore
- **CountDownLatch**：一等多场景，计数器不可重置
- **CyclicBarrier**：互相等待场景，可重用，支持回调
- **Semaphore**：限流基础，支持公平/非公平

### 2. Exchanger 与 Phaser
- **Exchanger**：两线程交换数据（遗传算法配对场景）
- **Phaser**：多阶段同步屏障（类似 CyclicBarrier 升级版）

### 3. CompletableFuture 异步编排
- **任务组合**：thenApply、thenCompose、thenCombine
- **异常处理**：exceptionally、handle
- **多任务并行**：allOf、anyOf

## 五、并发编程中的陷阱与最佳实践
### 1. 死锁的定位与避免
- **死锁四个必要条件**：互斥、持有并等待、不可剥夺、循环等待
- **`jstack` 检测死锁**：Found one Java-level deadlock
- **避免策略**：固定加锁顺序、尝试获取锁（tryLock 超时）

### 2. 并发集合的使用场景
- **ConcurrentHashMap** vs **Hashtable** vs **Collections.synchronizedMap**
- **CopyOnWriteArrayList**：适合读多写少（监听器列表）
- **BlockingQueue** 生产者消费者模式

### 3. 线程局部变量 ThreadLocal
- **实现原理**：Thread 内部的 ThreadLocalMap，Key 弱引用
- **内存泄漏风险**：使用后必须 remove()
- **InheritableThreadLocal** 与线程池上下文传递问题