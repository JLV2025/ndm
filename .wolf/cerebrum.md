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
- [2026-06-22] `extract_model` 对型号去重（`if model not in models`）→ 堆叠设备多台同型号时型号数 < 序列号数。去掉去重，型号与序列号按行序 1:1 对应
- [2026-06-22] Dashboard 堆叠拆分原样复制 `model` → 每个成员显示整串逗号拼接型号。需按索引拆分 `model_list[i]` 分配各自型号
- [2026-06-24] **GTS 服务器命名规范例外**：`GTSPEKESX01` 格式 — GTS + 3位site code + 类型码(ESX/SRV/SVR) + 可选编号。与标准 `3+2+3+2` 不同，site code 占3位而非2位。后端 TYPE_MAP 已有 ESX/SRV 映射但正则未覆盖，需同步更新三处（前端 parseDeviceName、后端 neighbor_parser DEVICE_NAME_RE、后端 role_verifier _parse_device_name）
- [2026-06-24] 设备名正则变更需同步三处位置，不能只改一处：PortTopologyCanvas.tsx `parseDeviceName()`、neighbor_parser.py `DEVICE_NAME_RE` + `DEVICE_NAME_SEARCH_RE`、role_verifier.py `_parse_device_name()`

## Key Learnings
- [2026-06-30] i18n `t(key, fallback?)` 函数不支持占位符替换（如 `{total}`），需直接用 JS 模板字符串拼接
- [2026-06-30] 告警详情展示：不应 `JSON.stringify(detail, null, 2)` 显示原始 JSON，应渲染中文标签的键值对（`dl/dt/dd`），数值字段自动格式化（秒→天、百分号、数组逗号拼接）
- [2026-06-30] 拓扑变更详情特殊处理：`new_neighbors`/`gone_neighbors` 数组改为紧凑列表（绿色+图标"新增N条"、红色-图标"消失N条"），`maxHeight: 340` 可滚动
- [2026-06-30] 端口DOWN异常检测必须加邻居过滤——仅检查 `port_name IN (SELECT local_port FROM neighbors)` 的端口，普通终端口（Fa0/2 之类）不产生告警
- [2026-06-30] 种子数据 `_seed_remediation_hints` 用 COUNT 检查已有记录，已有数据不覆盖 → 修改种子文本后还需迁移（_migrate_v4）更新已有记录
- [2026-06-30] SQLite 替代文本文件现状：alerts.py + reports.py 用 SQLite；data.py + stats.py + topology.py + devices.py 仍读文件系统。topology.py 依赖 running-config.raw 和 neighbors.json，切换需小心
- [2026-06-30] `last_synced` 时间戳自动更新到 devices.yaml，每天收集后自动变更，与业务无关

## Do-Not-Repeat
- [2026-06-30] 修改种子数据文本后只改 `_seed_remediation_hints()` 不够——数据库已有记录不会更新，必须写迁移（`_migrate_vN`）UPDATE 已有行
- [2026-06-30] `taskkill //F //PID` 在 Git Bash 下需双斜杠（`//F`），单斜杠会被转义失败

## Key Learnings
- [2026-07-01] SQLite 迁移完成：topology.py、data.py、role_verifier 全部改查 SQLite。`_get_latest_running_config()` / `_get_latest_neighbors()` / `_scan_device_neighbors()` 三个辅助函数统一查询模式
- [2026-07-01] 日志时间戳规范化：Cisco `*Mar  1 00:00:00` 无年份 → 用月份映射表 + 收集时间年份补全为 ISO 8601。Aruba 已是 ISO 无需处理
- [2026-07-01] 日志去重：查上次 `collected_at`，`parse_syslog_lines()` 返回 `normalized_ts` 字段，写入前过滤低于 cutoff 的条目。首次收集回退 7 天
- [2026-07-01] 所有设备统一收集日志（取消 Cisco IOS 跳过），`show logging | tail 300`
- [2026-07-01] LLM 日志分析：OpenAI 兼容接口，优先级链降级（遍历 providers，按序尝试，全挂才报错）。发送前脱敏（设备名/IP→占位符），LLM 回复后还原。错误助记符精确匹配 `remediation_hints` 表做本地缓存
- [2026-07-01] LLM 配置：settings.yaml `llm.providers[]` 数组 + 环境变量 `LLM_API_KEY_N` 覆盖 + 前端设置页面三种方式。API key 保存时脱敏显示（`****`），已脱敏的值不覆盖旧 key
- [2026-07-01] startup-config 完全废弃：`collect_config()` 不再执行 `show startup-config`，前端 Viewer 移除该选项。running-config 保持双轨（文件+SQLite）

- [2026-07-02] API key 保护机制：① `config/settings.yaml` 加入 `.gitignore` 永不提交 → ② 创建 `config/settings.example.yaml` 模板（api_key 为空）→ ③ `settings_loader.py` 回退链：环境变量 `SETTINGS_CONFIG_PATH` → `settings.yaml` → `settings.example.yaml` → ④ LLM provider 加载时环境变量 `LLM_API_KEY_N` 覆盖文件中的 key
- [2026-07-02] `terminal length 0` / `no page` 是 session 级命令，在 `connect()` 中发送一次即可，整个会话有效。之前每个方法都发是多余的
- [2026-07-02] Aruba CX 日志格式为 3 字段（`TIMESTAMP HOSTNAME PROCESS[PID]: MESSAGE`），严重级别在消息体内。与 Cisco syslog 的 4 字段格式完全不同
- [2026-07-02] 设备类型 `cisco_ios_router` 在 DB 中存为 `cisco_ios`（Netmiko 驱动映射），SQL 查询过滤路由器需 `IN ('cisco_ios', 'cisco_ios_router')`
- [2026-07-02] FastAPI 路由注册顺序决定匹配优先级：`/{device_name}` 会贪心匹配任意路径，分页/分析端点必须在它之前定义
- [2026-07-02] `i18n.t(key, fallback?)` 第二个参数是 fallback 字符串，不是占位符对象。模板变量必须用 JS 字符串拼接
- [2026-07-02] `t()` 的 fallback 不能含花括号（`{days}`），会导致 i18n 库尝试查找嵌套 key 失败 → 直接用字符串拼接

## Do-Not-Repeat
- [2026-07-02] for 循环中 `queue.length` 每次迭代重新求值 → `runNext()` 内部 `queue.shift()` 同步递减 length，N=2 时只启动 1 个 worker。**必须预计算**：`const n = queue.length; for (i=0; i<n; i++)`
- [2026-07-02] 删除函数前必须 grep 全仓确认无调用方 → `collect_all_devices_parallel` 删除后 collector.py 仍 import 调用，运行时段错误
- [2026-07-02] `_set_progress("connecting")` 默认 `progress=0` 会覆盖上一步 ping 的进度 → 步骤切换时传入当前百分比 `_set_progress("connecting", progress=current_pct)`
- [2026-07-02] SSE `onerror` 不能一概而论：收到数据后断连 → 报错；从未收到数据 → 让 EventSource 自动重连（后端可能尚未启动）
- [2026-07-02] `total_cmds` 防御性重算中混用 `device_type` 和 `effective_type` → 应统一使用探测后的实际类型
- [2026-07-02] `try { await Promise.all() } setBatchRunning(false)` 缺少 `finally` → worker 抛出未捕获异常时 UI 永久卡死
- [2026-07-07] N=2 批量收集总进度条不动的根因：React 18 auto-batching 把 `setBatchStatus('success') × 2` + `setBatchRunning(false)` 合并为一次渲染，进度条从未显示。N≥3 时递归 runNext 取下一设备的间隙给了 React 渲染窗口。最终方案：改为步骤级进度——每个设备的 SSE progress 实时汇总 `overallPct = sum / totalCount`，无需 flushSync/setTimeout
- [2026-07-07] `git push origin <branch>` 无错误处理和验证 → SSH 认证失败被静默忽略，第二台电脑 pull 不到更新。必须：① 检查 push 退出码 ② `git fetch` + `git log origin/<branch>` 验证远程已收到
- [2026-07-07] 收集流程将 model/version/serial_number/last_synced 写入 SQLite 但不回写 YAML，设备列表 API 只读 YAML → 这些字段在前端永远为空。修复：YAML→SQLite 统一迁移，device_dal.py 为唯一数据源
- [2026-07-07] Cisco 路由器 show version 无 `Model number :` 行，型号在处理器行：`cisco C8300-1N1S-4T2X (1RU) processor` 或 `Cisco CISCO2921/K9 (revision 1.0) with`。正则回退：`r'cisco\s+(\S+)\s*\('`
- [2026-07-07] SQLite last_synced 为 ISO 8601 (`2026-07-07T13:45:43`)，前端显示时需正则提取转为 `MM/DD/YYYY HH:MM:SS`
- [2026-07-07] Aruba VSF `extract_model` 从 `show system` 只提取一条 Product Name，但序列号有多个（从 `show vsf detail` 提取），导致前端只显示一个型号。修复：`extract_model` 后按 serial_number 数量补齐型号
- [2026-07-07] 批量收集进度条最终方案：每个设备 SSE 推送实时 progress% → `onDeviceProgress` 回调父组件更新 `BatchItemStatus.progress` → `overallPct = sum(progress) / totalCount`，按步骤平滑推进，不再依赖设备完成事件

