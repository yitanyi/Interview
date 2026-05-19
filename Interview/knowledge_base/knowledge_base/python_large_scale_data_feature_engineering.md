# 大规模数据处理与特征工程实战

## 一、Python 处理 GB 级别数据的高效模式
### 1. 分块读取与迭代处理
- **Pandas `chunksize`**：处理超过内存的 CSV/JSON 文件
- **Dask DataFrame**：与 Pandas API 兼容的并行计算框架
- **PySpark**：分布式数据处理入门与 RDD/DataFrame 转换

### 2. 内存优化技巧
- **数据类型降级**：`float64` → `float32`，`int64` → `int32/uint16`
- **稀疏矩阵存储**：`scipy.sparse` 处理高维稀疏特征（如 One-Hot 后）
- **分类特征编码**：`category` 类型大幅降低字符串列内存占用

### 3. 多进程与多线程的正确使用
- **GIL 的影响范围**：CPU 密集型使用 `multiprocessing.Pool`，IO 密集型使用 `ThreadPoolExecutor`
- **共享内存**：`multiprocessing.Array` 与 `multiprocessing.shared_memory`（Python 3.8+）
- **并行化加速 Pandas Apply**：`swifter` 或 `pandarallel` 库原理与限制

## 二、特征工程流水线构建
### 1. 离线特征计算框架
- **时间窗口聚合**：如何计算用户过去 1 天/7 天/30 天的行为统计量
- **序列特征处理**：用户行为序列的截断、填充与特征提取（如平均间隔、突变点）
- **交叉特征**：暴力组合与 FM（因子分解机）交叉项设计

### 2. 特征存储（Feature Store）设计
- **Feast 架构**：离线特征、在线特征的统一管理
- **特征版本控制**：模型训练与线上服务特征逻辑一致性保障
- **Point-in-Time 正确性**：避免特征穿越（使用未来信息）的工程方案

### 3. 自动化特征工程
- **Featuretools**：深度特征合成（DFS）的基本概念（Entity、Relationship）
- **遗传算法与强化学习在特征选择中的应用**（如 tsfresh 的自动特征提取）

## 三、机器学习管道优化
### 1. Scikit-learn Pipeline 实战
- **ColumnTransformer**：针对不同列应用不同预处理（数值/类别/文本）
- **自定义 Transformer**：实现带状态的转换（如计算训练集均值方差用于测试集）
- **缓存中间结果**：`memory` 参数加速重复执行

### 2. 特征选择与重要性评估
- **过滤式**：方差阈值、卡方检验、互信息法（`mutual_info_classif`）
- **包裹式**：RFE（递归特征消除）与交叉验证
- **嵌入式**：XGBoost/LightGBM 的特征重要性（`gain`、`split`、`cover`）
- **Permutation Importance**：模型无关的全局特征重要性评估方法

### 3. 特征稳定性监控
- **PSI（Population Stability Index）**：衡量特征分布偏移
- **CSI（Characteristic Stability Index）**：单特征分箱分布变化检测
- **自动化告警**：生产环境特征漂移的实时检测与触发模型重训

## 四、高效数据 IO 与存储格式
### 1. 列式存储格式对比
- **Parquet**：高压缩比、谓词下推（Predicate Pushdown）
- **Feather**：基于 Arrow 的内存格式，适合 Pandas 与 R 之间快速交换
- **Avro**：适合 Kafka 消息序列化，支持 Schema 演化

### 2. SQL 与 DataFrame 的混合计算
- **DuckDB**：嵌入式 OLAP 引擎，可直接查询 Pandas DataFrame
- **Polars**：基于 Apache Arrow 的高性能 DataFrame 库，懒执行优化

## 五、案例：CTR 预估中的海量特征处理
### 1. 特征规模与挑战
- 用户 ID、物品 ID 的高基数问题（千万级）
- 解决方案：Embedding 化、特征哈希（Hashing Trick）

### 2. 在线/离线一致性保证
- 使用 **Apache Beam** 统一流批特征计算逻辑
- 日志落盘与实时特征拼接的时间窗口对齐策略