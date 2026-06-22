# Cerebrum

> OpenWolf's learning memory. Updated automatically as the AI learns from interactions.
> Do not edit manually unless correcting an error.
> Last updated: 2026-06-07

## User Preferences

<!-- How the user likes things done. Code style, tools, patterns, communication. -->

## Key Learnings

- **Project:** ndm
- **Description:** 通过 SSH 登录 Cisco 和 Aruba 交换机，收集配置和日志，保存到本地并进行分析。
- Aruba CX VSF 堆叠必须用 `show vsf detail`（非 `show vsf`），输出中 `Member ID` 列出所有成员，每个成员有独立 `Serial Number`。`show vsf`（不带 detail）不含序列号信息。
- Cisco IOS `show logging` 无法限制条目数（不像 Aruba CX `show logging -r -n 100`），全量收集太慢，已跳过 Cisco 日志收集。
- Aruba 序列号正则应使用 `[A-Za-z0-9]+`（支持大小写），与 Cisco 正则保持一致。
- `version_extractor.py` 中 `VersionExtractor` 类为零调用方死代码，序列号/版本提取逻辑已由 `collector_service.py` 中独立函数取代，可后续删除。
- [2026-06-09] CDP/LLDP 邻居收集：每台设备执行 `show cdp nei` + `show lldp nei`，NeighborParser 自动识别 4 种格式（Cisco CDP 跨行、Cisco LLDP 列合并、Aruba CDP、Aruba LLDP SYS-NAME），去域名后正则校验 `[A-Z]{3}D\d[A-Z]{3,5}\d{2}`。
- [2026-06-09] ConfigParser 补充 SDW/FWL：CDP/LLDP 无法发现 SD-WAN 和防火墙设备 → 从 running-config 端口描述中解析 `SDW`/`FWL` 类型设备，追加到 neighbors.json。
- [2026-06-09] 多设备拓扑三层布局：WAN (RTW/SDW) → Core (notes 以 "core" 开头且类型 SWI) → Access (其余)。手工分层居中排列，层间 200px。
- [2026-06-09] 拓扑图连线智能路由：计算源/目标节点坐标差，|dy|>|dx| 垂直连线（顶/底 Handle），|dx|≥|dy| 水平连线（左/右 Handle），保持最短路径避绕设备。
- [2026-06-10] 设备批量导入：CSV 格式，后端 `POST /devices/batch-import` + `GET /devices/batch-import/template`，前端 ImportDialog 拖拽上传，重名跳过不覆盖。
- [2026-06-10] CSV 模板文件名：`NDM_Device_Import_Template.csv`，前后端需统一。
- [2026-06-10] 下载 Blob 文件时 `URL.revokeObjectURL()` 不能在 `a.click()` 后立即调用（文件未写入即释放），需先 `document.body.appendChild(a)` 挂 DOM 再延迟 `setTimeout` 1 秒释放。
- [2026-06-10] 拓扑图三层分类：RTW、SDW、FWL 均为 WAN 层（最上排），Core 中间，Access 最下排。
- [2026-06-10] 仪表盘设备清单堆叠拆分：序列号逗号分隔 → 物理成员各一行（SWI01-01, SWI01-02），逻辑设备名不再显示。
- [2026-06-10] LocationFilter 组件新增 `showAll` prop，拓扑图传 `false` 隐藏 ALL 按钮，设备管理保留默认 `true`。

- [2026-06-10] 设备批量导入：CSV 格式，name/ip/type 必填，platform/location/notes/uplink_ports 可选。模板下载端点 `GET /devices/batch-import/template`，导入端点 `POST /devices/batch-import`。重名设备跳过不覆盖。FastAPI 中批量导入路由必须在 `/{name}` 参数化路由之前定义，否则 `batch-import` 会被当作设备名匹配。