- [2026-07-09] `device_dal._extract_fields()` 返回 10 个字段但 INSERT 需要 11 个（遗漏 `name`），导致添加设备时 SQLite `ProgrammingError: Incorrect number of bindings supplied` → HTTP 500。`update_device` 不受影响（手动追加了 name）。修复：`(data["name"], *_extract_fields(data))`
- [2026-07-09] 配置查看器 SQLite 数据流：`GET /api/data/{device}/{week}/collection` → 返回 `available_types` + `metadata`；`GET /api/data/{device}/{week}/raw/{type}` → 返回格式化文本。6 种数据类型：running-config、boot-history、logs、port-status、neighbors、config-changes
- [2026-07-09] 端口状态格式化输出：固定列宽文本表格（Port/Status/Speed/Mode/Type/Rx Mbps/Tx Mbps/Rx%/Tx%/Description），`ORDER BY port_name`
- [2026-07-09] 邻居列表格式化输出：固定列宽文本表格（Local Port/Neighbor/Type/Platform/Source/Description），`ORDER BY local_port`
- [2026-07-09] 配置变更格式化输出：汇总行（新增/删除行数） + 分组列出具体变更内容（`change_summary` JSON 数组），按组标注 `+ ` / `- ` 前缀
- [2026-07-09] 版本号方案：大版本 2，小版本用日期 `2.M.D`（如 7 月 9 日 = 2.7.9）。涉及文件：VERSION（API 动态读取）、start.bat（banner）、frontend/package.json

- [2026-07-13] 批量收集进度条：SSE EventSource 在 Vite 代理下不可靠（http-proxy 缓冲流式响应，onmessage 不触发），改用 800ms 轮询 `GET /progress/{name}` 更稳定
- [2026-07-13] `setBatchStatus` 状态转换必须 spread `prev[name]` 保留已有字段（progress/cmdDone/totalCmds），否则 `{status:'collecting'}` 覆盖掉轮询写入的数据
- [2026-07-13] `_set_progress('analyzing'/'saving')` 必须传入当前 `progress=current_pct`，不能依赖默认 `progress=0`，否则进度条会明显回退
- [2026-07-16] VSDX 导出调试关键教训：① bug-530 说颜色 `#` 前缀导致 Visio 打不开是误诊——VSDX 格式颜色用 `#rrggbb` 是对的，当时真正的问题是 StyleSheet 中 `Char.Size` 等点号表示法 ② 程序生成的 VSDX 被 Visio 视为"不受信任"文件，执行严格 schema 验证，Cell 名称不对就拒载 ③ `bpmn-to-visio` (Mgabr90) 是 GitHub 上已验证可工作的纯 Python VSDX 生成器，可直接对照其结构 ④ StyleSheet 极简（5 个 Cell，无 Section/Row）即可，复杂的 Section/Row 反而容易触发 schema 问题 ⑤ VSDX 的 DocumentSettings/Colors/FaceNames 三个空元素要按顺序出现在 VisioDocument 中 ⑥ Visio Y 轴从下往上增长，代码的 Y 轴是自上而下，需要翻转 ⑦ 1-D Shape 的连线用 BeginX/EndX 定位端点而不是 Geometry MoveTo/LineTo
- [2026-07-13] 总进度条与单设备进度条不应同步：总进度应按步骤数加权 (`sum cmdDone / sum totalCmds`)，不是简单平均设备百分比

## User Preferences
- [2026-07-09] 数据类型按钮组：仅显示实际存在数据的类型（动态渲染），不用灰掉/隐藏不可用的按钮
- [2026-07-09] 页面布局偏好紧凑：关联控件同行排列（周下拉 + 数据类型按钮同行），下拉宽度适当减半不撑满

## Key Learnings
- [2026-07-21] 拓扑图设备类型应从设备名提取（如 `RTW`→router），而非 DB 的 Netmiko 驱动名。DB `type` 字段存的是驱动名（`cisco_ios`），不含设备角色信息。`neighbor_parser._extract_type()` 是设备名→类型的唯一事实来源，`_map_device_type` 应直接复用。
- [2026-07-21] CDP/LLDP 双向边合并：按设备对分组后分离 fwd/rev 方向，端口配对按索引对应（`fwd[i] ↔ rev[i]`）。SQLite 无 ORDER BY 时顺序不确定，多端口 LAG 场景下索引配对可能错位，但单链路始终正确。
- [2026-07-21] 设备改名 API：`PATCH /api/devices/{name}` 支持 `{"name": "new_name"}`，API 层 `device_exists` 预检查 + DAL 层 `IntegrityError` 捕获双重防护，并发冲突返回 409。
- [2026-07-21] `if new_name and ...` 在 Python 中把空字符串当 falsy，应写 `if new_name is not None and ...` 避免未来校验器变化导致空字符串绕过检查。

## Do-Not-Repeat
- [2026-07-21] `_extract_type` 返回的是类型值（`"router"`）不是类型码（`"RTW"`），不要对其返回值再做 `TYPE_MAP[code]` 二次查表。
- [2026-07-21] DAL 层 `UPDATE` 后应检查 `cursor.rowcount > 0`，不能无条件 `return True`。WAL 模式下并发场景可能导致 WHERE 匹配 0 行。
- [2026-07-21] 类型提取逻辑全局共 4 处重复（neighbor_parser._extract_type、topology._map_device_type、topology._compute_tier、config_parser.TYPE_MAP），新增类型相关逻辑前先查 `_extract_type` 是否可用。
- [2026-07-23] 新增数据库列时：① 更新 v1 CREATE TABLE（新数据库有列）② 写 _migrate_vN ALTER TABLE（旧数据库补齐）③ **递增 SCHEMA_VERSION 常量**，否则迁移永不触发 → 500 错误。
- [2026-07-23] **Emotion CSS-in-JS boxShadow 无法被内联覆盖**。MUI sx 的 boxShadow 通过 CSSStyleSheet.insertRule() 注入，不带 !important 却对内联样式/setAttribute/cssText 全部免疫。唯一有效方法：遍历 document.styleSheets 中的 CSSStyleRule，调用 rule.style.removeProperty('box-shadow')。html-to-image 通过 getComputedStyle 内联到克隆 DOM，必须从 CSSOM 源头改规则。
- [2026-07-23] **PNG 导出去发光终极方案**：html-to-image 的 `includeStyleProperties` 参数。只传白名单属性，`box-shadow` 和 `text-shadow` 刻意排除——getComputedStyle 不会内联到克隆 DOM，导出无发光。白名单必须补全 100+ 个 CSS 属性（flex/grid/position/transform/backdrop-filter 等），否则布局错位。比 CSSOM 操作/内联样式/正则替换 textContent 都可靠。

## Key Learnings
- [2026-07-22] Aruba CX LLDP `PORT-ID` 列就是远端端口号（如 `1/1/14`）。之前只解析了 SYS-NAME 和 PORT-DESC，漏掉了 PORT-ID。
- [2026-07-22] `html-to-image` 序列化 SVG 元素时读的是 `getAttribute('style')` 属性字符串，不是 JS `el.style` 对象。修改 JS style 对象对导出无效——必须操作 style 属性字符串。
- [2026-07-22] `EdgeLabelRenderer` 通过 React portal 渲染标签 DOM，不在 edge SVG `<g>` 子树内。查询标签时需用 `document.querySelectorAll` 而非从 edge 元素向下查找。
- [2026-07-22] CDP/LLDP 双向合并策略：合并只为补全 target_interface，绝不裁剪边。堆叠设备 CDP 数据不对称（逻辑名统一），需用 LLDP PORT-ID 确定正确的堆叠成员，避免复杂猜测逻辑。

