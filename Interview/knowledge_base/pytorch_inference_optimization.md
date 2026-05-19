# PyTorch 模型部署与推理加速实战

## 一、模型导出与跨框架转换
### 1. TorchScript（JIT）
- **Tracing vs Scripting**：Tracing（记录执行轨迹，条件分支无效）；Scripting（解析代码 AST，支持控制流）
- **导出与加载**：`torch.jit.trace` / `torch.jit.script`，保存为 `.pt` 文件
- **适用场景**：C++ 服务端部署（LibTorch）

### 2. ONNX（Open Neural Network Exchange）
- **导出 ONNX**：`torch.onnx.export`，动态轴设置
- **算子兼容性检查**：遇到不支持的算子如何处理？自定义算子注册
- **ONNX Runtime 推理**：支持 CPU、CUDA、TensorRT 后端

### 3. TensorRT 深度优化
- **构建引擎**：从 ONNX 或直接使用 TensorRT Python API 构建
- **FP16 / INT8 校准**：校准数据集准备与量化误差控制
- **动态 Shape 支持**：`OptimizationProfile` 设置最小/最优/最大维度

## 二、推理服务架构设计
### 1. 模型服务框架对比
- **TorchServe**：PyTorch 官方，支持版本管理、热加载、自定义 Handler
- **TensorFlow Serving**：支持 REST/gRPC，成熟稳定
- **Triton Inference Server**：多框架支持、动态批处理、并发模型执行

### 2. 在线推理流水线
- **预处理与后处理**：在服务端还是客户端完成？特征转换一致性问题
- **批处理请求合并**：Dynamic Batching 提高 GPU 利用率
- **负载均衡与弹性伸缩**：K8s HPA 基于 GPU 利用率

### 3. 低延迟优化技巧
- **算子融合**：Conv + BatchNorm + ReLU 融合
- **内存复用**：减少显存分配开销
- **CUDA Graph**：将整个推理流程固化，减少 kernel 启动开销

## 三、模型量化与剪枝实践
### 1. PyTorch 量化方案
- **Post-Training Quantization（PTQ）**：训练后量化，无需额外训练
  - **静态量化**：需校准数据集，适用于 CNN
  - **动态量化**：仅量化权重，适用于 LSTM/Transformer
- **Quantization-Aware Training（QAT）**：模拟量化噪声，精度更高

### 2. 剪枝与蒸馏联合优化
- **非结构化剪枝**：权重置零，依赖稀疏计算库加速
- **结构化剪枝**：移除整个卷积核/神经元，直接缩小模型体积
- **知识蒸馏实战**：用大模型 Logits 软化标签训练小模型

## 四、GPU 推理性能剖析与优化
### 1. Nsight Systems / Nsight Compute
- **时间线分析**：定位 CPU-GPU 同步点、内存拷贝瓶颈
- **Kernel 级优化**：查看 Warp 占用率、共享内存 Bank Conflict

### 2. 多流并发
- **CUDA Stream**：将无关的推理请求分配到不同流，实现 Kernel 执行与数据拷贝重叠

### 3. 混合精度推理
- **FP16 推理**：Volta 架构以上 Tensor Core 加速

## 五、案例：BERT 模型部署加速流水线
### 1. 基线：原生 PyTorch + Flask
- 推理延迟 ~200ms（V100），QPS 约 50

### 2. 优化一：TorchScript + LibTorch C++ 服务
- 延迟降至 120ms

### 3. 优化二：ONNX Runtime + CUDA EP
- 延迟降至 80ms

### 4. 优化三：TensorRT FP16
- 延迟降至 25ms，QPS 提升 4 倍

### 5. 优化四：Triton Dynamic Batching
- 在 QPS 300 时，平均延迟仅增加 10%