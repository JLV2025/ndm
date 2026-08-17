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
