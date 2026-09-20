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

## Key Learnings
- [2026-09-17] **「版本不一致」在两处必须同口径**：软件版本报告（`api/reports.py`）与异常检测（`analyzers/anomaly_detector.py:_check_version_mismatch`）都只比较**同一台设备内部的堆叠成员**（member_versions / member_rom_versions 去重 >1）；跨设备同型号版本不同属正常（分站点/分批次升级），两边都不报警。改规则时**两处要一起改**，否则报告与问题面板自相矛盾（bug-120）。
- [2026-09-17] 批量操作端点（如 `PUT /api/alerts/resolve-all`）的过滤参数与列表端点**逐一对齐**，页面「看到什么就清除什么」；实现上抽一个 `buildFilterParams()` 让两处共用，避免以后加筛选条件时漏同步。批量端点要注册在 `{id}` 参数化路由**之前**（本项目既有教训）。
- [2026-09-17] 批量操作前用**确认框 + 提示条**（Snackbar）：确认框写明影响条数与「此操作不可撤销」，成功后在 Snackbar 报实际清除条数（以服务端返回的 rowcount 为准，不是前端估算）。

## User Preferences
- [2026-09-17] 问题面板要能「全部清除」（按当前筛选条件批量标记已处理）。
- [2026-09-17] 英文模式下的原始 key 问题（en.ts 缺整段 alerts.* / reports.*）要顺手补齐，不留英文界面显示 `alerts.title` 这种半成品。
## Do-Not-Repeat
- [2026-09-17] **0 字节垃圾文件的根因找到了**：在 bash heredoc 里写 Python **f-string 且文本含裸花括号**（如中文里出现 `7}`、`{nb`）时，f-string 解析失败 → heredoc/重定向把残缺片段落成文件名（本项目已出现过 `{nb`、`ZGND1SWI01`、`1`、`7}` 四种）。**预防**：heredoc 里拼字符串用普通字符串 + `+` 或 `''.format()`，不要用 f-string 包裹含 `{}` 的自由文本；每次 `git add` 前照旧 `git status --short` 拦截（本轮又抓到 `1` 混进发布提交、`7}` 出现在工作区）。

## Key Learnings
- [2026-09-18] **成员级运行时间只在 ≥2 个成员时才落库**（`extract_member_uptimes` 有意为之，注释写「单机运行时间由设备级字段负责」）→ 报告侧必须**自己回退设备级** `collections.system_uptime_seconds`，否则单机设备（Cisco 非堆叠 11 台 + 3 台路由器 + Aruba 单机 10 台）整列显示 "—"。回退只对**单成员**设备做：多成员设备拿不到成员级数据时（C9500 StackWise Virtual 没有成员段）保持空 —— 设备级 uptime 只代表主/活动成员，复制给其它成员是错的（bug-121）。
- [2026-09-18] **Cisco 的 ROM（引导）版本在 `show version` 里**：`BOOTLDR: ... Version 15.2(4r)E3`（优先）/ `ROM: System Bootstrap, Version 12.2(44)SE6`（老 IOS）。真机只上报主交换机的引导版本、成员段没有该字段 → 解析后**按成员数复制**，保持「与序列号同序对齐」的列约定。注意 2960X 的 `ROM:` 行是 `Bootstrap program is C2960X boot loader`（无版本号，跳过）。
- [2026-09-18] **IOS-XE 堆叠的成员软件版本解析不到**（KWJD1SWI01 3850：成员运行时间解析成功、成员版本为空；C9500 SVL 两者都空）。原因很可能是 IOS-XE 的成员表多一列 `Mode`（INSTALL/BUNDLE），现有 `_CISCO_MEMBER_TABLE_ROW` 正则只吃 5 列（bug-123，待真机样本确认后修）。
- [2026-09-18] **「我看到的页面是不是最新版」的根源**：start.bat 每次启动都会重建前端（dist 确实是新的），但**浏览器标签页里驻留的旧 JS 不会自己更新** —— 界面代码是旧的、接口数据是新的，字段对不上号，看着就是"数据没显示"。SPA 尤其明显（站内跳转不触发整页加载）。已加两层防护：① index.html 一律 `no-cache, no-store`（bundle 名带内容哈希，index.html 是唯一引路文件）；② 前端自己的 bundle 名与 `/index.html` 里引用的不一致时弹「系统已更新」提示条（App.tsx，focus + 5 分钟轮询）。
- [2026-09-18] **SPA 回退必须排除 `/assets/`**：原先 404 处理器把 `/assets/xxx.js` 也回退成 index.html（200 + HTML 当 JS 交付）→ 请求已删除的旧 bundle 时模块解析失败且极难排查。现在返回 404 JSON。