## User Preferences
- [2026-07-22] 端点端口标签优于中点标签——网络工程师需要看"哪个端口连哪个设备"，标签靠近节点边框更方便日常维护。
- [2026-07-22] 导出 PNG 为白底浅色主题，不用 CSS filter 反转（SVG 渲染不一致），而是直接操作 DOM style 属性字符串。
- [2026-07-22] LAG 和 Port-Channel 逻辑端口在拓扑图中优先使用（高度概括），物理成员端口隐藏；端口连接图只用物理端口，排除逻辑端口。
- [2026-07-27] Aruba LLDP 用 `show lldp neighbor-info detail`（分块 KV 格式），非 `show lldp nei`（Cisco 表格格式）。
- [2026-07-27] LAG 成员关系从 `show lacp aggregates`（Aruba）/ `show etherchannel summary`（Cisco）获取，解析后存为 JSON（`lag_membership` 字段），供拓扑图合并物理链路。
- [2026-07-27] `is_logical` 字段（SQLite neighbors 表）区分逻辑端口和物理端口 — 收集层全量保留，展示层按需选择。端口名前缀 `lag*`/`po*`/`port-channel*` 自动标记 `is_logical=1`。
- [2026-07-27] Cisco CDP/LLDP 不报告 Port-Channel 逻辑口 → 从 `lag_map` 物理成员投票推断归属邻居，合成逻辑端口条目。
- [2026-07-27] LAG 端口名归一化：`lag14`→`lag 14`、`port-channel48`→`po 48`。入库 / API 层统一归一化，防止重复条目。
- [2026-07-27] 堆叠设备 LAG 扇出：逻辑端口按 `lag_membership` 中物理成员 slot 分布，扇出到每个承载成员，每条边共享 `target_interface`。
- [2026-07-27] `EdgeLabelRenderer` 标签需 `zIndex: 1000` 防止被 ReactFlow 节点层遮挡。
- [2026-07-27] 拓扑图节点宽度自适应：`max(基准宽度, 最忙侧 handle 数 × 52px)`，邻居多时自动加宽，少时自动缩回。
- [2026-07-27] 标签订阅字号：普通 14px / 高亮 16px（整体+2px）。

## Key Learnings
- [2026-08-03] LAG 逻辑条目补充逻辑不能与 running-config 解析耦合（同一 try/if 分支）——config 失败时物理成员被 lag_membership 隐藏而无逻辑条目覆盖，LAG 链路从拓扑整体消失。补充逻辑只应依赖 CDP/LLDP 邻居 + lag_map。
- [2026-08-03] LAG 投票平局（成员端口连不同邻居）不能用 max(key=...) 取插入序首个——被丢弃邻居的物理条目又被隐藏，链路消失。应保留所有最高票邻居各生成一条逻辑条目。
- [2026-08-03] Cisco 25G 端口短名存在 Tw/Twe 两种变体（show etherchannel summary 输出 Tw1/0/2，LLDP 长名归一化 Twe1/0/2），归一化映射需含幂等项 'Twe'→'Twe' 且必须在 'Tw' 之前（'Twe1/0/2' 也以 'Tw' 开头，顺序反了会双重转换）。
- [2026-08-03] Aruba LLDP detail 分块解析用「Port 键行触发新块」逐行扫描，比 re.split 按分隔线切块健壮——分隔线格式与设备实际输出不符时整段粘合成单块只留最后一条邻居。
- [2026-08-03] 扇出边 target_interface 传播只能在组内已知远端端口全部一致时进行；各成员对端不同时留空，避免 filled[0] 把别的链路的端口标到本条边。
- [2026-08-03] aruba_osswitch（非 CX ArubaOS）LLDP 命令用验证过的缩写 `show lldp nei`，不接受 Cisco 语法 `show lldp neighbors`；aruba_aoscx 用 `show lldp neighbor-info detail`。

