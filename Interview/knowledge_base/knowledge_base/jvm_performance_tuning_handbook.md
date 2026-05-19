# JVM 性能调优实战手册

## 一、JVM 参数配置原则
### 1. 堆内存设置
- **初始堆与最大堆**：`-Xms` 与 `-Xmx` 为什么建议设置为相同值（避免动态扩容带来的性能抖动）
- **新生代与老年代比例**：`-XX:NewRatio` 默认值 2，针对 Web 应用如何调整（通常 1:1 或 1:2）
- **Survivor 区大小**：`-XX:SurvivorRatio` 对晋升阈值的影响

### 2. 元空间（Metaspace）设置
- **`-XX:MaxMetaspaceSize`**：何时需要限制？微服务场景下默认无限制的风险
- **`-XX:MinMetaspaceFreeRatio` 与 `-XX:MaxMetaspaceFreeRatio`**：控制元空间 GC 触发时机

### 3. 直接内存与栈大小
- **`-XX:MaxDirectMemorySize`**：Netty、NIO 框架下直接内存溢出分析
- **`-Xss`**：线程栈深度与递归调用 StackOverflowError 的关系

## 二、垃圾收集器选型与调优
### 1. G1 收集器实战调优
- **核心参数**：`-XX:MaxGCPauseMillis`（期望暂停时间，如 200ms）
- **`-XX:G1HeapRegionSize`**：区域大小对 Mixed GC 效率的影响
- **`-XX:InitiatingHeapOccupancyPercent`**：老年代占用阈值触发并发标记周期
- **日志解读**：`-Xlog:gc*` 输出格式分析（JDK 9+）

### 2. ZGC 低延迟实践
- **ZGC 特点**：着色指针、读屏障、并发整理
- **适用场景**：堆内存 16GB 以上、要求亚毫秒级暂停的在线服务
- **配置示例**：`-XX:+UseZGC -Xms16g -Xmx16g -XX:ConcGCThreads=4`

### 3. Shenandoah 与 Parallel 收集器对比
- **吞吐量优先**：Parallel Scavenge + Parallel Old 组合
- **内存与 CPU 开销**：并发收集器的额外资源消耗评估

## 三、内存溢出（OOM）排查实战
### 1. 常见 OOM 类型与特征
- **`java.lang.OutOfMemoryError: Java heap space`**：堆内存不足，dump 分析大对象
- **`java.lang.OutOfMemoryError: GC overhead limit exceeded`**：GC 占用 98% 时间但回收不到 2% 内存
- **`java.lang.OutOfMemoryError: Direct buffer memory`**：NIO 直接内存未释放
- **`java.lang.OutOfMemoryError: unable to create new native thread`**：线程数超限

### 2. 分析工具链
- **MAT（Memory Analyzer Tool）**：Dominator Tree 定位最大内存消耗对象
- **Arthas**：`heapdump` 在线生成快照、`thread` 查看死锁
- **JProfiler / Async Profiler**：CPU 火焰图与内存分配热点分析

### 3. 典型故障案例
- **案例一**：日志框架异步队列堆积导致堆外内存泄漏
- **案例二**：ThreadLocal 未 remove 导致内存泄漏（弱引用 Entry 的 Key 为 null 但 Value 强引用）
- **案例三**：大量 Proxy 动态类导致 Metaspace OOM

## 四、JIT 编译器与代码优化
### 1. 编译层次与阈值
- **C1（Client Compiler）与 C2（Server Compiler）**：分层编译策略
- **`-XX:CompileThreshold`**：方法调用次数触发 JIT 编译的默认值（Client 1500，Server 10000）

### 2. 逃逸分析
- **标量替换**：对象未逃逸时直接在栈上分配成员变量
- **锁消除**：`StringBuffer` 在单线程环境下的同步锁优化
- **查看逃逸分析效果**：`-XX:+PrintEscapeAnalysis`

### 3. 即时编译日志
- **`-XX:+PrintCompilation`**：查看哪些方法被编译为本地代码
- **`-XX:+UnlockDiagnosticVMOptions -XX:+PrintInlining`**：方法内联情况追踪

## 五、容器环境下的 JVM 调优
### 1. 容器资源感知
- **JDK 8u191 之前**：JVM 无法感知容器限制，需手动设置 `-Xmx`
- **`-XX:+UseContainerSupport`**：让 JVM 读取 cgroup 内存限制

### 2. CPU 限制与 GC 线程数
- **`-XX:ActiveProcessorCount`**：手动指定可用核心数
- **ParallelGCThreads 与 ConcGCThreads** 自动计算公式