## Do-Not-Repeat
- [2026-09-18] **别用 `kill $!` 停 Windows 上后台启动的 `python backend/main.py`**：Git Bash 的 `$!` 不是那个 python 进程（实测杀完端口仍 LISTENING，且后来 `start.bat` 的端口检查会误判）。停服务用 `netstat -ano | findstr ":8002" | findstr LISTENING` 取真实 PID + `taskkill //PID <pid> //F`。
- [2026-09-18] 用户报「页面数据没显示」时，**先确认浏览器里跑的是哪个 bundle**（`index.html` 引用的 vs. 内存里运行的），再看数据 —— 本次"版本列为空"实为旧页面假象，白查了一轮数据库。
- [2026-09-18] **heredoc 陷阱第二次咬人：这次是反引号**。用 bash heredoc（即使写成 `<<'PY'` 加引号）追加含行内代码反引号的 Markdown（形如 \`analyze(...) -> dict\`）时，shell 把成对反引号当命令替换解析，碎片被重定向成了 0 字节文件 \`dict\`\`。**铁律：Markdown / JSON / 代码等内容一律用 Write/Edit 工具写，不要走 bash**（bug-094 已记过一次；`git add` 前照旧 `git status --short` 拦截）。

## User Preferences
- [2026-09-18] 报告页**只留页面级滚动条**：表格容器不要再套一层 `maxHeight` 内滚动（三张表的 `TableContainer sx={{ maxHeight: '72vh' }}` 已去掉）。
- [2026-09-18] 用户日常通过 `start.bat` 启动，期望**打开就是最新版页面**。

## Key Learnings
- [2026-09-18] **C9500 StackWise Virtual 是独立特例平台**（用户定案：就两台、快退休，将就加特例）。它的命令与其它 Cisco 都不同：`show version` 没有成员表、成员段也没有 Switch Uptime → 成员运行时间只能用 onboard logging 分别取：
  `show logging onboard switch active RP active uptime` / `show logging onboard switch standby RP active uptime`，
  两段各有 `Current uptime : 1  years  40  weeks  4  days  23  hours  6  minutes`（注意双空格、`Total uptime` 是累计值不要取）。两段顺序 = active、standby，与 `show version` 序列号顺序一致（1 号 = active）。判定用**型号**（`_is_svl_device`：模型含 C9500）——platform 是 cisco_ios_xe，与 C9200L 共用区分不开。
- [2026-09-18] **判定设备特例的型号来源**：`api/collector.py` 逐字段构造 Device 对象时**没有带 model**（bug-079 同类陷阱），特例判定要在连接前知道型号就必须补上 `device_obj.model`（来自 devices 表上次入库的值）。首采（型号未知）时特例不生效，第二轮才有 —— 可接受。
- [2026-09-18] **KORD1SWI02 的成员数据缺失已定性为设备侧**：8 台 Aruba VSF 堆叠里 7 台用 `show vsf detail` 正常拿到 ROM + 成员运行时间；只有它那次采集**每条命令**都被回 `Cannot execute command. Command not allowed.`（配置 1 行、端口 0、邻居 0、版本/序列号/型号全"未知"，boot_history_raw 存的就是那句原话）。它 09-15 采集还是正常的 → 该设备本地的账号/角色配置或 VSF 状态问题，重采即可验证。

## User Preferences
- [2026-09-18] **自定义报告只保留两张**：**设备运行状态报告**（原「软件版本报告」，按物理成员展开，含每台设备的运行时间）+ **带宽利用率汇总**。「设备在线时间」报告与之重复，用户定案删除 —— 端点 `GET /api/reports/device-uptime`、前端表与 `UPTIME_GETTERS`、`api.deviceUptime` 全部移除。代码标识同步更名：报告类型值 `device-status`、i18n key `reports.deviceStatus`（后端端点路径 `/api/reports/software-versions` 保持不动 —— 数据源语义未变）。

## Decision Log
- [2026-09-18] **把 allright/netstd 的配置审计能力并进 NDM**（用户自有项目，无知识产权顾虑）。定位不是"跑规则出报告"，而是**模拟资深网络专家评审**：设备上下文分族（平台×角色×站点适用域）→ 组合/配套规则（all_of / requires / conflict + 端口级作用域）→ 横向共识对比 → 按档位给优先级 → 给可执行命令与依据。判定只由确定性引擎做，AI 只负责讲成人话（二期）。计划落盘 `docs/superpowers/plans/2026-09-18-compliance-audit.md`，周日开发。
- [2026-09-18] 用户定案：**标准 = 页面可视化编辑 + YAML 存盘**（规则文件为唯一权威）；**审计 = 按需 + 全量入库**；一期做「标准页 + 查看器审计」；AI 专家简报二期。

## Key Learnings
- [2026-09-18] **厂商"配套使用"是审计最值钱的部分**（已查互联网核实）：Cisco L2 安全栈（DHCP snooping 建绑定表 → DAI → IP Source Guard，后两者依赖绑定表；上联口 trust、非信任口 rate limit、绑定表持久化）；SNMPv3 三件套（view + group v3 + **user v3**，缺 user 则整组不可用）；NTP 认证三件套（authentication-key + trusted-key + authenticate）；日志三件套（logging host + logging trap + service timestamps）；AAA 配套（tacacs server + group + 方法列表以 local 结尾 + **本地账号必须存在**，否则可能锁死）；802.1X 三件套；BPDU Guard 与 PortFast 配套且**不应出现在上行/干道口**；CX 侧 dhcpv4-snooping 必须配**上联口 trust**、`ipv4 source-lockdown` 依赖绑定库。
- [2026-09-18] **AOS-CX 的 BPDU Guard 命令官方拼写是 `spanning-tree bpdu-guard`**（接口上下文，可带 `timeout`）；"bpdus-guard" 是第三方误传 —— 用现网 18 台配置核实：bpdu-guard 9/18、bpdus-guard 0/18。
- [2026-09-18] **现网实测的配套缺口**（NDM 库 36 台最新配置）：Cisco `snmp-server group v3` 18/18 但 `user v3` **0/18**（有组无用户，SNMPv3 实际不可用）；CX `dhcpv4-snooping` 13/18 但 `dhcpv4-snooping trust` **仅 2/18**（配了一半）；Cisco `ip dhcp snooping` 1/18、DAI 0、IPSG 0。→ 审计首期就该报出这类"配了一半"。
- [2026-09-18] **netstd 引擎的数据契约**：命中证据 `evidence: [{line, text}]` 已带行号；`analyze(name, text, std) -> dict` 是字符串进/dict 出，NDM 可直接调；但 `dev.site` 只由设备名套命名正则派生 → 移植必须加显式 site/location 入参（否则站点豁免全失效）。规则无法表达组合，需加 1-2 个通用判定器（params 是自由 dict，无需新顶层字段）。
- [2026-09-18] **NDM 侧可复用**：Viewer 的 Compare 模式已有逐行渲染 + LCS 行级 diff + 左右同步滚动（审计左右对照的现成骨架）；`backend/api/logs.py` 的 GET/PUT `/api/settings/llm` 是"读写 YAML 配置"的模板（Pydantic 校验 + 保留未改字段 + 写回）；`analyzers/role_verifier.py` 的 `audit_location()` 是"审计发现"响应结构的先例；库内配置文本无 CR、无末尾空行，行号口径一致。

## Key Learnings
- [2026-09-18] **AOS-CX 命令勘误（总部 CFG-Aruba 文档第 7、8 章示例有误，已核实）**：`ssh server idle-timeout` **不是 AOS-CX 命令** —— CLI 空闲超时在 `cli-session` 上下文（`timeout <分钟>`，默认 30、范围 0–4320、0 为不超时；加固指南非敏感网络推荐 15，敏感网络 5–10；配套建议 `max-per-user`）。`snmpv3 enable` **也不是** AOS-CX 命令 —— 启用 SNMP 代理用 `snmp-server vrf <VRF>`，禁 v1/v2c 用 **`snmp-server snmpv3-only`**。佐证：现网 18 台 Aruba CX 中这两条命令命中均为 0，而 `cli-session` 也命中 0 → 空闲超时全网实际未生效（很可能就是照抄了不存在的命令）。
- [2026-09-18] **AOS-CX 管理 ACL 的正确应用方式**（总部文档只给了 ACL 定义、没写怎么应用）：ACL 定义完**必须显式绑定**才生效，管理面绑到 control plane —— `apply access-list ip MGMT_ACL control-plane vrf mgmt`（带外）与 `... vrf default`（带内 SVI）。两个要点：① AOS-CX 的 ACL **末尾自带隐式 deny**，示例里的 `999 deny ip any any log` 作用只是**记日志**；② control-plane ACL 会过滤**该 VRF 下设备所有本机地址**的流量 → 跑 OSPF/BGP 的设备**必须为路由协议预留 permit**，否则中断邻居；上线要**先在带外 mgmt VRF 验证再配 default VRF**，避免自我锁死。
- [2026-09-18] **AOS-CX 其余命令事实**：syslog 用 `logging <IP> [severity info] [vrf <VRF>]`（级别默认 info，info 及以上；支持 udp/tcp/tls、filter、rate-limit）。SNMPv3 算法 `auth md5|sha|sha224|sha256|sha384|sha512`、`priv aes|aes192|aes256|des`；**修改已有用户的算法时必须同时指定 `access-level ro`，否则读写级别会被重置为只读**。RADIUS 用主机名配置时必须有 `ip dns host <主机名> <IP>` 静态解析（不依赖 DNS 可用性）。`ip source-interface {radius|tacacs|ntp|syslog}` 决定设备访问这些服务时的源地址，配 AAA/NTP/Syslog 时必须一起配。
- [2026-09-18] **现网 18 台 Aruba CX 管理面实测缺口（2026-09 最新采集）**：Syslog **0/18**、任何 ACL **0/18**、`cli-session` **0/18**、`https-server rest access-mode read-only` 13/18、`ip source-interface` tacacs 14 / ntp 12 / radius 10（覆盖不均）、**7 台混配 `pool.ntp.org` 公网 NTP**（违反"仅用内部 NTP"）、**1 台仍有 `snmp-server community`（v2c 团体字）**、`snmpv3 user` 17/18、`aaa accounting` 14/18、`dhcpv4-snooping` 13/18 但 **trust 仅 2/18**。→ Syslog 与 MGMT_ACL 属**全网集体性缺失**，审计结果应单独成类，避免产生 18 条重复条目。
- [2026-09-18] **Qorvo Aruba 现网的组织形态（BJQ 三台提炼，写配置范例用）**：设备名 → `BJQD1SWI01`（核心 VSF 双成员 JL659A）/ `BJQD1SWI02`、`BJQD2QIS01`（接入单成员 R8Q70A）。AAA 是 **TACACS+ 三台（10.137.2.204 / 10.39.2.205 / 10.205.2.189，组名 `qorvo-tacacs`）+ ClearPass RADIUS 三台（`pvg0clrpasssub1` / `sin0clrpasssub1` / `ede0clrpasssub2`，组名 `qorvo-radius`，用户名 `cppm-arubaos-dur`）**双轨并存；`aaa authentication allow-fail-through` 保留；接入端口标配 **802.1X(dot1x)+MAC 认证双轨 + `critical-role` 降级 + device-fingerprint 指纹识别**（ClearPass 联动）；上行口用 LAG + `lacp rate fast` + `spanning-tree loop-guard`（**绝不配 bpdu-guard / admin-edge**），接入口才配 `bpdu-guard + admin-edge + loop-protect`；`spanning-tree bpdu-guard timeout 300` 为全局；VLAN 名称跨站点统一（`Qorvo-Data` / `Qorvo-Voice` / `Qorvo-Mgmt` 等）而 **VLAN ID 按站点规划**（BJQ 与 KORD、ZGN 各不相同）→ AOS-CX 支持按名称引用（`vlan access name Qorvo-Data`），端口模板因此可不含具体 ID。

## User Preferences
- [2026-09-18] **两类文档的存放分工**：总部下发标准的 **MD 转换版（英文原文保真 + 中文导读）** 与 **配置范例** 放 **OneDrive 文档库**（`01-DocWiKi/01_network_configuration/`，与 docx 同目录）；**NDM 项目内只放简化版**（`docs/standards/CFG-Aruba-checklist.md`，中文检查项清单，供合规审计功能做规则来源）。不要把完整标准或配置范例放进项目仓库。
- [2026-09-18] **配置范例的取材与脱敏规则**：只用**用户指定站点**的现网配置（本次为 BJQ）提炼，不要混其他站点；**共性内容写实际值**（AAA 服务器地址/主机名、NTP 地址、VLAN 名称），**站点相关内容留空**（具体 VLAN ID、本地网段/SVI 地址、网关）—— 因为配新设备时共性部分可复制粘贴、IP 必然要重写。密钥一律 `<CIPHERTEXT>` 占位，**绝不写明文口令**。

## Do-Not-Repeat
- [2026-09-18] **读 OneDrive 下的 docx/文件时，Python 可能直接 `PermissionError`**（Files On-Demand 占位文件 + 云筛选器驱动），而 `os.path.isfile()` 返回 True、bash 的 `head` 却能读 —— 表现为 `docx` 库报 `PackageNotFoundError: Package not found`（其内部 `is_zipfile()` 读不到文件尾）。**绕法：先用 bash `cp` 把文件复制到本地临时目录，再用 Python 处理副本**（`cp` 能触发下载）。不要因为 `isfile()` 为 True 就断定是路径写错了。

## Key Learnings
- [2026-09-18] **CFG-CISCO 基线存在"平台错配"**：总部写的 Cisco 基线**主要参考实现是 Nexus 9000 / NX-OS v7**，IOS 只作"可选参考示例"；但 **Qorvo 现网 18 台 Cisco 全是 IOS / IOS-XE / IOS 路由器（cisco_ios 14 + cisco_ios_router 3 + cisco_ios_xe 1），零 Nexus**。→ 合规检查必须**同时认两种命令形式**，且 IOS 形式才是当前实际生效的那一套。另外该文档第 7–10 章**只给了 NX-OS 示例**，IOS 侧命令要自己补（exec-timeout / logging host+trap / ip tacacs source-interface 等）。与 Aruba 版不同，Cisco 版**没有"命令不存在"级别的硬错误**。
- [2026-09-18] **NX-OS 关键命令事实（已核实）**：`ssh key rsa <bits>` 范围 **768–2048、默认仅 1024**（所以 `ssh key rsa 2048 force` 是提权到上限，正确）；SSH 最大登录尝试**默认 3、范围 1–10**（`ssh login-attempts`）；**`clock protocol ntp` 必须显式选择**，否则 NTP 不生效（IOS 无此步骤）；`key 7 <KEY>` 中的 7 表示密钥已加密存储；NX-OS ACL 同样自带隐式 deny，末尾 `deny ... log` 的作用是**记日志**；NX-OS 上 AAA/NTP/Syslog 都需 `use-vrf management` 指定管理 VRF（IOS 对应做法是 `ip tacacs|radius source-interface` + `logging source-interface`）。**待核实**：文档第 7 章的 `ssh timeout 600` 未能从公开文档确认，较新 NX-OS 记为 `ssh idle-timeout <秒>`（**默认 0 = 不限空闲**）——无论哪条，NX-OS 默认不限空闲，必须显式配置。
- [2026-09-18] **现网 Cisco 管理面实测缺口（18 台，2026-09 最新采集）**：**`snmp-server group ... v3 priv` 18/18 但 `snmp-server user` 0/18**（有组无用户 → **SNMPv3 实际不可用**，头号必报项）；**4 台仍有明文 `snmp-server community`，其中 1 个是 RW 读写团体字**（既是凭据暴露也违反 Ch8-1，**注意：这是凭据，写进任何文档/证据前必须脱敏**）；**`MGMT_ACL` 0/18**（现存 ACL 名为 `ACL-NMS-SNMPv3`、`CISCO-CWA-URL-REDIRECT-ACL`、`clearpass-redirect`、`default-port-acl`、`102`，**不能替代命名要求**）；`logging host` 10/18、`logging trap` 9/18、`logging source-interface` 仅 1/18；**明文 HTTP 未关闭约 11/18**（IOS 的 `ip http server` 默认开启，只有 7 台显式 `no ip http server`）；`transport input ssh` 16/18；`ip ssh version 2` 15/18；NTP 全用内部 `10.8.26.10`（**无公网源，优于 Aruba 侧**）但**只配了 1 台**；空闲超时用 `line vty` 的 `exec-timeout 15 0` 实现且 **18/18 达标**（IOS 位置与 NX-OS 不同）；AAA 覆盖良好（`aaa new-model` 18/18 + 命名 `radius server` 对象 + `aaa accounting commands 1|15`）。
- [2026-09-18] **《AUTOMATION-Cisco》实为审计功能的"输出契约"**：该指南用 Ansible 描述 Deploy → Validate → **Audit** → **Report** → **Dashboard** 五段生命周期，**NDM 的配置审计正是其中 Audit/Report/Dashboard 三段的自研实现**。可复用的硬约束：① **CSV 表头**采用其第 10 章版 `hostname,section,status,observed_value,remediation_note`（是第 8 章版的超集），且**列名必须稳定**否则仪表盘导入会断；② **证据文件不得包含可复用密钥/口令**（第 9 章）→ 导出前必须过滤现网配置里的 ciphertext、TACACS 密钥、v2c 团体字；③ Validate/Audit **一律只读**，Dashboard 层**只消费证据、不得回写设备配置或改写证据**；④ **已批准的站点特有例外不得判为不合规**（第 6 章工程注记）→ 规则模型必须支持例外豁免；⑤ 每行证据需含主机名/段/状态/修复建议，文本证据含观测值。

## Decision Log
- [2026-09-18] **AUTOMATION-Cisco 的处置结论：采纳其输出契约，不采纳其实现方式**。理由：其 Ansible playbook 方案与 NDM 已具备的能力高度重叠（SSH 采集、配置存储、报告导出），且 NDM 已有 Web UI、SQLite 与规则引擎，再引入 Ansible 是重复建设；但该指南是**总部对"审计证据长什么样"的正式约定**，NDM 的导出应对齐，以便结果能喂给总部设想的报告层。已把该约束写进 `docs/superpowers/plans/2026-09-18-compliance-audit.md` 的「九、补充」章节。
- [2026-09-18] **⚠️ 待用户定案的张力**：AUTOMATION-Cisco 用 **PASS/FAIL** 作为证据状态（`status` 列），而审计功能已定调「建议非强制、界面不出现违规/合规分/pass-fail 字样」。计划里给了三个调和方案（A：`status` 承载五档建议强度 + 另加 `severity` 列区分 shall/should；B：shall 项给 PASS/FAIL、should 项给建议档位；C：完全按总部 PASS/FAIL，不推荐），**周日动手前需确认**。

## User Preferences
- [2026-09-18] **总部标准文档的处理惯例（已成套）**：每份 `CFG-*.docx` → ① **OneDrive 同目录**放**完整转换版**（英文原文保真 + 每章中文导读 + 编者注/勘误）；② **项目 `docs/standards/`** 放**简化版检查项**（中文、带 ID/强度/判定提示，供合规审计做规则来源）。**配置文件只放在 OneDrive**，项目仓库不放。
- [2026-09-18] **脱敏红线**：写进项目文档的内容不得包含任何凭据——现网配置里的 SNMP v2c 团体字、ciphertext 口令、TACACS/RADIUS 密钥都属凭据，**只能描述"存在/不存在"与所在设备，不得抄录值**。

## 周日开工前（2026-09-20）必读：待确认与待办

**【第一件事 · 必须先问用户】审计导出的 `status` 列语义**——总部《AUTOMATION-Cisco》要求 PASS/FAIL，而本项目已定调"建议非强制、界面不出现违规/合规分/pass-fail"。三个候选：
- **A（推荐）**：CSV 的 `status` 列承载**五档建议强度**，另加 `severity` 列区分 `shall` / `should`；界面保持建议语义。
- **B**：`shall` 类给 PASS/FAIL，`should` 类给建议档位。
- **C**：完全按 PASS/FAIL 输出（与已批准决策冲突，不推荐）。
> 用户尚未选。周日动手写 `backend/api/audit.py` 的导出之前必须先确认，否则导出契约要返工。
> 详见 `docs/superpowers/plans/2026-09-18-compliance-audit.md` §九 与 §三 第一期 A→E。

**【已完成 · 无需重做】** 三份公司基线文档已产出（2026-09-18）：
- 完整转换版（英文原文保真 + 中文导读）→ OneDrive `01-DocWiKi/01_network_configuration/`：`CFG-Aruba.md`、`CFG-CISCO.md`、`CFG-Aruba-Example.md`（配置范例，仅此一份在 OneDrive）。
- 检查项简化版（合规审计的规则来源）→ 项目 `docs/standards/`：`CFG-Aruba-checklist.md`、`CFG-Cisco-checklist.md`。**两份都带 ID / 强度 / 判定提示，可直接映射成 `config/audit/*.yaml` 规则草稿。**

**【待提交 · 用户未发话】** `git status --short` 当前：
```
 M .wolf/anatomy.md
 M .wolf/buglog.json
 M .wolf/cerebrum.md
 M docs/superpowers/plans/2026-09-18-compliance-audit.md
?? docs/standards/
```
**周末不要自行提交**——项目约定是"仅在用户要求时提交/推送"。

**【周日开工顺序（按已批准计划 §三 第一期）】** A 引擎移植与改造 → B v13 迁移 → C `api/audit.py` → D 前端（Viewer 审计模式 + 标准页）→ E 测试。先跑通"标准页 + 单台审计"，再补全量入库；每步单独提交。
**回归基准**：现有 238 项测试全绿；移植等价性基线 = 库里 36 台真机配置跑出**总命中 205 条**，前后必须一致。

## Decision Log
- [2026-09-20] **审计导出 `status` 语义定案：采用方案 A**（关闭周四遗留的待定案项）。导出 CSV 列 = `hostname,section,status,severity,observed_value,remediation_note`（在总部《AUTOMATION-Cisco》第 10 章版基础上**增加 `severity` 列**）。**`status` 承载五档建议强度**（强烈建议/风险提示/改进建议/可选优化/需人工判断），**不输出 PASS/FAIL**，界面与导出统一"建议非强制"语义；**`severity` 承载强度来源**：`shall`（公司基线强制）/ `should`（公司基线建议）/ `vendor`（厂商加固）/ `convention`（现网惯例）——总部若要按 PASS/FAIL 消费，自行用 `severity = shall` 过滤即可。已写入计划 §十。
- [2026-09-20] **标准来源的边界定案：一期不扩标准源**。开工前讨论确认：判定仍只用三层——**公司总部要求**（CFG-Aruba / CFG-CISCO）+ **厂商加固建议** + **现网惯例**。理由是三层都是"配置该长什么样"的静态标准，而扩范围会挤掉"标准页 + 单台审计"最小闭环。新增来源分三类处理（计划 §十一）：**一期顺手做**运维就绪度；**记入二期**厂商安全公告与生命周期（EoL/CVE）、流程合规（变更单比对）、例外登记机制；**只做标签不新增判定**的是合规框架映射（NIST 800-53）；**RFC/IEEE 协议标准不作为标准来源**，而作为规则的**技术依据**写进 `why` 字段——这是"资深专家评审"与"规则引擎跑分"的区别。

## Key Learnings
- [2026-09-20] **NDM 当前采集链路已不含 startup-config**：`backend/collectors/base.py` 与 `collector_service.py` 中**没有任何 startup 相关代码**，`collections` 表也没有 startup 列（列为 id/device_id/week/phase/collected_at/software_version/serial_number/model/system_uptime_seconds/running_config/running_config_lines/boot_history_raw/lag_membership）。但磁盘上**仍有 2026-24~27 周的历史 `startup-config.raw`**——说明以前采过、后来被移除。→ **"running 与 startup 是否一致"这类运维就绪度检查，前置条件是先把 `show startup-config` 重新纳入采集**；不要误以为现成数据可用（CLAUDE.md 里仍写着采集项含 `show startup-config`，与实际代码不符）。
- [2026-09-20] **现网 25/36 台设备的登录横幅自称可能承载 CUI**（`Controlled Unclassified Information`；aruba_aoscx 10 台 / cisco_ios 12 台 / cisco_ios_router 2 台 / cisco_ios_xe 1 台，其余用较早的 LEGAL NOTICE 文案）。这条横幅是「Qorvo Acceptable Use Policy」版本文案的一部分。→ 若确实涉及 CUI，则 **NIST SP 800-171 / CMMC** 可能是硬要求，中国站点还可能要面对**等保 2.0**；已作为待确认问题提给用户。**这是判断"要不要加合规框架"的关键线索，别丢掉。**

## Decision Log
- [2026-09-20] **规则库层优先级定案（用户定案）：总部要求 > 厂商推荐 > 配置惯例**。三层规则**重复或冲突时一律以高层为准**。落地方式：① **重复**（同一件事多层都要求）→ 只在高层写规则，低层不重复写；若低层已有规则，则给高层规则挂 `controls` 溯源，避免同一问题报两遍（已用此法处理 SNMPv3 / SSH / HTTP / BPDU 等 4 处重叠）；② **冲突**（高层要求做、低层要求不做）→ 高层规则照常判定，低层规则显式置 `enabled: false` 并写明 `superseded_by`，**不删除**（删掉会丢掉"讨论过、因冲突而让位"的记录）。引擎侧 `LAYER_PRIORITY` 用于同档位下的报告排序。原则已写入 `config/audit/_scopes.yaml` 文件头作为全局约定。
- [2026-09-20] **SNMP 团体字冲突的处置**：总部 CFG-CISCO 第 8 章要求"SNMPv1/v2c 不得配置"（shall），而 vendor-baseline 的 `not_adopted` 记录着"用户决定不收 SNMP 团体字相关项"。按层优先级，**保留总部规则 `hq_cs_no_snmp_community`**；`not_adopted` 对应条目改为记录"已被总部要求覆盖"，不删除。现网实况：4 台 Cisco 仍有明文团体字，其中 1 个是 **RW 读写**。

## Key Learnings
- [2026-09-20] **AOS-CX 的 AAA 方法列表顺序有讲究**：`aaa authentication login default group local qorvo-tacacs` 是"**先本地、后集中**"，与总部第 5 章"本地认证仅作集中式 AAA 不可用时使用"相反；正确写法是 `group qorvo-tacacs local`。**现网两种顺序并存**，是真实偏离。规则用正则 `^aaa authentication login default group \S+ local` 专抓这个顺序。
- [2026-09-20] **现网 Cisco 侧 SNMPv3 有组无用户（18/18）**：全部配了 `snmp-server group ... v3 priv`，却**一台都没配 `snmp-server user`** —— SNMPv3 没有用户就无法认证，整组不可用，而监控侧看起来"配了 SNMPv3"。这是本次审计最该报出的一条，也是"配了一半"的典型。
- [2026-09-20] **端口角色推断必须按信号优先级分层，不能做"信号投票"**（真机教训）：① `vlan trunk allowed <列举>` **不是**上行信号 —— 现网 214 处其实是**电话口**（`vlan trunk native 16 / allowed 8,16`），只有 `allowed all`（50 处）才是干道；② 弱信号不能推翻强证据 —— BJDD1SWI01 多个口对端 CDP 报出的是 SD-WAN 路由器（硬证据），但配置是 `vlan access`（SD-WAN 的 LAN 口本就落在 access VLAN 上），用形态提示降级硬证据会把真实上行口变成"拿不准"；③ **完全判断不出的端口不进"拿不准"清单**，否则电话口会淹掉真问题。分层结果：high 176 / medium 1624 / low 21。
- [2026-09-20] **总部的"至少两台"类要求需要新的判定原语**：第 5/9/10 章都要求 ≥2（AAA 服务器 / NTP / syslog 收集器），简单正则表达不了"几条" → 新增 `min_count` 判定器（params: pattern + min + label）。
- [2026-09-20] **【重要】NDM 的 data_root 是相对路径，跑脚本必须在项目根目录**：`config/settings.yaml` 里 `data_root: ./data`，从 `backend/` 下跑会**新建一个空库** `backend/data/ndm.db`（现象极具误导性：跑了 v1→v12 迁移、查询返回 0 台设备，看起来像"数据全没了"）。主库不受影响。跑 NDM 脚本一律在项目根目录 + `sys.path.insert(0, 'backend')`。已记 buglog。
- [2026-09-20] **规则库现状（58 条）**：公司总部 29（CX 14 + Cisco 15）+ 厂商基线 21 + 组织惯例 8；severity 分布 shall 17 / should 12 / vendor 21 / convention 8；33 条带 NIST `controls` 标签。全网 36 台 **486 条命中、741 ms（20.6 ms/台）**。**移植等价性回归仍在守**：按 netstd 原有 26 条规则 id 过滤后仍为 207 = 207 —— 规则库继续扩充也不会让这条回归失效。

## Key Learnings
- [2026-09-20] **ruamel.yaml 往返编辑必须设三个参数，否则会把整个文件重排**（会让 git 历史报废：改一个字段看起来像全文重写）。`YAML()` 之后必须：`indent(mapping=2, sequence=4, offset=2)`（让列表项写成 `  - id:`）、`width=4096`（**禁止按 80 列折行**）、`preserve_quotes=True`。另有一条更隐蔽的：**跨行的"普通标量"回写时会被合并成一行**（如手写的两行 `why:`）——规则文件里跨行的 why/note **必须写成 `>-` 折叠块**。已验证：4 个规则文件在两个修正后均"零改动往返逐字节不变"。两道闸门测试已加：改一个字段只允许 1 行差异；全部规则文件必须往返稳定。
- [2026-09-20] **FastAPI 端点的 `Query(...)` 默认值在"直接调用端点函数"时会变成 `Query` 对象**（不是默认值），导致 `sqlite3.ProgrammingError: type 'Query' is not supported`。本项目的既有端点都用**普通默认值**（`level: str | None = None`）就是为了测试能直接调用。去掉 `Query(pattern=...)` 后要自己在函数里校验取值。
- [2026-09-20] **审计 API 的最终形态（7 个端点）**：`GET /api/audit/ruleset`（含已停用规则）、`GET /api/audit/device/{name}`（envelope，含配置原文）、`GET /api/audit/device/{name}/export?format=md|json`、`POST /api/audit/run`（全量入库，36 台 877 ms）、`GET /api/audit/runs`、`GET /api/audit/runs/{id}`、`PUT /api/audit/standards/rule/{id}`。规则写入链：乐观锁 → 备份（`.backups/` 留 10 份，已 gitignore）→ 原子替换（临时文件 + `os.replace`，Windows 占用重试 10 次 × 0.2 s）→ 校验失败回滚 → 清缓存。
- [2026-09-20] **验证规则编辑往返正确性的最简办法：比对规则集指纹**。编辑前记录 `ruleset_hash`，改一个字段再改回来，指纹若回到原值即证明文件内容逐字节还原（比人眼看 diff 可靠）。

## Decision Log
- [2026-09-20] **规则文件编辑采用 ruamel.yaml（新增依赖 `ruamel.yaml>=0.19`）**，而非计划里"一期用 PyYAML、接受丢注释"的方案。理由：规则文件里的注释记录着每条规则**为什么存在**（不采纳项的来龙去脉、现网实测依据、勘误说明），是这个库最值钱的部分，丢注释等于丢机构记忆。代价是要处理 ruamel 的重排/折行/合并三个坑（已修并有测试守着）。

## Decision Log
- [2026-09-20] **startup-config 的存储策略定案（用户拍板）**：数据库 `collections.startup_config` 与 running 同一套保留策略（留最近 2 次）；**文件层只留最新一份**（`data/{设备}/startup-config.raw`，覆盖写），**不做周历史**。理由：两者价值曲线不同——running 变化频繁、历史有价值（变更检测/审计取证）；startup 变化极少（只在 save 时），按周存 52 份里 51 份是重复副本。总增量约 3.5 MB 且不随时间增长；照 running 的方式存则每年 +62 MB。
- [2026-09-20] **"改了没保存"做成双轨（用户定案）**：采集后即时**告警**（`config_drift`，时效性强——设备随时可能重启）+ **审计检查项**（`ops_config_not_saved`，状态画像）。与项目既有的「堆叠成员版本不一致」同构（那个也是既进告警又进报告）。
- [2026-09-20] **状态型告警必须有去重与自动消除**：`config_changed` 是**事件型**（每次变更一条，累积 258 条合理），而 `config_drift` 是**状态型**——只要没保存就一直存在，每次都插一条的话一周能堆上千条。所以：已有未处理的同类告警不重复新增；running/startup 恢复一致时自动 resolve。**一个不会自己消失的告警，很快就会被无视，那这条检查就白做了。**

## Key Learnings
- [2026-09-20] **running/startup 比对必须重度归一化，否则 100% 误报**（一条总在误报的检查等于没有）。109 对真实样本的实测过程：最初版本 108/109 报差异（全误报）→ 逐类剥离后 **105 一致 / 4 差异**。要剥掉的噪声：`Building configuration...`/`Current configuration : N bytes`/`Using N out of M bytes` 头部、`! Last configuration change at ...`（**两边本来就该不同**）、命令行回显（`SWI01#` / `SWI01# show running-config`）、**证书块**（running 是 `certificate ca 01` + 数十行 hex + `quit`，startup 只有 `certificate ca 01 nvram:xxx.cer` —— 同一条证书两种表示）、`ntp clock-period N`（IOS 自动校准值，NTP 每次校准都改写 running）、空行/分隔行（`!`/`! ! !`/`---`）/行尾空格。**消费方（告警与审计）必须共用同一套归一化**（`utils/config_diff.py`），否则会出现「告警说没问题、审计说有差异」的自相矛盾。
- [2026-09-20] **这条检查第一次跑就抓到真隐患**：SHAD1SWI01（C9500 SVL 对）的 `stackwise-virtual link 1` 在 running 里、不在 startup 里，**且经设备自报时间戳独立印证**——`! Last configuration change at 6/30 13:58` vs `! NVRAM config last updated at 6/25 21:36`，即 6/30 的改动从未保存。设备一重启，SVL 链路配置会丢。**交叉验证的办法很值得复用：设备自己会交代"最后变更时间"与"最后保存时间"。**
- [2026-09-20] **`_save_data` / `_save_to_sqlite` 加参数要加在末尾并带默认值**：这两个函数在 collector_service 里被位置传参调用（测试也直接调），中间插参数会让所有后续实参错位（本次导致 21 个测试失败）。`_save_to_sqlite` 的调用点用的是关键字传参，所以只需在它签名末尾加 `startup_config: str = ""`。
- [2026-09-20] **`_seed_remediation_hints` 原来"表非空就跳过"** → 新增的告警类型永远进不了已有库（老库 count 早 > 0）。已改为**按 alert_type 补缺**。

## Decision Log
- [2026-09-20] **例外登记机制四项定案（用户逐条确认）**：① 存**独立文件** `config/audit/_exceptions.yaml`（不进规则文件：例外是"登记表"，有批准人/到期日/复核生命周期；且 `ruleset_hash` 不被例外增删污染，趋势才能分开判断"标准变没变"与"豁免变没变"——例外有独立 `exceptions_hash`）；② 命中语义 = **保留可见 + 单列一类**（findings 仍带徽章出现，不计入建议统计，单列「已批准例外 N 条」——审计不能悄悄藏东西，但噪声不干扰待办数）；③ 过期 = **自动失效 + 页内提醒**（回到普通统计并标注「例外已过期」，标准页有即将到期/已过期视图；**不进告警表**——审计重跑会重新报出来，避免两套提醒打架）；④ 字段约束 = **理由 + 批准人 + 到期日必填**（默认 180 天，**不允许永久例外**——长期不适用属"标准问题"，应改 `exempt_sites` / 停用规则，走 git 评审）。
- [2026-09-20] **例外两条匹配语义（容易写反）**：① **已撤销的条目不参与匹配**——设备级被撤销后，站点级应重新生效，而不是"这条规则从此无人豁免"；② **生效中的优先于已过期的**——设备级过期、站点级还有效时应当用站点级豁免；只有全都没生效，才拿最具体的过期条目去标注「例外已过期」。两者都有专门的测试钉住。
- [2026-09-20] **例外注册表**用「事实字段 + 推导状态」：文件里只存 approved_at / expires_at / revoked 事实，status（active/expiring/expired/revoked）一律由 `engine.exception_status()` 推导——存字段就会与日期打架。撤销 = 软删除（写 revoked 块），历史审计里的 exempt_by 要能永远查到出处。

## Key Learnings
- [2026-09-20] **`present_regex` 的语义是"应该有"（未命中 pattern 才出建议），不是"命中即报"**；`absent_regex` / `present_flag` 才是"命中即报"。写例外测试时按"命中即报"选了 present_regex，结果规则反向触发、11 条用例失败。（见 buglog 2026-09-20）
- [2026-09-20] **等价性回归的可复用做法**：`git worktree add <临时目录> HEAD` 拉出改动前的代码 → 用同一个脚本（`F:\temp\eq_check.py`：显式设 `dbmod._db_path` 指向主库、不走 init_db）分别跑改动前/后 → `diff` 两份 JSON。本次结果：36 台逐设备逐规则 **486 = 486 完全一致**。比"人肉推理不会变"可靠得多。
- [2026-09-20] **主库 schema 可能落后于代码**：迁移只在 `init_db()`（服务启动 / 脚本调用）时执行。本次发现主库还停在 v13（无 `startup_config` 列），因为上次改完代码后服务没重启过。**跑任何依赖新列的脚本前，先 `init_db('./data')` 把库升到最新**。
- [2026-09-20] **例外机制的关键实现点**：`analyze()` 读 `std.get("exceptions") or []`（签名不变，大量测试用 `make_std()` 合成字典没有该键）；`counts` 五档只数未豁免的，另有 `exempt_count`；`audit_findings` 增 `exempt_by`/`exempt_json`（**快照**：批准人/依据/到期日——历史审计要能回答"那次审计时它被谁批的"，不能只存 id 再去 YAML 现查），`audit_runs` 增 `exceptions_hash`/`exempt_count`（v15 迁移）。`_exceptions.yaml` 的可选文件语义：不存在 = 空登记表，不是错误。
- [2026-09-20] **UI 测试可绕过登录门槛**：`sessionStorage['ndm_session']`（`{username, password, deviceIp, expiresAt}`，base64 编码）预置一个假会话即可进入页面——审计端点本身不校验会话，登录只是前端路由门槛。仅用于本地 UI 实测，不要写入任何文档或提交。

## Decision Log
- [2026-09-20] **趋势页五项定案（用户）**：① 位置 = **新建独立页「配置审计」**（标准 vs 结果分开）；② 触发 = **采集后自动跑 + 手工触发**；③ 图表粒度 = **每周取该周最后一次运行**（与"配置按周存/流量周锚定"惯例一致），**本周尚无运行则不画该周**（否则周一会把上周数据画成本周）；④ **榜与图同基准**（最新周最后一条 vs 上一周最后一条 —— 避免"榜变了但图没动"）；⑤ 头部显示**最新一次**统计。
- [2026-09-20] **采集后自动跑用服务端去抖，不在前端批次结束处触发**：采集是前端 worker 队列逐台调单设备端点，服务端没有"批次"概念；去抖（每台成功重置 60 秒定时器，静默后跑一轮）同时覆盖 UI 批量与 CLI 采集，一批只跑一轮且跑的时候数据完整。**失败隔离是硬要求**：调度与执行全程 try/except，审计任何异常都不能拖累采集。开关 `settings.yaml → audit.run_after_collect`（默认开）。

## Decision Log
- [2026-09-20] **设备生命周期（EoL + 保修）定案（用户）**：① **双轨**——Cisco 走 EoX API（凭据到位前手工兜底），Aruba 手工（**无公开 API**，已核实）；② **保修期按手工编辑设计**（Cisco SN2INFO 仅对 SNTC 客户/PSS 伙伴开放，HPE 无 API —— 手工不是兜底而是主路径）；③ **有信息且有问题 → 风险提示；没信息 → 「待查」算建议**（不让未登记设备静默通过）；④ 「待查」**聚合**（≥3 台折叠成一条，`collapse_collective`）；⑤ 登记超过 365 天未复核重新算「待查」。
- [2026-09-20] **生命周期数据进 DB（v16 两张表），不进 YAML** —— 与例外机制相反：例外是"决策记录"（谁批的、到期复核，要 git 追溯）；EoL/保修是**设备事实数据**（随 API 刷新、条数多、且要"手工值不被自动刷新覆盖"）。DAL 用 `source=api|manual` + `force` 表达覆盖语义。
- [2026-09-20] **新增通用机制 `engine.collapse_collective()`**：规则标 `collective: true` 时，全量审计命中 ≥ 阈值（默认 3，`params.collective_threshold` 可调）折叠成**一条网络级条目**（`device_name='全网'`，列出设备名）。同时补上了一期承诺但未实现的「集体性漏配单独成类」。runner 的顺序固定为**先收集 → 折叠 → 落库**（边判边写就没法折叠）。

## Decision Log
- [2026-09-20] **AI 专家简报定案（用户）**：**单台 + 全网两份**都做。铁律 = **判定归引擎、叙事归 AI**（prompt 硬约束"不得新增任何未列出的问题、命令、日期"）；不喂配置原文；发送前所有文本过 `utils/redact`（凭据值不外发）；**不落库**（讲解随时可重新生成）；LLM 不可用 → 可读 400，审计不受影响。
- [2026-09-20] **凭据打码是独立纪律项**：`utils/redact.py` 按行打码（团体字/各类 key/auth-priv/Cisco 哈希/ciphertext），**保留命令与加密类型数字**（"配了什么、用了哪种加密"是有用信息）。原则"宁可多打不可漏打"。

## Key Learnings
- [2026-09-20] **真实 LLM 验证结果（DeepSeek）**：单台简报能识别"管理面三条（MGMT_ACL/SNMP 团体字/SNMPv3）是同一件事的三个面"、指出"DAI 依赖 DHCP snooping"的配套关系、如实说"生命周期这块没有数据"——**且未编造任何规则 id**（自动抽查：正文提到的 id ⊆ 给定条目）。这正是总计划要的"资深专家评审"效果。全网简报同理，并会主动标注"标准变过，条目变化不一定代表设备变差"。
- [2026-09-20] **两个接线坑（都在本次踩到并留下测试）**：① SQLite 连接**不能跨线程** —— `asyncio.to_thread` 里不能读库，正确做法是"读库在主线程、只把阻塞的 LLM 调用放进线程"；② 用 `cat >>` 追加代码时 **cwd 漂移会写错目录**（仓库根目录有个历史遗留 `tests/`，害我查了半天 ModuleNotFoundError）——写文件一律 Write/Edit + 绝对路径。
- [2026-09-20] **trends 查询核心提取到 `analyzers/compliance/trends.py`**：API 与简报共用同一口径；放在 api 层会让 services 反向依赖，且服务里 `asyncio.run` 调异步端点会在运行中的事件循环里炸。
- [2026-09-20] **Cisco EoX API 事实**（调研确认）：4 个方法 `EOXByProductID`（每次 ≤20 个型号，支持通配符）/`EOXBySerialNumber`/`EOXByDates`/`EOXBySWReleaseString`；OAuth2 凭据来自 `apiconsole.cisco.com`；返回 `EndOfSaleDate`/`LastDateOfSupport`/公告号与链接。**保修是另一套**：`SN2INFO`（`/product/v1.0/coverage/summary/serial_numbers/…` 给 `warranty_end_date`）**仅 PSS 伙伴 / SNTC 客户可用**。Aruba/HPE 两者都只有网页表单。
- [2026-09-20] **多入口接线是这类功能的典型坑**：同一份新数据往往要接 `runner`（全量）与 `_envelope`（单台）**两条路径** —— 本次只接了 runner，单台审计就一直报"待查"（幸而浏览器复验抓到了，见 bug-200）。改这类"上下文注入"时，**先 grep 这个参数名在哪些调用点出现**，一处不能漏。
- [2026-09-20] **串行号/型号在库里是逗号拼接的成员串**（`SG30LMQ17K, SG30LMQ108` / `JL659A, JL659A`）—— 11 台堆叠设备各有 2–3 个成员。`lifecycle_dal.split_serials()` 负责拆分；匹配用大写归一化。判定器要把 `extra_rows`（登记过但当前采集不到的序列号）也算上，否则成员换件/采集缺列会丢数据。

## Key Learnings
- [2026-09-20] **周格式是 `YYYY-WW`（如 `2026-38`），不是 ISO 的 `2026-W38`** —— 与 `collections.week` 保持一致。`_iso_week()` 用 `isocalendar()` 但输出不带 `W`（写测试时按 ISO 写法踩过一次）。
- [2026-09-20] **趋势口径与实现**：建议数 = **未豁免** findings（`json_extract(exempt_json,'$.status') IN ('active','expiring')` 的排除掉，SQLite JSON1 可用）；例外数 = 生效中 + 即将到期；站点过滤走 `LEFT JOIN devices ON d.name = af.device_name`（设备改名/删除时退化为"无站点"，不算错）。所有趋势/榜数据**查询侧聚合**，不加表。
- [2026-09-20] **审计结果主页的信息层级**：最近一次（用户最关心"现在"）→ 趋势图 → 收敛/恶化榜 → 历史表（点开下钻）。`audit_runs` 里 v15 之前的老记录 `exceptions_hash` 为 NULL，与后续比较会显示"已变"——属正常，不是 bug。
- [2026-09-20] `nav.audit` 文案一期就已预留在 i18n 里（'配置审计' / 'Config Audit'），新增页面直接复用；**加 i18n 键前先 grep 一遍**，否则会撞出 TS1117 重复键。

## Do-Not-Repeat
- [2026-09-20] **别把 `present_regex` 当"命中即报"**：它的语义是「该配置**应该有**」——**未命中 pattern 才出建议**；`absent_regex` / `present_flag` 才是"命中即报"。写规则或写测试前先看 `checks.py` 里判定器的 docstring，别按名字猜（本次因此 11 条测试失败）。
- [2026-09-20] **跑依赖新 schema 列的脚本/回归前，先确认主库已迁移**（`init_db('./data')`）：迁移只在 init_db 时执行，服务不重启库就停在旧版本（本次主库停在 v13，`startup_config` 列不存在）。

## 当前状态（2026-09-20 收尾）
**第一期全部完成**：A 引擎+规则库 ✅ / B v13 迁移 ✅ / C API ✅ / D 前端 ✅ / E 测试 ✅ / 定案 1 startup-config ✅
- 规则库 **59 条**（公司总部 29 / 厂商基线 21 / 组织规范 9）；schema **v14**
- 测试 **355 项全绿**；移植等价性回归（按 netstd 原 26 条规则 id 过滤）仍 **207 = 207**
- 后端可 `python backend/main.py` 启动（8002），前端已构建进 `frontend/dist`
- **二期进展（2026-09-20 晚）**：**例外登记机制 ✅** + **审计趋势与历史页 ✅** 完成。
  - 例外：设计+计划 `docs/superpowers/plans/2026-09-20-exceptions-registry.md`；提交链 5f6e425 → 246b7f1 → 3ca81b0 → fa5a0e0 → 1213a2d → 7237d88；浏览器实测通过（登记→计数 7→6 + 灰徽章；撤销→恢复）。
  - 趋势：计划 `docs/superpowers/plans/2026-09-20-audit-trends.md`；提交链 2836c54 → 40ef6a9（提取 runner）→ 02b0369（趋势/对比端点）→ d8cd37e（采集后自动跑）→ 9a2630d（新页面）；浏览器实测通过（触发→toast+新记录；下钻明细 486 条、档位筛选 238/486）；采集后自动跑真实链路验证（run 4, trigger=post_collect, 969 ms）。
  - schema **v15**；测试 **401 项全绿**；等价性回归 486=486；主库现有 4 条运行记录（10:03 用户/12:50 验证/13:01 页面按钮/13:0x post_collect）。
- **二期进展（2026-09-20 深夜）**：**设备生命周期（EoL + 保修期）✅** —— 计划 `docs/superpowers/plans/2026-09-20-device-lifecycle.md`；提交链 90fd17e（计划）→ fb7b80c（v16 + DAL）→ 41d5976（EoX 客户端）→ b356c1a（API）→ 37477e4（三规则 + 折叠）→ 825b753（接线修复）→ 0207abc（前端卡片）。schema **v16**；测试 **443 项全绿**；等价性：禁用三条新规则后 **486 且逐设备逐规则与改动前一致**；浏览器实测通过（登记保修 → 审计报「保修已于 2025-03-31 过期（538 天前）」；批量导入回显匹配/未匹配/坏行；刷新未配凭据给可读原因）。
- **二期进展（2026-09-20 收尾）**：**AI 专家简报 ✅ —— 二期四项全部完成**。计划 `docs/superpowers/plans/2026-09-20-ai-briefing.md`；提交链 79969e6（计划）→ afd9368（打码）→ 426472f（trends 提取）→ 2a1b3aa（打码修复）→ 1116006（简报服务）→ ab79ecd（端点）→ 592cdaf（前端）。测试 **466 项全绿**；真实 DeepSeek 调用实测通过（单台 + 全网）。
- **待办（二期之后 / 外部依赖）**：① Cisco EoX 凭据到位后**实盘验证刷新**（用户正在办 API Console 注册）；② 问清 SNTC 订阅以决定保修能否自动化；③ **CUI/CMMC/等保 待用户向合规口确认** —— 简报会把审计条目（已打码凭据、不含配置原文）发给第三方 LLM，若确认涉及 CUI 需重新评估；④ 生命周期数据需要用户登记（Aruba 18 台 EoL + 各家保修，走批量导入）；⑤ 清理项：`port_snapshots.is_uplink`、前端 `deviceApi.batchCollect` 死代码。