## Do-Not-Repeat
- [2026-08-03] pytest 运行会写测试配置 backend/tests/config/test_devices.yaml → git stash 后 pop 必冲突。stash 前/后先 `git checkout -- backend/tests/config/test_devices.yaml` 丢弃测试副作用。另注意 bash cwd 在 backend/ 时 `tests/` 即 `backend/tests/`，路径要用仓库根绝对路径避免歧义。
- [2026-08-03] `git add -p` 用 stdin 传 y/n 时，回答数必须等于当前 hunk 数——分次提交后 hunk 数递减，先 `git diff | grep -c '^@@'` 确认再喂 stdin，回答数不匹配会静默取消暂存。
- [2026-08-03] **端口连接图（/port-topology）真实画布是 PortTopologyCanvas 自己**（pipe 边 + FrontPanelNode 节点），`TopologyCanvas.tsx`（AggDevice 分组 + 三层 fitsThreeTier 路径）是**零引用的死代码**。修改前端画布前先 `grep -rn "组件名" frontend/src --include="*.tsx" | grep -v 自身文件` 确认实际使用路径，改错文件白做功。
- [2026-08-03] 端口 DOWN 检测数据源：`port_snapshots` 表（status_up=0）按设备最新 collection 查询；邻居条目（neighbors 表）与端口状态可能不同 collection，需各自取最新。端口名统一 `_norm_port` 后再比对。
- [2026-08-17] **DSH run_code 内嵌 PowerShell 命令的转义陷阱**：run_code 的 code 是 TS 模板字符串，命令里的反引号（`）和 `\n` 会被 TS 转义成真实换行，导致 PowerShell 或写入的 JS 脚本语法错误（本会话踩了 4 次）。正确做法：① 需要换行用 `[char]10`；② 复杂脚本用 write 工具写独立 .js/.ps1 文件再执行，不要嵌在命令里。
- [2026-08-17] PowerShell 数值常量不能以 `$` 开头跟数字（`$0.007` 会被解析为变量 `$0` 拼 .007），结果完全错误。正确做法：先赋变量 `$pCache = 0.007` 再参与计算。
- [2026-08-17] DSH 会话日志 `~/.dsh/sessions/**/session.jsonl.zstd` 是**多帧 zstd 连接**（每批事件一个独立帧），`zstdDecompressSync` 只解第一帧（约 176 字节）。需按帧头 magic 0xFD2FB528 扫描帧边界，逐帧解压拼接。解压后 usage 在 `assistant/message.data.usage`（嵌套在 data 下），统计 token 时注意 chunk/message 双写去重。
- [2026-08-17] write/edit 工具修改已存在的文件前必须先 read（fs-observation-policy），否则报错；避开办法是换新文件名。
- [2026-08-17] 当前模型 deepseek-v4-flash **不支持图像输入**，read_image 直接失败。要看运行中的网页：用 Chrome headless `--dump-dom` 抓渲染后 DOM 文本（能读页面内容）；`--screenshot` 截图只能给用户看、我看不了。
- [2026-08-17] GitHub fine-grained PAT 创建 Release 需要 **Contents: Read and write**（只读权限返回 403 "Resource not accessible"）；Classic token 勾 `repo` scope 即可。PowerShell 5.1 Invoke-RestMethod 发送含中文的 JSON body 会编码损坏（400 Problems parsing JSON）——改用 UTF-8 写文件 + `curl.exe --data-binary @file` 发送。

## Do-Not-Repeat
- [2026-08-17] 版本号禁止写死。曾有两处：Login.tsx:243 硬编码 `v2.0.0`、main.py FastAPI `version="2.0.0"`，而真实版本在根目录 `VERSION` 文件（2.8.3）。统一方案：VERSION 文件是唯一事实来源 → 后端 `_load_version()`（main.py）读取并暴露 `GET /api/version` → 前端 fetch 动态显示（App.tsx 与 Login.tsx 同模式，version 为空时不显示）。新增版本显示功能时先查是否已有 `/api/version` 调用。

## Key Learnings
- [2026-08-31] Aruba CX VSF 堆叠成员信息全部来自 `show vsf detail`：每成员节含 `Member ID` / `Type`(SKU, 如 JL726B/R8S89A) / `Model`(系列名, "Aruba 6200F 48G...") / `Serial Number`。`show system` 只显示 commander（或连接成员）的 Product Name —— 成员级型号/序列号必须解析 vsf detail。
- [2026-08-31] running-config.raw 可确认 VSF 成员型号归属：`vsf member 1 \n type jl726b` 段（真实事实：UCD member 1=JL726B 原交换机，member 2=JL725A 新加）。
- [2026-08-31] `extract_member_ids`/`extract_serial_number`/`extract_model` 三者遍历同一 vsf 输出按行序收集 → 天然 1:1 对齐。**成员提取绝不能去重**（serial 提取有去重逻辑，重复序列号时会导致对齐错位）。
- [2026-08-31] 前端堆叠拆分 guard：`member_ids 逗号数 == serial 逗号数 && 全部为数字` 才用真实 ID，否则回退序号（兼容旧数据/脏值）；真实 ID 不 pad。
- [2026-08-31] 设备管理页"离线设备"判定用**时间阈值**（device_members.last_seen < now-30天），不用"不在当前条目"（避免用户删条目误报）。

## User Preferences
- [2026-08-31] 堆叠成员显示：`-1`/`-2` 用真实 Member ID 不 pad（跳号 `-3` 原样）；用户接受最小改动方案（member_ids 补全到设备清单）而非完整角色清单建模。
- [2026-08-31] 离线设备入口放"设备管理"页（Tab 切换），同时作为彻底删除入口；不建独立页面。

## Do-Not-Repeat
- [2026-08-31] Python 函数签名：**带默认值的参数不能放在无默认值参数之前**。给 `_save_to_sqlite` 加 `member_ids: str = ""` 时插在了 `system_uptime_seconds: int | None`（无默认）前面导致 SyntaxError（bug-032）。新增可选参数应放签名末尾有默认值区域（调用处用关键字传参则位置无关）。
- [2026-08-31] `vite build` 不跑 tsc —— 前端改动验证必须显式 `npx tsc --noEmit`（项目存在存量类型错误：LocationFilter.tsx / DirectionPad.tsx / LocationTopologyCanvas.tsx，与本次改动无关）。

## Decision Log
- [2026-08-31] 物理设备身份建模：采纳"device_members 档案表（SN 主键，收集时 upsert，永不删除）+ 设备管理页离线视图"方案，而非完整角色清单（用户 YAGNI：迁移历史追踪非刚需）。离线判定 = 时间阈值（用户指定 30 天）。
- [2026-08-31] 型号显示格式：SKU+系列名（"JL726B 6200F"，用户选定），从 vsf detail 的 Type+Model 行拼装，与现有 show system Product Name 格式一致。

## Key Learnings
- [2026-09-14] 前端堆叠成员编号的唯一来源是 `deviceUtils.memberSuffixes(serialNumber, memberIds, padWidth)`：member_ids 与 serial 同序 1:1，全数字才采用真实 Member ID（不补零，跳号正确），否则回退按序号补零。Dashboard 与后续任何消费方都应调它，不要再内联拆解 member_ids。
- [2026-09-14] `device_dal.py` 是 `device_members`（物理设备档案）表的唯一入口：`list_offline_members(days)` / `delete_member(serial)`。API 层不再写裸 SQL。

## Do-Not-Repeat
- [2026-09-14] 本次 VSF 提交曾给 `deviceUtils.expandStackedDevices` 补充逻辑，但该函数与 `isStackedDevice` 全仓零调用方（死代码），Dashboard 另有内联副本 → 同一规则两处维护且序号格式已分叉（固定 2 位 vs 变长 padWidth）。**新增前端共享逻辑前先 grep 调用方**；发现零调用方的 export 直接删，不要往里加。

## Decision Log
- [2026-09-14] 成员编号规则下沉：删除死的 `expandStackedDevices`/`isStackedDevice`/`PhysicalDevice`（净 -78 行），把规则抽成具名函数 `memberSuffixes` 供 Dashboard 调用。后端 `topology.py` 的 Python 版保留（跨语言，无法共用）。

## Do-Not-Repeat
- [2026-09-14] 版本号共 **5 个手工维护位置**，改版必须全部同步，漏一个就漂移：① 根 `VERSION`（唯一事实来源，API 动态读取）② `start.bat:12` banner ③ `frontend/package.json:4` ④ `README.md:4` 徽章 ⑤ `NDM用户使用文档.html:182/867`。上次 caf4a34 只改了 ①，导致 ②③ 停在 2.8.3 长达两周（bug-047）。
- [2026-09-14] OpenWolf 钩子的 `.wolf/hooks/_session.json.<hash>.tmp` 变体未被忽略，每次会话都残留未追踪文件、污染 `git status`（原有规则只精确忽略 `_session.json` 本身）。已在 `.gitignore` 改为前缀通配 `.wolf/hooks/_session.json*` 覆盖。这些是钩子运行时临时文件，**不要提交入库**。

## Key Learnings
- [2026-09-14] **端口流量是设备报告的速率，不是我们算的差值。** 全链路：`base.py:166 collect_show_interface_utilization`（Aruba CX 用 `show interface utilization`，Cisco 用 `show interfaces | include rate|load|packets`）→ `performance.py:402/465` 解析成 `rx_mbps/tx_mbps` → `collector_service.py:922` 原样写 `port_snapshots` → `api/stats.py:88` 取每设备最新快照按 rx+tx 排序取 Top10。两种命令给的都是**速率**（Aruba 是 interval 均值，Cisco 是设备维护的 5 分钟滑动平均），原始数据里没有累计计数器可做差。全项目唯一做"与上次对比"的是 `anomaly_detector.py`（用 `prev.rx_util_pct`），**不参与流量排行** —— 排查流量相关问题时别再误以为排行榜是差值。
- [2026-09-14] 流量排行**默认只统计上行链路**：`stats.py:91` 先过滤 `is_uplink = 1`，一条都没有时才在 `stats.py:118` 回退到全部有流量端口。`is_uplink` 来自设备配置的 `device.uplink_ports`（`collector_service.py:921` 写入）。
- [2026-09-14] **Cisco 的端口↔流量归属不可靠**：`show interfaces | include rate|load|packets` 的输出**不含接口名**，`performance.py:473` 注释已自认"只能按块顺序存储"，靠 `_enrich_port_details`（`performance.py:546`）按索引与 interface status 对齐。数值本身可信，但端口名可能张冠李戴；改动 interface status 解析顺序会连带污染流量排行。Aruba 路径用端口名直接匹配，无此问题。
- [2026-09-14] **实测拆解 Cisco 索引错位的真实成因（173 vs 151）**：以 SZXD1SWI01（WS-C2960X×3 堆叠）为例，`show interfaces` 输出 **173** 块 = 157 物理口 + 16 个 Vlan SVI；`show interface status` 只有 **151** 行业务口。差异 = **16 个 Vlan SVI**（status 不列）+ **6 个 FlexStack-Plus 堆叠口**（Gi{x}/0/49-50，配置体为空，status 不列）。**子接口数量为 0** —— 不要想当然归因为 subinterface。堆叠口被排除是正确行为（跑堆叠背板流量，不该进流量排行）；但 **Vlan SVI 必须显式排除**，其计数器统计经该 SVI 路由的流量，会与物理口重复计数导致排行榜虚高。
- [2026-09-14] **修 Cisco 对齐的正解是让利用率输出自带端口名，而非再找一个"权威端口清单"命令**。`show interfaces | include ^[A-Za-z]|rate|bytes` —— 接口名行在第 0 列、其余行均有前导空格（已用 raw 文件逐行验证），故 `^[A-Za-z]` 能干净地只捞出接口名行。改用按名匹配后 `_enrich_port_details` 的索引对齐（`performance.py:546`）可弃用。Cisco 累计字节**早已在现有 raw 文件里**（`N packets input, N bytes`），只是没解析 —— Cisco 侧无需增加采集量。

## Do-Not-Repeat
- [2026-09-14] 我把 `data/{设备}/{周}/` 里只剩 `running-config.raw` 判成了"落盘逻辑坏掉、原始证据丢失"，被用户纠正：那是**双轨策略**的设计（`collector_service.py:1092` 注释明写「仅保留 running-config.raw 文件写入（双轨策略）」，`:1277` 也有呼应）。running-config 走文本文件、其余数据一律只进 SQLite。**下"这是 bug"的结论前，先 grep 代码注释和相邻行确认设计意图**，尤其是删除/保留文件这类看起来像回归的改动。

## Key Learnings
- [2026-09-14] **平台确认的端口/流量命令（团队口述 + 实测）**：
  - **列物理端口**：Cisco `show interface status`（注意：C2960X 上只列物理口，**C9500 上还会列 port-channel**，输出内容随平台变）；**Aruba 用 `show interface physical`**（当前代码 `base.py:160` 发的是 `show interface brief`，会把 lag/vlan 一起列出来，应改）。
  - **取端口流量**：Cisco **`show int counters`**（两张定宽表 In/Out，自带端口名，只含物理口，64 位累计字节）；Aruba **`show interface statistics`**（单表含 RX/TX 两组列）。
  - **Aruba 的 `show interface statistics` 绝不能加 `non-zero`**：实测 `1/1` 成员 52 口只出 74 行、缺 15 个口。后果是零流量端口没有基线，且"本轮无流量"与"端口被拔掉"**再也无法区分**。也不能加 `human-readable`（会取整成 1K/345M/2G 破坏计数器精度）。
- [2026-09-14] Aruba AOS-CX 文档里**没有** `show interface counters` 这个命令（`counters` 不是关键字，只在老式 ArubaOS / Dell W-Series 文档里出现）。AOS-CX 的是 `show interface statistics`，可选 `non-zero` / `human-readable` / `monitor`。
- [2026-09-14] Aruba 设备实测型号：**6300M / JL659A，AOS-CX 10.10.1070**。`show interface statistics` 表头只出现 1 次（不像 Cisco 会重复），且不输出独立的 lag/vlan 行；LAG 成员以 `1/1/5 - lag1` 形式标注，取 `parts[0]` 即可，`performance.py:437` 已有处理 `- lagN` 的现成逻辑。

## Key Learnings
- [2026-09-15] **端口流量口径（用户确认的业务规则，重写任何流量逻辑前必读）**：设备配置/端口状态**越新越好、新的覆盖旧的**；但**流量计数器必须按周锚定** —— 周流量 = **本周最早**一次采集的读数 − **上周最早**一次采集的读数，**一周内锁死不变**。基线绝不能用"上一次采集"：上周五多采一次会把基线推后，本周一算出来只剩 3 天、偏小一半。每个 ISO 周必须保住该周**最早**那次读数。实测采集间隔 13 分钟~21 天极不均匀，这正是必须按周锚定的原因。
- [2026-09-15] **四类设备的正确命令（全部经真机输出验证，样本在项目根目录）**：
  | 设备 | 端口清单 | 流量计数器 |
  |---|---|---|
  | Cisco 交换机 2960X/IOS-XE | `show interface status` | `show int counters` |
  | Cisco **C9500** | 同上 | `show int counters` **+ 排除 `Po*`/`Hu*`** |
  | Cisco **路由器** | `show interfaces description`（`show interface status` 在路由器上返回空） | `show interfaces stats`（取 `Total` 行的 `Chars In`/`Chars Out`） |
  | **Aruba AOS-CX** | `show interface physical`（`show interface brief` 会把 lag/vlan 一起列出来） | `show interface statistics` |
- [2026-09-15] **C9500 的 `show int counters` 会额外输出逻辑/堆叠口，必须排除**：`Po*`（Port-channel 计数器是成员口的聚合，实测 `Po1 InOctets=3.28e13`，包含会与成员口**重复计数**）；`Hu*`（HundredGigE 堆叠口，实测 `Hu1/0/27=1.37e13`，跑的是成员间背板流量，会霸榜）。其他 Cisco 型号和 Aruba 都无此问题。
- [2026-09-15] **计数器命令自带端口名且覆盖完整物理口集合，不需要 join 第二个命令**（实测：C9500 status vs counters 58=58 完全相同；Aruba physical vs statistics 52=52）。这意味着流量路径可以彻底不依赖索引对齐。
- [2026-09-15] **Cisco 路由器两份输出的命名必须归一化，且大小写有别**：`show interfaces description` 用缩写（`Gi0/0/0`/`Te0/0/4`/`SE0/1/0`/`Se0/1/0:0`），`show interfaces stats` 用全称（`GigabitEthernet0/0/0`/`TenGigabitEthernet0/0/4`/`Service-Engine0/1/0`/`Serial0/1/0:0`）。**`SE`=Service-Engine，`Se`=Serial，含义不同，映射表必须区分大小写**，不能统一 upper/lower。两份输出各 39 条、1:1 对应。
- [2026-09-15] `show int counters` 的表头行会**重复出现**（2960X 与 C9500 实测 Out 表各重复 2 次，前后带空行）。用 `mode` 变量记录当前处于 In 还是 Out 表即可天然跳过，比 `header_lines_seen` 计数法稳。Aruba 的 `show interface statistics` 表头**只出现 1 次**。

## Key Learnings
- [2026-09-15] **流量排行需要时间窗选择器（用户新增需求）**：可选近 1 周 / 近 3 周 / 近 8 周 / 近 13 周。窗口越长越准 —— 计数器差值本身是精确的，但它是对"该端口典型负载"的估计，1 周窗口容易被单个异常周（假期、备份周）带偏，长窗口把周内波动平均掉。**这个需求简化了数据模型**：`port_snapshots` 只需加 `in_octets`/`out_octets` 两列存**原始读数**，派生值全部由 API 读时按窗口算。若预计算 `week_rx_mbps` 之类，每加一档窗口就要加 3 列 + 改 INSERT + 改迁移；存原始读数则窗口增减是纯前端 + 一个查询参数的事。
- [2026-09-15] 读时算的可行性已核实：SQLite **3.50.4**（窗口函数 ≥3.25 支持）、36 台设备、最新一轮全设备端口快照 **2076 行**；8 周窗口去重后约 1.6 万行，Python 分组取首尾是毫秒级。**不要为性能牺牲灵活性**。
- [2026-09-15] 按周取基准的 SQL 用 `ROW_NUMBER() OVER (PARTITION BY device_id, port_name, week ORDER BY collected_at, cid)` 取每个 ISO 周**最早**一次采集。**排序用 `collected_at` 而不是 `week` 字符串** —— 实测 week 全部两位补零（`2026-23`…`2026-38`）字符串排序安全，但用真实时间戳不依赖补零约定。
- [2026-09-15] C9500 的排除规则**直接写死，不做可配置层**（用户确认）：全网只有**一套 C9500，且今年退休**。硬编码 `C9500_EXCLUDED_PREFIXES = ("Po", "Hu")` 即可，不值得为它建配置机制。

## Do-Not-Repeat
- [2026-09-15] 别为"看起来该可配置"的东西建配置层。我曾在计划里建议把 C9500 的 `Po*`/`Hu*` 排除规则做成可配置清单，用户否掉了：只有一套设备且即将退役。**先问清楚规模与生命周期，再决定要不要抽象** —— 单例 + 短命的东西硬编码是对的。

## Key Learnings
- [2026-09-15] 流量排行时间窗最终定为 **3 档：`1 / 4 / 13` 周**（近 1 周 / 近 1 个月 / 近 3 个月）。用户明确不要太多档位。
- [2026-09-15] **Cisco 路由器只算父口，子接口不进排行榜**：`show interfaces stats` 的 39 个块里 31 个是子接口（`Serial0/1/0:N`），过滤后剩 8 个父口。排除规则 `':' in name or '.' in name`（`:`=串口通道，`.`=VLAN 子接口，物理口名永不含这两者）。**该规则对 `show interfaces description` 与 `show interfaces stats` 两侧都要应用**，只在一侧过滤会导致集合不一致。

## Key Learnings
- [2026-09-15] **`max_versions: 10` 从未生效** —— `keep_latest_versions_per_device` / `cleanup_old_versions`（`backend/storage/file_manager.py:33/76`）**全仓库零调用点**。实测 DB 保留 16 周（2026-23~2026-38，最早 2026-06-01），设备周目录 13~14 个。**配的 10 周 < 流量排行最大窗口 13 周**，一旦接上清理，13 周档会静默缺数据。建议把 `max_versions` 提到 26（半年）。另注意 `utils/storage.py`（README/CLAUDE.md 写的路径）与 `backend/storage/file_manager.py`（实际实现）**不是同一处**。
- [2026-09-15] **邻居关系确实会落在逻辑端口上**：`neighbors` 表 `is_logical=1` 共 **272 条**（`lag1`/`lag14`~`17`/`lag49`/`lag51`/`Po1`/`Po2`/`Po3`/`Po24`/`Po48` 等）。标记本身可靠、无漏网。**但 `local_port` 未归一化**：`Po1` / `po 1` / `lag 1` / `lag1` 混用（Cisco 用 `Po`，Aruba 用 `lag`，空格与大小写不一致），**同一次采集内会并存重复** —— `KR3D1SWI01` 到 `KR3R1SWI01` 有 3 条（物理口 `Gi1/1/2` + `Po1` + `po 1`），拓扑图会重复画线。属既有问题，未在流量改造中处理。

## Key Learnings
- [2026-09-15] **数据保留与归档规则（用户确认，分层）**：
  | 对象 | 规则 |
  |---|---|
  | 配置文本文件 `data/{设备}/{YYYY-WW}/running-config.raw` | 最近 **16 周**按周；更早的**按月收缩**，该月**最后一个**版本移入 `data/{设备}/archive/{YYYY}-M{MM}/`，该月其余删除 |
  | DB `collections.running_config` | 留最近 **2 次** |
  | DB `device_logs` | 留最近 **2 次** |
  | `port_snapshots`/`neighbors` 等 | 留 **16 周**（13 周窗口 + 余量） |
  - **动机是可查看性，不是省空间**（实测约 **140 MB/年**：running_config 76 MB + device_logs 47 MB + port_snapshots 13 MB）
  - **周目录识别必须用严格正则 `^\d{4}-\d{2}$`**，否则 `2026-M09` 会被当成周目录参与清理
  - **归档是不可逆删除**，必须提供 `--dry-run` 先列清单
  - 在采集时触发，但只有存在 >16 周目录时才动作
  - "配置取月末"与"流量取周初"**方向相反但都对**：配置是状态快照（月末最有代表性），流量是累计值（需最早作基线）
- [2026-09-15] **配置文件在 DB 里也存了一份全文**（`collections.running_config`，682 份 = 22.93 MB，占 43 MB DB 的 **53%**），且 `config_changes` 的变更检测用的就是 DB 那份（`collector_service.py:717`），**不是文件**。改动配置存储相关逻辑时必须两处都考虑。

## Key Learnings
- [2026-09-15] **A1/A2 已完成**：`backend/analyzers/counter_parser.py`（三平台解析器 + 归一化 + 排除规则 + `compute_week_deltas`），`backend/tests/test_counter_parser.py`（47 用例，直接读 `backend/tests/fixtures/`）。`pytest backend/tests/` **86 passed**。
- [2026-09-15] **跑测试必须在 `backend/` 目录下**（`cd backend && python -m pytest tests/ -q`）。`pytest.ini` 在 `backend/`，测试用 `from analyzers.xxx import` 绝对导入；在项目根目录跑会 `ModuleNotFoundError: No module named 'analyzers'`。
- [2026-09-15] **Cisco 表头重复的确切次数**（分屏拆分，中间夹空行）：2960X In 表头 **2 次**（行 3/88）、Out 表头 **3 次**（行 157/175/262）；C9500 In **1 次**、Out **2 次**。用 `mode` 变量记录当前处于哪张表即可天然跳过 —— 重复表头只会把 mode 重置为同一值。**不要用「统计表头行数」的写法**（`performance.py:402-425` 的 `header_lines_seen` 就是这种），表头重复次数超预期时会把表头当数据行。
- [2026-09-15] **解析结果的三组真机基数**（可作回归锚点）：2960X counters **150** 口（status 151，多一个 `Fa0` 管理口）；C9500 counters 排除 `Po`/`Hu` 后 **48** 口（48+8 Hu+1 Po1 = 57 = status 57）；路由器 stats **7** 个父口；Aruba statistics **52** 口。**每一台的关键交叉验证**：counters 里的端口一个不漏地出现在 status 中（`counters - status == ∅`），所以流量口一定有状态元数据可挂。
- [2026-09-15] 路由器 `show interfaces stats` 的 `Total` 行 = `Pkts In, Chars In, Pkts Out, Chars Out`，取 `parts[2]`/`parts[4]`。已验证 Total 等于各 switching path 之和（`Gi0/0/1`：1039934817 = 373725508 + 666209309）。
- [2026-09-15] Aruba `show interface statistics` 表头**只出现 1 次**，样本里**没有** lag/vlan 独立行、**没有** LAG 成员标注行（`1/1/5 - lag1` 那种）。解析器仍保留了对这两种写法的兼容（端口名后只取整数 token，天然跳过 `-` / `lag1`），但**别以为样本里有**。
- [2026-09-15] Aruba 表头列名含空格（`RX Bytes`），不能按空白切分建列名表。做法：用 `header.find(列名)` 取各列名的**字符位置**，按位置排序即为取值顺序 —— 列集随型号变化（`RX Pause`/`TX Pause` 并非所有平台都有）时仍正确。

## Do-Not-Repeat
- [2026-09-15] **不要用 `cut -c1-N` 截断显示后再判断数据本身是否被截断。** 我为了压缩输出用 `sed -n '45,60p' | cut -c1-200` 看 Aruba 统计表，看到尾部行只有 5 个数值，据此断定「样本行尾列被终端宽度截断」，还写进了测试断言。实测 51 行数据**全部是 13 个 token**，毫无截断。**这是本项目第二次栽在"显示假象"上**（第一次是把 `show int counters.txt` 读短了，误判文件残缺）。**结论：判断数据形态必须用程序统计（`Counter(len(l.split()))`），不能用肉眼看过截断的输出。**
- [2026-09-15] 计划里两处数字是估的，实测要修正：路由器 stats 是 **38 个接口节**（不是 39；39 是含命令回显行的总数），其中 **31 个子接口、7 个父口**（不是 8 个父口）。写断言前先跑一遍统计脚本，别照抄计划里的数字。

## Key Learnings
- [2026-09-15] **A5/A6 完成**：`performance.py` 接线（`counters_raw`/`description_raw`/`model` 三个 ctor 参数 + `_analyze_counters` + `_enrich_counters` 按**名字**合并 + `_parse_cisco_router_description`），`collector_service.py` 接线（新增 2 条采集命令 + `total_cmds` 6 base + INSERT 19→21 列）。测试 **111 passed**。
- [2026-09-15] **A5/A6 的三组端到端基数**（无设备即可验证，全部走样本文件）：2960X 端口 151 / 带计数器 150（`Fa0` 无计数器）；C9500 端口 57 / 带计数器 48（`Hu*`+`Po1` 共 9 个被排除）；路由器 7 父口 / 带计数器 7，up=2 down=5；Aruba 端口 52 / 带计数器 52。
- [2026-09-15] `_save_data` **不需要**新增参数就能把计数器落库 —— 计数器随 `port_details` 从 `performance_results` JSON 流下来（`_save_data` 解析 JSON 取 `interface_summary.details` 传给 `_save_to_sqlite`），只需扩展 `port_snapshots` 的 INSERT。
- [2026-09-15] **计数器列绝不能过 `_safe_str`**（`collector_service.py` 里那个 `None→''` 的辅助函数）。必须 `p.get("in_octets")` 原样传，让 None 落成 NULL。这是「读到 0」与「本轮没采到」可区分的唯一保证。
- [2026-09-15] 测试里换数据库时**必须 `db.close_connection()`**。`get_connection()` 返回线程本地缓存连接，`init_db` 换 `_db_path` 后旧连接仍指向旧库文件，测试之间会串数据（表现为上一条测试的行数出现在下一条里）。

## Do-Not-Repeat
- [2026-09-15] **`_analyze_interfaces()` 开头有 `if not self.interface_lines: return 空` 的早退**。路由器的 `interface_status` 本来就是空的，加任何基于 `description_raw` 的新分支前，**必须先放宽这个早退条件**，否则新分支永远走不到。我在这里踩了一次：断言里看到 7 个端口全落到「补入」路径、status 全是 unknown，才定位到。
- [2026-09-15] `_parse_aruba_cx` 的列索引是**「最后一个匹配胜出」**（header 循环里没有 break）。`show interface brief` 表头只有一个 `Status` token 所以正常；但 `show interface physical` 的表头有 **4 个** `Status`（Link Status / Speed Status / Flow-Control Status 等），会把 status 列取到第 11 列（PoE Power），静默产出 `status='0.00'` 这种垃圾。**用户已决定保留 brief**，但若将来有人改回 physical，这里必须先修。

## Key Learnings
- [2026-09-15] **A9 完成**：分层保留落到 `backend/storage/file_manager.py`（重写，替换掉那两个从未被调用的死函数）+ `backend/scripts/retention.py`（`--dry-run` / `--db-only`）+ 采集结束时触发。测试 `test_retention.py` 17 用例。**后端 144 项全绿**。
- [2026-09-15] **`CONFIG_KEEP` 不能小于 2** —— 变更检测读的是「倒数第二次」采集的配置（`collector_service.py` 的 `SELECT running_config ... ORDER BY id DESC LIMIT 1 OFFSET 1`）。只留 1 次就没有基线，变更检测会静默失效。
- [2026-09-15] **周目录 → 月归档的映射取「该 ISO 周周一所在的月份」**（`date.fromisocalendar(y, w, 1)`）。跨月的周归属到周一那天，保证确定性；跨年也对（`2025-01` → `2024-M12`，因为 2025 年第 1 周的周一是 2024-12-30）。
- [2026-09-15] `shutil.move(src_dir, dst_dir)` 在 **dst_dir 已存在**时会把 src_dir 整个塞进 dst_dir 里面（变成 `archive/2026-M05/2026-20/`）。要移动的是**文件**，必须显式 `shutil.move(src/running-config.raw, dst/running-config.raw)` 再 `rmtree(src)`。
- [2026-09-15] **`--dry-run` 的 DB 侧报数用「跑一遍再 `conn.rollback()`」** —— 比另写一套只读统计查询可靠，且不会出现「预览数与实际执行数不一致」。前提是连接用 sqlite3 默认的隐式事务（`isolation_level` 未改成 None）。
- [2026-09-15] 归档的**收益是可查看性不是省空间**（实测约 140 MB/年）。所以「能不删就不删，只把粒度放粗」。**不做 `collections`/`port_snapshots` 行删除** —— 用户确认的四条里没有它，且这 7 张表都以 `REFERENCES collections(id)` 外键挂在 `collections` 上（无 ON DELETE CASCADE），删父行要先删子行，风险不值当。
- [2026-09-15] `config/settings.yaml` 的 `max_versions: 10` **已移除**（连同 `settings.example.yaml`）—— 全仓库只有那两个死函数读它，且 10 周 < 流量排行最大窗口 13 周，留着是个陷阱。

## Do-Not-Repeat
- [2026-09-15] 写测试断言「哪些周目录过期」时，别把周的编号顺序想当然。我写了 `weeks[:4]` 却断言「全部 8 个都被处理」，实际 `2026-23` 比 `2026-13` **新**，过期的是编号小的那批。**周编号是 {年}-{周} 两段各自定序，先排序再取前 N 个**。
- [2026-09-15] `run_retention` 一开始没暴露 `weekly_keep` 参数，导致测试没法用小的保留周数（默认 16 会让 4 个周目录的用例变成空操作）。**给阈值加参数默认值**是让清理类逻辑可测的最低成本做法。

## Key Learnings
- [2026-09-15] **A10 首轮真机验证结果**（全网 37 台一次收集）：`SZXD1SWI01` 151 口/150 有计数器 ✅、`SHAD1SWI01`(C9500) 57/48 ✅、Aruba 全部精确相等（`BJQD1SWI01` 从 107 口（含 3 个 lag）变成 104 口）✅、`BJQD1RTW01`(C8300) 7/7 ✅。保留策略执行成功：配置全文 682→72（与 dry-run 预测的置空 610 份精确吻合），日志 72162→10823。
- [2026-09-15] **累计计数器会出现「链路已断但读数巨大」的正常现象**：`KR5D1SWI01 Gi1/0/10`（描述 Servers）现在 `notconnect` 但有 1.79 PB 累计入向。这是计数器跨链路状态保留导致的。**新口径只用周差值，断线口差值为 0 自然出局** —— 这恰好反证了原 bug 的性质（老代码把累计大数当瞬时速率，才让空口霸榜）。数值可信度校验法：`Gi1/0/1`(SD-WAN 上行) 1.65 PB ÷ 1G 满速 ≈ 165 天，与运行时长吻合。
- [2026-09-15] **`show interfaces stats` 不列管理性关闭（admin down）的接口** —— 两台 ISR 上恰好只有 3 个 admin down 的口没有计数器，其余全有。这些口不承载流量，不影响排行，属预期。
- [2026-09-15] **`_PORT_ABBREV` 存在的意义是「让两侧命令对上」**：路由器上 `show interfaces description` 给缩写、`show interfaces stats` 给全称。已知必须有的映射：GigabitEthernet/TenGigabitEthernet/TwentyFiveGigE/HundredGigE/FortyGigE/FastEthernet/Service-Engine(SE)/Serial(Se)/**Loopback(Lo)**/**Tunnel(Tu)**。加新设备型号时先核对两侧命名。
- [2026-09-15] `_enrich_counters` 的「补入」兜底路径**是有诊断价值的**：全网只有 2 处触发，全部指向 `Loopback1`/`Lo1` 命名不一致。可以用「status='unknown' 且 in_octets IS NOT NULL 的端口数」当作命名对齐是否出问题的探针。

## Do-Not-Repeat
- [2026-09-15] **`backend/api/collector.py:139` 逐字段构造 `Device` 对象**，`models/devices.py` 的 `from_dict` 有 10 个字段，这里只赋了 6 个（漏 model / password / uplink_ports）。**给 Device 加新字段时，务必同时检查这个构造点** —— 漏 `uplink_ports` 让全库 `is_uplink` 恒为 0，排序静默失效，不报任何错。更稳的做法是用 `Device.from_dict(device)`。

## Do-Not-Repeat
- [2026-09-15] **shell 会话里反复冒出 0 字节垃圾文件**（本次会话三次：`(3` `1` `3` `3.25)` + `'` + `backend/2` + `backend/0` + `backend/16`）。全部是 0 字节、时间戳落在本会话内、文件名像命令片段（数字、括号、引号）。**尝试复现失败**：heredoc + `2>&1`、heredoc + `2>&1 | head` 两种最常见形式都试过，都不产生垃圾文件；原因未查明（怀疑是 Git Bash on Windows 的引号/重定向解析在特定输入下的副作用，或后台钩子）。
  **缓解措施（已生效）**：每次 `git commit` 前必跑 `git status --short`，看到 `??` 的 0 字节文件就删。三次都被这一步拦住了，没有一次混进提交。代价可控，不必深挖。