- [2026-06-13] **端口连接图绘制三步规则** (适用于所有端口连接图, 执行顺序严格):
  ## 第一步: 布局规则
  1. 层定义: L1=WAN(router/firewall/sdwan), L2=上游核心交换机, L3=选中设备, L4=下级交换机+端点
  2. 核心选中(isCore): WAN? → ★Core → 接入交换机+端点(同层)
  3. 接入选中(!isCore): WAN? → 上游核心? → ★Access → 下级交换机+端点(同层)
  4. 空层折叠: 某层无设备则下层上移
  5. 堆叠展开: 每个成员独立switchNode, 水平排列
  6. 邻居交换机识别: neighbor_notes含"核心"/"core"=上游核心; 堆叠名(-M1)需还原原名查找
  7. 设备方框颜色+发光: SwitchNode用getNodeColors(displayType)取fill/glow/border三件套; NeighborDeviceNode用getNodeColors(toDisplayType); 禁止手写单色拼发光
  ## 第二步: Handle规则
  7. 交换机: 始终 switchNode, 上下两排 handle, 奇数Top/偶数Bottom
  8. 首层非交换机: bottom only; 末层非交换机: top only; 端点强制 top
  ## 第三步: 连线规则
  9. 水平管道: N层→N+1条(每层上方1条+最下层下方1条); 垂直管道: 选中设备行最右+100px
  10. 高层设备出线(优先级 WAN>Core>Access>End), 用高层设备颜色
  11. 端口出线: top handle→最近管道(pipe[row]); bottom handle→pipe[row+1]
  12. 同管道两侧: 源→垂直进管道→水平到目标X→垂直到目标
  13. 跨管道: 源→垂直进源管道→右转垂直管道→上行/下行→目标管道→水平到目标X→垂直到目标
  14. 转角: buildRoundedPath(二次贝塞尔, 半径12px); 管道内线段可重合
  ## 过滤
  15. LAG(isLagInterface), 自身引用, 堆叠线(isStackLink)

## Do-Not-Repeat

- [2026-06-10] **拓扑图 LocationTopologyCanvas 遗留问题**：
  1. 少数 location（如 BJQ）连线不全 — Handle 匹配机制不稳定，需仔细调试 sourceHandle/targetHandle ID 与 edg e 的对应关系。
  2. 多设备不同层时，核心交换机水平方向未居中 — 行宽计算需以所有行中最大宽度为基准，每行节点居中偏移。
  3. 堆叠设备容器内文字未垂直居中、成员间缺少视觉间隙 — 堆叠成员应 `justifyContent: 'center'` + `gap`。
  4. 一个设备在一个方向有多根连线时，共用单个 Handle 导致部分重合 — 需要每边多个均匀分布的 Handle，并在 edge 中分配不同 handle ID。
  5. ReactFlow `fitView` 在切换 location 时未重新计算 — 需 `key={selectedLocation}` 强制 remount。
  当前代码状态：Handle 已简化为每边 1 source + 1 target（st/tt/sb/tb/sl/tl/sr/tr），居中已尝试按 maxRowW 偏移但可能仍有错位。下次修复从 `LocationTopologyCanvas.tsx` 的 `layRow` 和 edge 生成部分入手。

