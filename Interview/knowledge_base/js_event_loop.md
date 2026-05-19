# JavaScript事件循环（Event Loop）与异步机制

## 一、为什么需要事件循环？
JavaScript是**单线程**的。这意味着同一时间只能做一件事。为了协调事件、用户交互、脚本、渲染、网络请求等任务，防止主线程阻塞，浏览器引入了事件循环机制。

## 二、执行栈与任务队列

### 1. 执行栈（Call Stack）
- **定义**：一种后进先出（LIFO）的数据结构，用于存储所有要执行的代码。
- **流程**：当调用一个函数时，其执行上下文被推入栈中。函数执行完毕后，从栈中弹出。

### 2. 任务队列（Task Queue）
- **宏任务队列**：存放宏任务的队列。
- **微任务队列**：存放微任务的队列。**微任务队列的优先级高于宏任务队列**。

## 三、宏任务与微任务

### 1. 宏任务（MacroTask）
- **包括**：`setTimeout`、`setInterval`、`setImmediate`（Node）、I/O操作、UI渲染、`MessageChannel`。
- **特点**：每次执行栈清空后，事件循环会从宏任务队列中取出**一个**任务执行。

### 2. 微任务（MicroTask）
- **包括**：`Promise.then`、`async/await`（`await` 之后的代码）、`MutationObserver`、`queueMicrotask`、`process.nextTick`（Node）。
- **特点**：在当前宏任务执行完毕后，渲染开始前，会**一次性清空整个微任务队列**。

## 四、经典事件循环流程
1.  执行全局Script代码（整体代码本身可以看作一个宏任务），将同步代码推入执行栈执行。
2.  执行过程中，遇到宏任务（如 `setTimeout`）将其回调放入宏任务队列；遇到微任务（如 `Promise.then`）将其回调放入微任务队列。
3.  **执行栈清空**（全局Script执行完毕）。
4.  **执行所有微任务**：依次取出微任务队列中的所有任务执行（如果微任务在执行过程中又产生了新的微任务，会继续执行，直到微任务队列为空）。
5.  **执行渲染**（如果需要）：浏览器进行UI渲染。
6.  **取出一个宏任务**：从宏任务队列头部取出一个任务放入执行栈执行。
7.  重复步骤4-6。

### 示例代码分析
```javascript
console.log('1'); // 同步代码

setTimeout(function() {
    console.log('2'); // 宏任务
    Promise.resolve().then(() => {
        console.log('3'); // 宏任务内部的微任务
    });
}, 0);

Promise.resolve().then(function() {
    console.log('4'); // 微任务
}).then(function() {
    console.log('5'); // 微任务
});

console.log('6'); // 同步代码

// 输出顺序：1, 6, 4, 5, 2, 3
// 解析：
// 1. 执行栈：执行1和6。
// 2. 微任务队列：[then4, then5] (因为第一个then返回undefined，第二个then注册)
// 3. 宏任务队列：[setTimeout]
// 4. 清空微任务：输出4, 5。
// 5. 取一个宏任务：执行setTimeout，输出2，此时产生微任务then3，立即执行输出3。