## Key Learnings
- [2026-09-15] **本日会话总结：端口流量排行改造（A1–A10 全部完成）**。5 个提交：`b87b007` 基础设施（counter_parser + v10 迁移）、`08f1569` 接线改造、`e7639b7` 分层保留、`9f61637` 真机验证修复、`692a833` 版本+文档+索引。后端测试 **32 → 149 项**。
  - 核心设计：**周锚定** —— 周流量 = 本周最早一次采集的读数 − 上周最早一次采集的读数，一周内锁死（周中再采多少次排行榜都不变）
  - 数据模型只加 2 列原始读数（`in_octets`/`out_octets`），派生值全部由 API 按用户选的时间窗在读时算
  - 计数器命令**自带端口名**，流量路径完全不 join 端口清单 —— 索引错位那一整类 bug 从根上消失
  - 三档窗口 `1/4/13` 周；排序 `is_uplink DESC, 流量 DESC`；过渡期显示空态**不回退**旧口径
  - 真机首轮验证：2960X 151/150、C9500 57/48、Aruba 精确相等且 lag 已过滤、C8300 路由器 7/7
- [2026-09-15] 本日共发现并修复 **6 个既有 bug**：路由器身份丢失（`devices.type` 被写成 Netmiko 驱动名）、`_analyze_interfaces` 早退、Aruba lag 混入、`uplink_ports` 从未传递、ISR 的 `admin down` 两词状态、`Loopback1`/`Lo1` 命名不一致。**其中有 4 个是"静默失效"型**——不报错、不崩溃，只是数据悄悄不对。这类问题的共性：**靠肉眼看结果是发现不了的，必须拿真机数据做交叉核对**。
- [2026-09-15] **定位"静默失效"的有效手法**：找"本不该出现的组合"。本次靠三个探针找出三处 bug ——
  (1) `status='unknown' 且 in_octets IS NOT NULL`（补入路径被触发）→ 暴露命名不一致
  (2) `is_uplink=1` 全库 0 行 → 暴露字段没传进去
  (3) 路由器端口快照 0 条 → 暴露类型判断失效
  **给关键路径埋这种"异常组合"统计，比读代码有效得多。**