- [2026-05-13] 前端密码 decode 不要使用 `escape()` 函数。`escape()` 会将 `%` 编码为 `%25`，导致 `encodeURIComponent` 的结果被双重编码。正确做法：`decodeURIComponent(atob(value))`
- [2026-05-13] `extract_software_version` / `extract_serial_number` 中 Aruba 设备类型判断不要只写 `aruba_osswitch`，需同时覆盖 `aruba_aoscx`。使用辅助函数 `_is_aruba_device()` 统一判断。
- [2026-05-13] `DeviceConnection` 创建时务必传入 `platform` 字段，否则 Aruba CX 系列（6300/6400/8xxx）无法被识别为 `aruba_aoscx` 驱动，导致 `send_command` 提示符匹配失败。
- [2026-05-13] 前端收集配置 API 调用时，后端返回 `success: false` 表示收集失败（HTTP 状态码 200），前端需检查 `data.success` 字段并抛出错误，错误信息从 `data.detail` 或 `data.error` 获取。
- [2026-05-13] `settings.yaml` 中的 `data_root` 不能是相对路径，必须是项目根目录的绝对路径，否则后端服务工作目录变化会导致数据保存到错误位置。
- [2026-05-13] 用户在登录页面输入的账号和密码就是用来登录设备的 SSH 凭证，前端 session 和后端收集都使用这些凭据进行 SSH 认证。
- [2026-06-06] 全局颜色替换（如 `#22C55E` → `#2DD46E`）时，必须同时 grep 两种 rgba 格式：带空格 `rgba(34, 197, 94,` 和不带空格 `rgba(34,197,94,`。单次 grep 会遗漏不带空格的变体，导致遗漏替换。
- [2026-06-06] `openwolf designqc` JPEG 截图对 OLED 暗色主题（背景 `#020617`）压缩后几乎全黑，无法用于视觉审查。替代方案：用 Playwright MCP `browser_take_screenshot` type=png 直接捕获。
- [2026-06-06] Vite dev server (port 3000) 在 Emotion 环境下抛 `ReferenceError: init_emotion_react_browser_development_esm`。解决：用 `npx vite preview --port 4173` 以生产模式预览，绕过开发模式 Emotion 错误。
- [2026-06-06] MUI `createTheme` 中 Card/Paper 的全局样式覆盖必须放在 `components.MuiCard.styleOverrides.root` 路径下，否则 box-shadow/transition 不生效。
- [2026-06-06] Edit 工具要求文件必须在当前 session 中已被 Read 过。批量跨文件编辑前，先逐文件 Read 再 Edit，否则工具调用全部失败。
- [2026-06-07] React Flow 自定义节点中 Handle 必须是节点的直接子元素（不能嵌套在绝对定位的子 Box 内），否则位置计算错误。端口视觉和 Handle 应分离渲染。
- [2026-06-07] React Flow Controls 在暗色主题下默认显示白条，需通过 `<style>` 注入 CSS 覆盖 `.react-flow__controls-button` 的 `background`/`fill`/`svg fill`。
- [2026-06-07] React Flow `smoothstep` 边类型通过 `pathOptions: { borderRadius, offset }` 可实现连线绕行，`nodesDraggable` + `elementsSelectable` 开启拖拽调整布局。
- [2026-06-07] 端点聚合：31 个 Phone-* 不应各占一个节点（连线密集重叠），合并为 `电话 ×31` 一个紧凑节点（`compact: true`），节点 200×58px，不画端口视觉只保留 Handle。
- [2026-06-07] 堆叠交换机水平居中公式：`switchStartX = (maxW - switchesW) / 2`，然后 `switchStartX + i * (CENTER_W + H_GAP)`。不能从 0 开始。
- [2026-06-07] 所有外部设备只能分 `top` 和 `bottom` 行，不能有 `center` 行（与交换机同行会导致连线水平穿过交换机节点）。
- [2026-06-07] React 组件中 `const` 对象（如 `btnSx`）定义在组件函数 `}` 之后会导致 TDZ `ReferenceError: Cannot access 'k' before initialization`。SX 常量必须放在组件函数之前，或在 JSX 中直接 inline。
- [2026-06-07] Vite build 必须在项目根目录（含 `index.html`）执行，不能在 cwd 不对时运行，否则报 `UNRESOLVED_ENTRY`。务必先 `cd frontend` 再 `npx vite build`。
- [2026-06-13] 端口拓扑图数据源优先级：CDP/LLDP neighbors.json（网络设备物理端口）> ConfigParser running-config（端点设备），双源均在后端过滤 LAG 虚接口
- [2026-06-13] 交换机颜色发光统一用 `getNodeColors(displayType)` 取 fill/glow/border 三件套，禁止 SwitchNode 手写单色拼发光
- [2026-06-13] `neighbor_interface` 字段由后端反查邻居 CDP/LLDP 获取远程端口，前端端口标签 + handle + 堆叠成员分配均以此为准
- [2026-06-13] 端点计数用 `ifaces.length`（每端口=一个物理端点）而非去重设备名，因 ConfigParser 可能返回统一 device_name
- [2026-06-13] `except:pass` 静默吞异常 → 所有异常处理至少 `logger.warning()`
- [2026-06-13] UI/UX 审查工具：`ui-ux-pro-max` 技能可用于搜索设计风格/配色/字体；Playwright browser_evaluate 可提取实时字号/颜色/间距数据
- [2026-06-09] React Flow `useReactFlow()` 需要 `ReactFlowProvider` 祖先组件。自定义节点和控件面板应作为 `Panel` 放入 `<ReactFlow>` children 内，不要用 `ReactFlowProvider` 包裹外部 DOM。
- [2026-06-09] 自定义 ReactFlow 节点必须包含 `<Handle>` 元素（即使 `visibility: 'hidden'`），否则边无处可连，画布上不显示连线。
- [2026-06-09] Windows 批处理 `for /f` 内嵌 pipe `^|` + 重定向 `2^>nul` 在 Win11 cmd.exe 下转义不稳定。正确做法：先在 `for` 外执行 `command | findstr > tempfile`，再 `for /f` 读临时文件。
- [2026-06-09] start.bat 端口检测不能依赖 `findstr /C:":%PORT%"` 做精确匹配——虽不会误匹配 `:18002`（因为 `:8002` 不是 `:18002` 的子串），但 IPv6 地址 `[::8002]:port` 可能被误命中。应加入 `LISTENING` 二次过滤。

