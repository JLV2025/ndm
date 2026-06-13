---
name: 天龙五步
description: 构建 ReactFlow 端口拓扑画布 — 天龙五步：布局 → Handle → 管道连线 → 颜色发光 → 自动居中。适用于网络设备 LLDP 邻居可视化。
disable-model-invocation: false
---

# 天龙五步

当用户需要构建网络设备端口连接图（基于 LLDP/CDP 邻居数据，ReactFlow 渲染）时，按以下规则执行。

## 设计原则

- 所有设备方框颜色和发光效果必须通过 `getNodeColors()` 统一驱动，禁止手写单色拼发光
- 布局/Handle/连线三步严格顺序执行
- 空层自动折叠上移

## 第一步：布局规则

### 层定义
| 层 | 内容 | 条件 |
|----|------|------|
| L1 (WAN) | Router, Firewall, SD-WAN | 有 WAN 设备时 |
| L2 (Core) | 上游核心交换机 | neighbor_notes 含"核心"/"core" |
| L3 (Selected) | 选中设备本身 | 始终存在 |
| L4 (Access/End) | 下级交换机 + 端点设备 | 有设备时 |

### 核心交换机场景 (isCore = true)
```
WAN? → ★Core → Access(接入交换机+端点同层)
```

### 接入交换机场景 (isCore = false)
```
WAN? → Core(上游核心)? → ★Access → End(下级交换机+端点)
```

### 空层折叠
某层无设备时，下层依次上移。

### 堆叠展开
每个堆叠成员独立渲染为 `switchNode`，水平排列，间距 `STACK_GAP`。

### 核心检测
- 自身：`/核心|core/i.test(deviceNotes)`
- 邻居：读取 `neighbor_notes` 字段，支持 `-M1` 后缀还原原名查找

## 第二步：Handle 规则

| 设备类型 | Handle 模式 | 说明 |
|----------|------------|------|
| 交换机 | `switchNode` (上下双排) | 奇数端口 Top，偶数端口 Bottom |
| 首层非交换机 | Bottom only | 仅下部 handle |
| 末层非交换机 | Top only | 仅上部 handle |
| 端点设备 | Top only | 强制 top |

## 第三步：管道连线规则

### 管道系统
- **水平管道**：N+1 条（每层上方 1 条 + 最下层下方 1 条）
- **垂直管道**：选中设备行最右侧设备右边缘 + 100px
- 管道用虚线显示（可选）

### 端口→管道映射
- Top handle → `pipe[row]`（本层上方管道）
- Bottom handle → `pipe[row+1]`（本层下方管道）

### 路由逻辑
```
同管道：源→垂直进管道→水平到目标X→垂直到目标
跨管道：源→垂直进源管道→水平到垂直管道→垂直管道内上行/下行→目标管道→水平到目标X→垂直到目标
```

### 方向与颜色
- 物理连线始终从高层设备出发（行号小的层）
- 连线颜色取高层设备颜色（优先级：WAN > Core > Access > End）
- `swap` 标志：邻居在更高层时反转路径端点
- 转角用二次贝塞尔圆弧（半径 12px）

### 过滤
- LAG 逻辑接口：`/^lag\s*\d/i`
- 自身引用：`device_name === currentDevice`
- 堆叠互联线：`isStackLink(description)`

## 颜色系统

```typescript
// constants.ts 中定义工业级三件套
export interface NodeColorSet {
  fill: string   // 深色填充
  glow: string   // 发光色
  border: string // 边框色
}

// 统一取色
const nc = getNodeColors(displayType)  // 'core-switch' | 'access-switch' | 'router' | ...

// 使用模板（SwitchNode）
borderColor: nc.border,
bgcolor: `${nc.fill}2A`,
boxShadow: `0 0 32px ${nc.glow}99, 0 4px 16px ${nc.glow}66, inset 0 1px 0 ${nc.glow}20`,
// 图标颜色
color: nc.glow,
filter: `drop-shadow(0 0 6px ${nc.glow}80)`,
```

## 第四步：自动居中适配

```typescript
useEffect(() => {
  if (!rfInstance.current || nodes.length === 0) return
  const timer = setTimeout(() => {
    rfInstance.current?.fitView({ padding: 0.08, duration: 300, maxZoom: 1.5 })
  }, 60)
  return () => clearTimeout(timer)
}, [deviceName])
```

## 布局常量参考

```typescript
const SWITCH_W = 368; const SWITCH_H = 125
const NEIGHBOR_W = 252; const NEIGHBOR_H = 83
const MANAGED_W = 288; const MANAGED_H = 83
const COMPACT_W = 172; const COMPACT_H = 42
const ROW_GAP = 140; const DEVICE_GAP = 44; const STACK_GAP = 24
const SIDEBAR_W = 104
```

## 应用到新项目

1. 复制 `DEVICE_COLORS` / `NODE_COLORS` / `getNodeColors()` 到项目的 constants
2. 复制 `PipeEdge` + `buildRoundedPath()` 管道组件
3. 复制 `SwitchNode` + `NeighborDeviceNode` 节点组件
4. 按三个函数模板实现：`resolveLayers()` → `resolveHandles()` → `resolveEdges()`
5. 加 `useEffect` + `fitView` 自动居中
6. 图例放在左侧 `SIDEBAR_W` 宽度的纵向面板

## 相关文件（本项目的参考实现）

- `frontend/src/components/topology/PortTopologyCanvas.tsx` — 完整实现
- `frontend/src/shared/constants.ts` — 颜色、图例、过滤函数
- `frontend/src/types/topology.ts` — NeighborNode 类型定义
- `.wolf/cerebrum.md` — 三步规则完整文档