## Key Learnings
- [2026-09-17] **STP 生成树拓扑图（新功能，v2.9.17）**：采集 `show spanning-tree`（两平台同一条命令：Aruba AOS-CX RPVST / Cisco Rapid-PVST）→ `analyzers/stp_parser.py` 双平台解析 → `stp_snapshots` 表（迁移 v11，一行=设备×VLAN×端口）→ `GET /api/topology/location/{loc}/stp` → 前端 `StpTopologyCanvas`（VLAN 彩色伪端口 + 按 STP 深度分层 + 图例点击高亮单棵生成树）。
- [2026-09-17] **跨厂商认根必须比归一化 MAC，不能比优先级数值**：Cisco 显示含 sys-id-ext（VLAN1 显示 8193），Aruba 显示 8192；MAC 格式 Cisco 点号 `9c37.0806.b540` vs Aruba 冒号 `9c:37:08:06:b5:40`，统一为无分隔符小写后可比。
- [2026-09-17] **落库行数 = 真机 summary 的「STP Active」列**（SWI03=14 / SWI04=32 / SWI05=61）——过滤 Down/Disabled 端口的口径由此交叉验证。Cisco `show spanning-tree summary` 只有端口计数没有角色，画不出「哪条链路阻塞」，画 STP 图必须采完整版。
- [2026-09-17] 真机输出是 **CRLF 行尾**：解析器必须先 `\r\n → \n` 归一化，否则 `^VLAN\d+$` 这类 `$` 锚点全部失效（grep 验证时也踩了同一个坑）。
- [2026-09-17] **站点级根桥 ≠ 任一 VLAN 的根**：本地孤立 VLAN（PVG 的 VLAN34 在 SWI02/SWI05 上各有一个根、VLAN4092/4093 在 SWI04）的根若计为站点根桥，会把接入交换机错误抬到第一层。正确定义：至少是一个「有跨设备边的 VLAN」的根。
- [2026-09-17] PVG 真机锚点（回归用）：5 台交换机、55 条 VLAN 边（15+13+14+13）、根 SWI01 在第一层、四个接入在第二层、各设备 VLAN 数 16/16/13/16/14。
- [2026-09-17] **STP 数据保留：`stp_snapshots` 每设备留最近 2 次采集**（用户指定，与配置全文/日志同档）——图只读最新一轮，第 2 轮作「根桥/阻塞变化」对比基线。`prune_db` 顺手修正：logs_keep/stp_keep 原先借用 config 的 keep 列表（参数形同虚设，都默认 2 才没出事）。
- [2026-09-17] **STP 连线按层带几何自适应**（用户澄清后定案，f5c7837）：按「源设备→目标设备」分层带，两端芯片最大横向错位 < 64px → **整带走直线**（BJQ 三层链：每层 VLAN 相同、列对位，实测 maxDx=0px）；否则**管道折线+圆角+线束**（PVG 星型，实测 maxDx 374~1164px）。教训：正交折线路径必须先保证 `|dx| ≥ 2×圆角半径`，否则水平段反向折回、退化出钩形——这就是「圆角方向反了」的真相（bug-105）。**先去库里取真机数据模拟布局数学再改路由，比凭感觉改快得多**（本次用 tmp 脚本复现了前端布局计算）。
- [2026-09-17] **同一对设备间可能有多条物理链路，STP 只跑在部分端口上**（SHA：SHAD2SWI02→C9500 两条链路，STP 只在根端口 Gi1/0/42 上有行）。成边必须**保留全部候选链路并按 VLAN 取真实跑 STP 的端口（优先 root 角色）**——「每个邻居只挑一条」会挑中无 STP 行的端口 → 节点孤立消失（bug-106）。VLAN 级负载分担（不同 VLAN 根端口不同）也靠这个合并规则各取所需。
- [2026-09-17] **同层双根桥是真实存在的**（SHA：SWI01 是主 VLAN 的根、SHAD2SWI02 是 VLAN4092/4093 的根 → 都在第一层并排）。同层边要两个配套改动：后端按 STP 角色定向（designated 端为上游、箭头朝根端）+ 前端底部下弧线渲染（`bt-<vlan>` 底部 target handle）。