## Key Learnings

- **Project:** ndm
- **Description:** 通过 SSH 登录 Cisco 和 Aruba 交换机，收集配置和日志，保存到本地并进行分析。
- Aruba CX VSF 堆叠必须用 `show vsf detail`（非 `show vsf`），输出中 `Member ID` 列出所有成员。
- Cisco IOS `show logging` 无法限制条目数，全量收集太慢，已跳过 Cisco 日志收集。
- `version_extractor.py` 中 `VersionExtractor` 类为零调用方死代码，可后续删除。
- Aruba CX 交换机（6300/6400/8320/8xxx）使用 `#` 提示符，必须用 `aruba_aoscx` 驱动。
- Netmiko 4.6.0 移除了 `look_for_keys`、`allow_agent` 参数。
- 前端密码存储：`encodeURIComponent` + `btoa` 编码，`atob` + `decodeURIComponent` 解码。
- [2026-05-17] LCS diff 使用标准 DP 算法。Diff 双面板同步滚动使用 `useRef` + `onScroll` + `requestAnimationFrame`。
- [2026-06-07] 方向键盘移动节点通过 `offsets` state（`Record<string,{dx,dy}>`）实现，`positionedNodes` useMemo 将偏移应用到原始节点坐标，不影响基础布局计算。移动后 fitView 需重新触发。
- [2026-06-07] ReactFlow 连线点击高亮：`onEdgeClick` 回调中按 `edge.target` 匹配末端节点 ID，`finalEdges` useMemo 中非目标连线设 `opacity: 0.06` 且移除 `markerEnd`，目标连线 `strokeWidth: 5` + `animated: true`。
- [2026-06-07] ReactFlow 内置 `MarkerType.ArrowClosed` 的 `width`/`height` 参数只影响 viewBox 宽高比，不会改变箭头实际外观形状。要真正改变箭头需自定义 SVG `<marker>` + `<defs>` 注入。
- [2026-06-07] ReactFlow `Controls` 组件内置 4 个按钮：+（放大）、-（缩小）、fit view（适配视口）、lock（锁定视口禁止平移缩放）。锁按钮点击后画布无法缩放/平移，用于固定布局。
- [2026-06-07] 前端 preview 模式（`vite preview`）不代理 API，需改 `api.ts` 中 `API_BASE = import.meta.env.PROD ? 'http://localhost:8002/api' : '/api'`，所有 fetch 调用需加 `credentials: 'include'`，后端 CORS 需允许 preview 端口。

## User Preferences

- [2026-06-07] 拓扑图中端点设备（Phone-*, Printer-*, AP 等）应聚合为一个节点，标注数量（如 `AP ×6`），节省画布空间。
- [2026-06-07] 堆叠交换机必须水平中线对齐。
- [2026-06-07] 导航栏中"拓扑图"应改名为"端口连接图"，预留真正的多设备互联拓扑图功能留给后续。
- [2026-06-07] 图例应放在画布左侧纵向排列（小色块 + 小字体），不应放在底部或顶部横排遮挡内容。
- [2026-06-07] 节点方向键盘应放在画布左下角 zoom 控件上方，不重叠。
- [2026-06-09] CDP 和 LLDP 邻居信息每台设备都要收集，不区分 Cisco/Aruba — 两个命令都跑避免遗漏。
- [2026-06-09] `cdp-neighbors.raw` 和 `lldp-neighbors.raw` 只保存不显示，API 和前端只用解析后的 `neighbors.json`。
- [2026-06-09] Core 层判定：设备 notes 以 "core" 开头（不区分大小写）即为核心交换机，不管前缀字符串多长。
- [2026-06-09] 多设备拓扑是网状图，只选 location 不需要选具体设备。左侧独立「拓扑图」导航入口。
- [2026-06-09] 导出功能：PNG 图片 + Visio .vdx 格式，两个画布都要有。
- [2026-06-09] 方向键盘在拓扑图和端口连接图上风格统一（Material 图标按键）。

## Decision Log

<!-- Significant technical decisions with rationale. Why X was chosen over Y. -->

- [2026-06-12] Vite 8 与 MUI 5 / emotion 11.14 不兼容（init_emotion_react 未定义）。降级到 Vite 7.2.7 + emotion 11.13.5 解决。
- [2026-06-12] taskkill //F //IM node.exe 会杀全部 Node 进程（含 MCP 服务），应用 PID 精准杀或 taskkill //FI "WINDOWTITLE eq vite*"
- [2026-06-12] 端口连接图与网络拓扑图应独立画布，端口连接图侧重端口编号 Handle + 分层布局

