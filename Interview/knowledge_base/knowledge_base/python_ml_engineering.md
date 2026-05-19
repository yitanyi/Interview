# Python 算法工程与模型部署实战

## 一、Python 语言高性能编程
### 1. 进阶特性与性能优化
- **生成器与迭代器**：惰性计算处理超大日志文件（GB 级别）
- **协程与异步 IO**：`async/await` 在高并发推理服务中的应用
- **性能分析**：使用 `line_profiler` 和 `memory_profiler` 定位代码瓶颈

### 2. 科学计算与数据处理
- **NumPy 向量化**：避免 Python 原生 for 循环，利用 SIMD 加速
- **Pandas 内存优化**：`category` 类型降维、分块读取 CSV

## 二、深度学习框架核心原理
### 1. PyTorch 进阶
- **自动求导机制**：计算图构建与 `torch.no_grad()` 内存释放
- **混合精度训练**：AMP（Automatic Mixed Precision）加速与梯度缩放
- **分布式训练**：DataParallel (DP) vs DistributedDataParallel (DDP) 原理与通信开销

### 2. 模型可视化与调试
- 使用 TensorBoard 可视化计算图与 Embedding 降维分布
- 梯度消失/爆炸的实时监控与排查

## 三、模型优化与压缩
### 1. 模型轻量化技术
- **量化感知训练**：模拟量化误差，减小精度损失
- **知识蒸馏进阶**：FitNet（中间层提示学习）与自蒸馏
- **模型结构搜索**：基于 Once-for-All (OFA) 的硬件感知搜索

### 2. 推理引擎优化
- **ONNX Runtime**：从 PyTorch 到 ONNX 的算子兼容性处理
- **TensorRT**：FP16/INT8 部署与 Plugin 自定义层开发

## 四、AB 实验与归因分析
### 1. 实验设计与统计学基础
- **假设检验**：P 值与置信区间的正确解读
- **分层实验**：解决正交实验中的流量饥饿问题
- **SRM（样本比率失配）**：如何发现并修复实验分流不均

### 2. 归因模型
- **Shapley Value**：在推荐系统中的特征贡献度计算
- **马尔可夫链归因**：渠道转化路径分析