## Do-Not-Repeat
- [2026-09-17] **Git Bash heredoc 再次踩坑**：`cat >> file <<'EOF'` 追加含引号/反引号的大段代码直接报 `unexpected EOF while looking for matching`。**追加代码一律用 Write/Edit 工具**，不要在 bash 命令里嵌大段内容（与 2026-08-17 的教训同源）。
- [2026-09-17] 0 字节垃圾文件再次出现（本次 `{nb`、`ZGND1SWI01`，来自 python heredoc 会话）。提交前 `git status --short` 拦截依旧有效，照旧处理。

## User Preferences
- [2026-09-17] STP 图形态由用户指定：只画交换机、VLAN 当伪端口（每 VLAN 一色）、按 STP 深度分层、根桥第一层、标注优先级/转发/阻塞；读存量数据不做实时采集；模式一致性检查为内置功能。
- [2026-09-17] STP 图首版获用户认可（「效果挺好」）——VLAN 伪端口 + 分层 + 着色的呈现方式就是用户想要的效果，后续调整在此骨架上做。
- [2026-09-17] 真机样本由用户提供（`PVGD1SWI0* show spanning-tree*.txt` 存项目根目录）——先取样、再写解析器。

## Decision Log
- [2026-09-17] 不用 running-config 推算 STP：配置只有意图（优先级/模式），缺实际根桥（需桥 MAC 决胜、可能站点外）、端口角色、转发/阻塞（纯运行态）；trunk 口常隐式全放行，连「链路承载哪些 VLAN」都查不全。只新增一条采集命令 `show spanning-tree`。
- [2026-09-17] STP 图按 LAG 逻辑口成边（物理成员隐藏，与既有偏好一致）；堆叠成员合并为逻辑节点（STP 以逻辑桥运行）；`show spanning-tree detail` 不需要（完整版已含端口表）。

