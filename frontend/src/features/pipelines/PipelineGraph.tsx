import type { PipelineStepRead } from '@/lib/api/pipelines'

interface StepStatus {
  status?: 'success' | 'error' | 'skipped'
}

interface Props {
  steps: PipelineStepRead[]
  stepStatuses?: Record<number, StepStatus>
  mergeStrategy: string
  hasOutputTransform?: boolean
}

function nodeColor(type: string, status?: string): string {
  if (status === 'success') return '#22c55e'
  if (status === 'error') return '#ef4444'
  if (status === 'skipped') return '#94a3b8'
  return type === 'soap' ? '#3b82f6' : '#10b981'
}

function groupSteps(steps: PipelineStepRead[]): PipelineStepRead[][] {
  const map = new Map<number, PipelineStepRead[]>()
  for (const s of [...steps].sort((a, b) => a.step_order - b.step_order)) {
    const g = map.get(s.step_order) ?? []
    g.push(s)
    map.set(s.step_order, g)
  }
  return Array.from(map.values())
}

const NODE_W = 160
const NODE_H = 52
const H_GAP = 20
const V_GAP = 60
const BOX_PADDING = 24

export function PipelineGraph({ steps, stepStatuses = {}, mergeStrategy, hasOutputTransform }: Props) {
  const groups = groupSteps(steps)

  // Calculate SVG dimensions
  const maxGroupWidth = Math.max(...groups.map((g) => g.length * NODE_W + (g.length - 1) * H_GAP))
  const svgWidth = Math.max(maxGroupWidth + BOX_PADDING * 2, 300)

  const inputH = 32
  const fuseH = 32
  const transformH = hasOutputTransform ? 32 + V_GAP : 0
  const outputH = 32
  const svgHeight =
    inputH +
    V_GAP +
    groups.length * (NODE_H + V_GAP) +
    fuseH +
    transformH +
    V_GAP +
    outputH +
    BOX_PADDING * 2

  let y = BOX_PADDING

  const elements: React.ReactNode[] = []
  const cx = svgWidth / 2

  // Input
  elements.push(
    <g key="input">
      <rect x={cx - 70} y={y} width={140} height={inputH} rx={8} fill="#f1f5f9" stroke="#cbd5e1" strokeWidth={1.5} />
      <text x={cx} y={y + 21} textAnchor="middle" fontSize={12} fill="#475569" fontWeight={600}>
        Input params
      </text>
    </g>,
  )
  y += inputH

  // Arrow down
  elements.push(<line key="arr-input" x1={cx} y1={y} x2={cx} y2={y + V_GAP / 2} stroke="#94a3b8" strokeWidth={1.5} markerEnd="url(#arrow)" />)
  y += V_GAP / 2

  // Groups
  for (let gi = 0; gi < groups.length; gi++) {
    const group = groups[gi]
    const totalGroupW = group.length * NODE_W + (group.length - 1) * H_GAP
    const startX = cx - totalGroupW / 2

    // Draw parallel bracket if multiple
    if (group.length > 1) {
      const bracketY = y - 4
      elements.push(
        <rect
          key={`bracket-${gi}`}
          x={startX - 8}
          y={bracketY}
          width={totalGroupW + 16}
          height={NODE_H + 8}
          rx={6}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={1.5}
          strokeDasharray="4 3"
        />,
      )
    }

    for (let si = 0; si < group.length; si++) {
      const step = group[si]
      const nx = startX + si * (NODE_W + H_GAP)
      const status = stepStatuses[step.step_order]?.status
      const fill = nodeColor(step.connector_type, status)

      elements.push(
        <g key={`step-${step.id}`}>
          <rect x={nx} y={y} width={NODE_W} height={NODE_H} rx={8} fill={fill} />
          <text x={nx + NODE_W / 2} y={y + 18} textAnchor="middle" fontSize={11} fill="white" fontWeight={700}>
            {step.name.length > 18 ? step.name.slice(0, 17) + '…' : step.name}
          </text>
          <text x={nx + NODE_W / 2} y={y + 34} textAnchor="middle" fontSize={10} fill="rgba(255,255,255,0.85)">
            {step.connector_name.length > 20 ? step.connector_name.slice(0, 19) + '…' : step.connector_name}
          </text>
          {/* Step order badge */}
          <circle cx={nx + 14} cy={y + 14} r={10} fill="rgba(0,0,0,0.2)" />
          <text x={nx + 14} y={y + 18} textAnchor="middle" fontSize={10} fill="white" fontWeight={700}>
            {step.step_order}
          </text>
        </g>,
      )
    }

    y += NODE_H + V_GAP / 2

    if (gi < groups.length - 1) {
      // Arrow to next group
      if (group.length > 1) {
        // Converge lines to center
        const totalGroupW2 = group.length * NODE_W + (group.length - 1) * H_GAP
        const startX2 = cx - totalGroupW2 / 2
        for (let si = 0; si < group.length; si++) {
          const nx = startX2 + si * (NODE_W + H_GAP) + NODE_W / 2
          elements.push(
            <line key={`conv-${gi}-${si}`} x1={nx} y1={y - V_GAP / 2 + NODE_H} x2={cx} y2={y} stroke="#94a3b8" strokeWidth={1} />,
          )
        }
        elements.push(
          <line key={`arr-g-${gi}`} x1={cx} y1={y} x2={cx} y2={y + V_GAP / 2 - 4} stroke="#94a3b8" strokeWidth={1.5} markerEnd="url(#arrow)" />,
        )
      } else {
        elements.push(
          <line key={`arr-g-${gi}`} x1={cx} y1={y - V_GAP / 2 + NODE_H} x2={cx} y2={y} stroke="#94a3b8" strokeWidth={1.5} markerEnd="url(#arrow)" />,
        )
      }
    } else {
      // Arrow to merge
      if (group.length > 1) {
        const totalGroupW2 = group.length * NODE_W + (group.length - 1) * H_GAP
        const startX2 = cx - totalGroupW2 / 2
        for (let si = 0; si < group.length; si++) {
          const nx = startX2 + si * (NODE_W + H_GAP) + NODE_W / 2
          elements.push(
            <line key={`conv-end-${si}`} x1={nx} y1={y - V_GAP / 2 + NODE_H} x2={cx} y2={y + V_GAP / 2 - 4} stroke="#94a3b8" strokeWidth={1} />,
          )
        }
      } else {
        elements.push(
          <line key="arr-to-fuse" x1={cx} y1={y - V_GAP / 2 + NODE_H} x2={cx} y2={y + V_GAP / 2 - 4} stroke="#94a3b8" strokeWidth={1.5} markerEnd="url(#arrow)" />,
        )
      }
    }
    y += V_GAP / 2
  }

  // Merge node
  const fuseLabel = { merge: 'Fusion — merge', first: 'Fusion — premier', last: 'Fusion — dernier', custom: 'Fusion — custom' }[mergeStrategy] ?? 'Fusion'
  elements.push(
    <g key="fuse">
      <rect x={cx - 90} y={y} width={180} height={fuseH} rx={8} fill="#f8fafc" stroke="#e2e8f0" strokeWidth={1.5} />
      <text x={cx} y={y + 21} textAnchor="middle" fontSize={11} fill="#64748b" fontWeight={600}>
        {fuseLabel}
      </text>
    </g>,
  )
  y += fuseH

  if (hasOutputTransform) {
    elements.push(<line key="arr-fuse-transform" x1={cx} y1={y} x2={cx} y2={y + V_GAP / 2} stroke="#94a3b8" strokeWidth={1.5} markerEnd="url(#arrow)" />)
    y += V_GAP / 2
    elements.push(
      <g key="transform">
        <rect x={cx - 80} y={y} width={160} height={fuseH} rx={8} fill="#faf5ff" stroke="#d8b4fe" strokeWidth={1.5} />
        <text x={cx} y={y + 21} textAnchor="middle" fontSize={11} fill="#7c3aed" fontWeight={600}>
          Transform final
        </text>
      </g>,
    )
    y += fuseH
  }

  elements.push(<line key="arr-fuse-out" x1={cx} y1={y} x2={cx} y2={y + V_GAP / 2} stroke="#94a3b8" strokeWidth={1.5} markerEnd="url(#arrow)" />)
  y += V_GAP / 2

  // Output
  elements.push(
    <g key="output">
      <rect x={cx - 70} y={y} width={140} height={outputH} rx={8} fill="#dcfce7" stroke="#86efac" strokeWidth={1.5} />
      <text x={cx} y={y + 21} textAnchor="middle" fontSize={12} fill="#166534" fontWeight={700}>
        Résultat final
      </text>
    </g>,
  )

  return (
    <svg width={svgWidth} height={svgHeight} className="mx-auto block">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0,0 L0,8 L8,4 z" fill="#94a3b8" />
        </marker>
      </defs>
      {elements}
    </svg>
  )
}