## User Preferences
- [2026-06-12] 设备方框需显示设备名字 + 型号 + IP（如有）
- [2026-06-12] Handle 仅上下边框，禁止左右
- [2026-06-12] 连线颜色 WAN 优先 > 核心 > 接入
- [2026-06-12] 堆叠交换机间距缩短以示区别
- [2026-06-18] 拓扑图布局右对齐（非居中），最长层为锚点，其他层右边缘对齐
- [2026-06-18] 设备角色以 YAML notes 标注为准（"Core Switch"/"Access Switch"/"Cascade Switch"），辅以后端核查

## Key Learnings
- [2026-06-18] 设备命名规范：{site3}{room2}{type3}{num2}，如 PVGD1SWI02。同一机房同一类型交换机编号从 01 开始，SWI01 不一定是核心
- [2026-06-18] 接入交换机判断硬条件：必须直连核心交换机（LLDP）。串接交换机判断（排除法）：不直连核心 + 编号偏大
- [2026-06-18] 水平管道应按 handle 实际位置按需生成，不固定 N+1 条。三层 WAN→Core→Access 只需两条管道（层间中点），首层上方和末层下方无 handle 则不需要管道
- [2026-06-18] 管道索引映射从硬编码 `pipe[row]` 改为查找表 `row2pipe[].topPipeIdx/.bottomPipeIdx`，灵活适配不连续管道

## Key Learnings
- [2026-06-18] ReactFlow v12 默认给所有节点加 `nopan` CSS class，点击到节点区域会阻止画布拖拽。解决：`nodesDraggable={false}` + `panOnDrag`，所有拖拽统一变成画布平移
- [2026-06-18] ReactFlow `fitView` prop 在每次 nodes/edges 引用变化时重新执行动画，与用户交互冲突导致拖拽失效。用 `useEffect` + `ref` 防重机制代替 prop 驱动
- [2026-06-18] 右对齐布局后节点集中右侧，空区域减少，用户更容易点到节点 (nopan)，拖拽失效更明显
- [2026-06-18] `canvasW` 在右对齐布局中仍需保留——`startX = canvasW - lw - RIGHT_PADDING` 依赖它计算右对齐偏移，删除会导致坐标漂移

- [2026-06-22] 设备名正则不应硬编码 `[A-Z]{3}` 站点前缀——含数字的站点（KR3, KR5）无法匹配。改为以设备类型码（SWI/RTW/FWL/WLC/SDW/QIS）为锚点，固定10位宽度：`\w{3}\w{2}(类型码)\d{2}`
- [2026-06-22] CDP输出端口名为短格式（Gi1/1/2），ConfigParser running-config 为长格式（GigabitEthernet1/1/2），必须用 `_normalize_port_name` 统一为短名再做去重 key
- [2026-06-22] 邻居去重三关：① 端口名规范化（Cisco 长→短名）；② `(port, neighbor_name)` 去重 key；③ admin down 端口过滤（解析 running-config 中 shutdown 标记）
- [2026-06-22] ConfigParser 补充逻辑不应跳过 switch/router 类型——CDP/LLDP 可能因未启用而空输出，`seen_ports` 去重已足够防止重复。硬跳过导致无 CDP 数据时丢失全部邻居

## Do-Not-Repeat
- [2026-06-12] 删除常量后遗留引用导致 ReferenceError → 改前先 grep 全文件引用的常量名
- [2026-06-12] Vite 8 + emotion 11.14 白屏 → 生产项目不用最新版，等生态跟上
- [2026-06-18] ReactFlow `nodesDraggable` 和 `panOnDrag` 同时启用导致节点拖拽与画布拖拽冲突 → 关闭 `nodesDraggable`，仅保留 `panOnDrag`
- [2026-06-18] `fitView` prop 不可与交互并存 → 用受控的 `useEffect` 替代 `fitView` prop
- [2026-06-22] 设备名正则以字母集 `[A-Z]` 硬编码 → 改用 `\w` 放宽 + 锚定类型码，适应含数字站点
- [2026-06-22] CDP/LLDP 和 ConfigParser 端口名格式不一致（Gi1/1/2 vs GigabitEthernet1/1/2）→ 统一规范化后再去重
- [2026-06-22] ConfigParser switch/router 类型邻居直接跳过 → CDP 无输出时邻居全丢；`seen_ports` 去重已足够