## Key Learnings
- [2026-09-17] **Dashboard 端口统计的三个桶**：`port_stats` = up / disabled（管理性关闭，status ∈ {disabled, admin}）/ down（其余非 up：notconnect、err-disabled、unknown…）。「空闲端口」卡片口径 = down + disabled = 全部非 up。此前 `disabled` 初始化后从未累加（恒 0），柱状图 Disabled 段永远为 0——聚合 SQL 用 `SUM(CASE WHEN status IN ('disabled','admin') THEN 1 ELSE 0 END)` 分类即可（bug-114）。
- [2026-09-17] **port-channel（Po*）在任何 Cisco 平台上都是逻辑口**：`show interfaces counters` 对 2960X/3850/3560/9200L 同样输出 Po（counter_parser 里「只有 C9500 输出逻辑口」的注释是过时的），Po 计数器 = 成员口聚合，与成员口同时入库会**双重计数**（实测 KR5D1SWI01：Te1/0/1 与 Po1 读数几乎相同）。排除要**两侧同时做**，否则 status 侧过滤后 `_enrich_counters` 会把它当「清单外物理口」以 status=unknown 补回来：`is_excluded_port` 全局判 Po（Hu 仍仅 C9500）+ `_parse_cisco_ios` skip_prefixes 加 "po"。与 Aruba 排除 lag 口径一致。
- [2026-09-17] **前端图表配色按数据键，不按显示名**：环形图曾经用 `entry.name === 'Cisco IOS'` 比对图例文案，而 Aruba 的 i18n 实际文案是 'Aruba OS' → 匹配失败落进 other 灰，与路由器同色（bug-115）。显示名走 i18n，改文案/切语言就会再次撞色。正确做法：数据里带原始 `type` 键，颜色表 `Record<rawType, color>`，未登记类型走 fallback 色表轮转。

## Do-Not-Repeat
- [2026-09-17] 端口清单/流量口径改动要考虑**双数据源**（status 解析 + counters 补录），只改一侧会把端口以错误状态补回来——见上条 Key Learning 的具体机制。

## User Preferences
- [2026-09-17] 用户认可用「先查真实库把数字构成摊开（每类多少条、都是什么）」的方式回答数据疑问，再给方案让其选择（本轮 1438 idle 端口的构成分析）。

## Key Learnings
- [2026-09-17] **报告页最终形态（用户定案）：三张表都是「一张大表 + 位置过滤 + 列头排序 + CSV 导出」**，不做分组卡片、不做 Top N 硬截断 —— 排序出来的前几行自然就是 top。位置过滤器复用 `LocationFilter`（ALL + 站点按钮组），位置列表与设备管理页同源（设备清单去重）。
- [2026-09-17] **堆叠设备的型号字段是逗号拼接的成员型号**（"JL658A, JL658A"）。做「同型号版本一致性」比较前必须**去重**（去重后单机 JL658A 与堆叠 JL658A 才归为一组）——实测去重后多抓出一组不一致：JL727B（"JL727B" vs "JL727B, JL727B" 原先因字符串不同被漏掉）。
- [2026-09-17] **端口名/版本的展示值不要和图例显示名绑定**（与 bug-115 同源），报告里的排序键要用原始字段；型号列展示用去重后的 `model` 字符串。
- [2026-09-17] **CSV 导出三件套**：① 内容前加 `﻿` BOM，否则 Excel 打开中文乱码；② 行尾 CRLF、字段按 RFC 4180 转义；③ Blob URL 先 `appendChild` 再 `click()`、延迟 1 秒 `revokeObjectURL`（项目既有教训）。导出内容 = 当前筛选 + 当前排序（所见即所得），文件名带报告名 + 位置 + 日期。
- [2026-09-17] **解析器修复只对「新采集」生效**：uptime 是采集时解析后入库的标量（`collections.system_uptime_seconds`），而 `show version` 原文不入库（只有 Aruba 的 boot_history_raw 存了）→ 历史行无法追溯回填，修完必须重新采集设备才有数据。写这类"入库前派生"的解析逻辑时，测试与真机回归要趁早做（本次 18 台 Cisco 空了一整轮才发现）。
- [2026-09-17] FastAPI 端点的**默认参数别写 `Query(None, description=...)`**——直接调用（测试）时会把 Query 对象当值传进 SQL。项目里 `stats.py` 用的是普通 `None` 默认值，保持一致（bug-118）。

## User Preferences
- [2026-09-17] 报告/表格类页面：用户偏好**扁平大表 + 过滤 + 排序**，而不是分组卡片；能排序就不要再加筛选下拉（类型筛选被表头排序替代）。
- [2026-09-17] 数据类页面要能**导出**（CSV，Excel 可直接打开）。

## Key Learnings
- [2026-09-17] **堆叠成员级数据模型**（v12）：`devices` 表新增 `member_versions` / `member_rom_versions` / `member_uptimes`，三列都与 `serial_number` **同序逗号对齐**（成员三元组序列号/型号/成员编号的既有约定）。历史采集无此数据且 show version 原文不入库 → **不可回填**，只有重新采集才填充。
- [2026-09-17] **堆叠是整堆叠共享一个软件镜像**（Aruba VSF / Cisco IOS-XE StackWise / 正常运行的 classic StackWise）：逐成员软件版本只存在于 **classic IOS 堆叠**的 `show version` 成员表（`Switch Ports Model SW Version SW Image`，2960X 等）；Aruba VSF 的 `show vsf detail` 软件版本在**堆叠级**，成员级唯一逐成员字段是 **ROM Version**；IOS-XE 堆叠（C9500/3850）的 show version 只有成员段（Switch 02）无版本列。→ 成员版本不一致实际只在 classic IOS 堆叠的**升级窗口**出现（一个成员已进新镜像、另一个还没重启）。
- [2026-09-17] 成员级运行时间：Cisco 用各成员段的 `Switch Uptime`（**1 号成员 = 设备级 `<主机名> uptime is`**，主交换机），Aruba 用成员段的 `Uptime`（注意 AOS-CX 会写 `21 hours under a minute` —— 秒级忽略）。成员级 uptime 能看出设备级看不出的信号：堆叠里单台成员重启。
- [2026-09-17] 成员命名规则（前后端一致）：**真实 Member ID 优先**（数量与序列号一致时），否则顺序号；≤9 个成员不补零（`SZXD1SWI01-1/-2/-3`），≥10 才补零（padWidth = len(str(count))）。后端在报告里合成最终名称（导出也用同一个名字）。
- [2026-09-17] **`zip()` 展开成员字段是陷阱**：`zip(serials, member_ids, models)` 在 member_ids 为空（Cisco 堆叠）时静默产出 0 条 —— 正确做法是以最全的字段（序列号）为基准，其余字段按数量是否对齐决定用或退回（bug-119）。

## User Preferences
- [2026-09-17] **软件版本报告的语义（用户定案）**：按**物理成员**展开（堆叠拆成 SZXD1SWI01-1/-2/-3），每个成员显示自己的序列号/版本/运行时间；**只有同一堆叠内成员版本不一致才报警**，跨设备同型号版本不同是正常的分站点差异、不报警。
