import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from '@xyflow/react'

/**
 * 带端点端口标签的 smoothstep 边。
 *
 * 与 ReactFlow 内置 smoothstep 渲染一致，额外在两端绘制端口号标签：
 *   - srcPort 靠近 source 节点
 *   - tgtPort 靠近 target 节点
 *
 * 碰撞避免通过 edge.data.srcLabelRow / tgtLabelRow 实现：
 *   行 0 = 20px 偏移, 行 1 = 40px, 行 2 = 60px …
 */
export default function LabeledSmoothstepEdge(props: EdgeProps) {
  const { id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, style, markerEnd, markerStart, selected } = props
  const d = data as any

  // smoothstep 路径
  const [path] = getSmoothStepPath({
    sourceX, sourceY, targetX, targetY,
    sourcePosition, targetPosition,
    borderRadius: 40, offset: 40,
  })

  const dimmed = style?.opacity !== undefined && (style.opacity as number) < 0.15
  const hl = !!d.highlighted || !!selected

  const labelBase = {
    fontSize: hl ? 14 : 12,
    fontWeight: hl ? 700 : 500,
    color: hl ? '#2DD46E' : '#1e293b',
    fontFamily: '"Fira Code", monospace',
    pointerEvents: 'all' as const,
    whiteSpace: 'nowrap' as const,
    background: hl ? '#DCFCE7' : 'rgba(255,255,255,0.92)',
    padding: hl ? '2px 6px' : '1px 5px',
    borderRadius: 3,
    opacity: dimmed ? 0 : 1,
  }

  // 标签 Y 偏移: 行 0=20px, 行 1=40px, 行 2=60px…
  const srcDY = 20 + (d.srcLabelRow || 0) * 22
  const tgtDY = 20 + (d.tgtLabelRow || 0) * 22

  // sourcePosition/targetPosition 指示 handle 在节点哪一侧
  const srcAbove = sourcePosition === 'top'
  const tgtAbove = targetPosition === 'top'

  return (
    <>
      <BaseEdge id={id} path={path} style={style} markerEnd={markerEnd} markerStart={markerStart} />
      <EdgeLabelRenderer>
        {d.srcPort && (
          <div
            style={{
              ...labelBase,
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${sourceX}px, ${sourceY + (srcAbove ? -srcDY : srcDY)}px)`,
            }}
            className="nodrag nopan"
          >
            {d.srcPort}
          </div>
        )}
        {d.tgtPort && (
          <div
            style={{
              ...labelBase,
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${targetX}px, ${targetY + (tgtAbove ? -tgtDY : tgtDY)}px)`,
            }}
            className="nodrag nopan"
          >
            {d.tgtPort}
          </div>
        )}
      </EdgeLabelRenderer>
    </>
  )
}
