import { toPng } from 'html-to-image'
import type { Edge } from '@xyflow/react'

/**
 * 端点标签碰撞避免 — 贪心分配垂直行。
 *
 * 所有标签默认距离节点边框 20px。同 (nodeId, side) 组内，
 * 按水平位置排序后逐标签检测：若与同行已放置标签碰撞，
 * 则推到 40px；若仍碰撞则 60px…如此类推。绝大多数情况
 * 标签只分两排（20px / 40px）。
 *
 * edge.data 注入:
 *   srcPort / tgtPort — 端口名
 *   srcSide  / tgtSide  — 'top' | 'bottom'
 *   srcLabelRow / tgtLabelRow — 垂直行号 (0=20px, 1=40px, …)
 */
export function assignEndpointLabels(
  edges: Edge[],
  getApproxX: (e: Edge, side: 'src' | 'tgt') => number,
  getSrcPort: (e: Edge) => string,
  getTgtPort: (e: Edge) => string,
): Edge[] {
  // 分组
  type SideItem = { e: Edge; end: 'src' | 'tgt' }
  const groups = new Map<string, SideItem[]>()
  for (const e of edges) {
    for (const end of ['src', 'tgt'] as const) {
      const port = end === 'src' ? getSrcPort(e) : getTgtPort(e)
      if (!port) continue
      const side = (e.data as any)?.[`${end}Side`] || 'bottom'
      const key = `${end === 'src' ? e.source : e.target}:${side}`
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push({ e, end })
    }
  }

  // 每组内贪心分配
  const rowMap = new Map<Edge, Record<string, number>>()
  for (const [, group] of groups) {
    // 按 X 排序
    const sorted = group.map(si => ({
      ...si,
      x: getApproxX(si.e, si.end),
      text: si.end === 'src' ? getSrcPort(si.e) : getTgtPort(si.e),
    })).sort((a, b) => a.x - b.x)

    // 贪心分配行号
    const rowRightmost: number[] = []
    for (const si of sorted) {
      const textW = si.text.length * 9 + 16  // 标签宽度 (含内边距)
      const left = si.x - textW / 2
      const right = si.x + textW / 2

      let row = 0
      while (true) {
        if (row >= rowRightmost.length) rowRightmost.push(-Infinity)
        if (left > rowRightmost[row] + 6) {
          rowRightmost[row] = Math.max(rowRightmost[row], right)
          break
        }
        row++
      }

      if (!rowMap.has(si.e)) rowMap.set(si.e, {})
      rowMap.get(si.e)![si.end === 'src' ? 'srcLabelRow' : 'tgtLabelRow'] = row
    }
  }

  return edges.map(e => {
    const rm = rowMap.get(e) || {}
    const data = { ...(e.data as any) }
    data.srcPort = getSrcPort(e) || undefined
    data.tgtPort = getTgtPort(e) || undefined
    data.srcLabelRow = rm.srcLabelRow ?? 0
    data.tgtLabelRow = rm.tgtLabelRow ?? 0
    // 保留已有的 srcSide/tgtSide (调用方已注入)
    return { ...e, data, label: undefined, labelStyle: undefined, labelBgStyle: undefined }
  })
}

/* CSS 覆盖层：仅处理 HTML 元素的背景和阴影。
 * SVG 元素必须通过 DOM style 属性操作（见下方 exportTopologyAsPng）。 */
const EXPORT_LIGHT_CSS = `
[data-ndm-export] { background-color: #ffffff !important; }

[data-ndm-export] .react-flow__background,
[data-ndm-export] .ndm-hex-grid { display: none !important; }

[data-ndm-export] * { box-shadow: none !important; text-shadow: none !important; }
[data-ndm-export] svg [filter] { filter: none !important; }

[data-ndm-export] [class*="MuiPaper-root"] {
  background-color: #f8fafc !important;
  border-color: #cbd5e1 !important;
}

[data-ndm-export] .MuiTypography-root { color: #1e293b !important; }
`

/** 替换元素 style 属性中的 key 值。
 *  html-to-image 序列化 SVG 时读的是 style 属性字符串，
 *  不是 JS style 对象——必须直接操作属性。 */
function styleAttrReplace(el: Element, key: string, value: string) {
  const prev = el.getAttribute('style') || ''
  const re = new RegExp('\\b' + key + '\\s*:\\s*[^;]+', 'i')
  const next = re.test(prev)
    ? prev.replace(re, key + ': ' + value)
    : (prev ? prev + '; ' + key + ': ' + value : key + ': ' + value)
  el.setAttribute('style', next)
}

/** 导出 ReactFlow 拓扑画布为浅色背景高清 PNG */
export async function exportTopologyAsPng(element: HTMLElement, filename: string): Promise<void> {
  // 1. 注入 CSS
  const styleEl = document.createElement('style')
  styleEl.textContent = EXPORT_LIGHT_CSS
  document.head.appendChild(styleEl)
  element.setAttribute('data-ndm-export', '')

  // 2. 备份 → 修改 → 截图 → 还原
  const backups: { el: Element; style: string }[] = []

  // 边标签文字：浅色 → 深色
  element.querySelectorAll('.react-flow__edge-text').forEach(el => {
    backups.push({ el, style: el.getAttribute('style') || '' })
    styleAttrReplace(el, 'fill', '#1e293b')
  })

  // 高亮边标签：深绿
  element.querySelectorAll('.ndm-edge-highlighted .react-flow__edge-text').forEach(el => {
    styleAttrReplace(el, 'fill', '#166534')
  })

  // 边标签背景：隐藏
  element.querySelectorAll('.react-flow__edge-textbg').forEach(el => {
    backups.push({ el, style: el.getAttribute('style') || '' })
    styleAttrReplace(el, 'fill-opacity', '0')
  })

  // 缩放控件：隐藏
  const controls = document.querySelector('.react-flow__controls') as HTMLElement | null
  if (controls) {
    backups.push({ el: controls, style: controls.getAttribute('style') || '' })
    styleAttrReplace(controls, 'display', 'none')
  }

  // 边端口标签：背景改为不透明
  element.querySelectorAll('.react-flow__edgelabel-renderer > div').forEach(el => {
    backups.push({ el, style: el.getAttribute('style') || '' })
    const prev = el.getAttribute('style') || ''
    const next = prev.replace(
      /background:\s*rgba\(\s*255\s*,\s*255\s*,\s*255\s*,\s*0\.\d+\s*\)/g,
      'background: rgba(255,255,255,1)'
    )
    el.setAttribute('style', next)
  })

  // 节点发光覆盖标签的根因：html-to-image 通过 getComputedStyle
  // 将 Emotion CSS class 中的 boxShadow 内联写入克隆 DOM。
  // Emotion 使用 CSSStyleSheet.insertRule() 注入规则，其 CSSOM 属性
  // 对内联样式/JSDOM/CSS specificity 操作完全免疫。
  // 唯一有效方法：遍历所有 CSS 规则，对包含发光 boxShadow
  // (32px 模糊半径) 的规则直接调用 rule.style.removeProperty，
  // 然后强制重算样式。截图后恢复原值。
  type RuleBackup = { rule: CSSStyleRule; value: string }
  const ruleBackups: RuleBackup[] = []
  for (const sheet of document.styleSheets) {
    try {
      for (const rule of sheet.cssRules) {
        const text = rule.cssText
        if (text.includes('box-shadow') && text.includes('32px')) {
          const sr = rule as CSSStyleRule
          ruleBackups.push({ rule: sr, value: sr.style.boxShadow })
          sr.style.removeProperty('box-shadow')
        }
      }
    } catch (_) { /* cross-origin stylesheet */ }
  }
  // 强制浏览器重新计算所有样式
  document.body.classList.add('__ndm_export_force')
  document.body.offsetHeight
  document.body.classList.remove('__ndm_export_force')

  try {
    const pixelRatio = Math.max(window.devicePixelRatio || 1, 3)
    const url = await toPng(element, { backgroundColor: '#ffffff', pixelRatio })

    const a = document.createElement('a')
    a.download = filename
    a.href = url
    document.body.appendChild(a)
    a.click()
    setTimeout(() => document.body.removeChild(a), 1000)
  } finally {
    // 3. 还原
    element.removeAttribute('data-ndm-export')
    document.head.removeChild(styleEl)
    for (const b of backups) {
      if (b.style) b.el.setAttribute('style', b.style)
      else b.el.removeAttribute('style')
    }
    for (const rb of ruleBackups) {
      rb.rule.style.boxShadow = rb.value
    }
  }
}
