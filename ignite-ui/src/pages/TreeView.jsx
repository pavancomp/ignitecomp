import { useEffect, useState, useRef } from 'react'
import { distributors as api } from '../api'

const CENTER_COLORS = { 1: '#4f46e5', 2: '#2563eb', 3: '#7c3aed' }
const NODE_W = 148, NODE_H = 58, H_GAP = 40, V_GAP = 90

// ── Layout: post-order traversal, parents centered above children ──────────

function layoutTree(node, depth = 0, offset = { x: 0 }) {
  if (!node) return null

  // Sort children: left leg always first
  const children = (node.children || []).sort((a, b) => a.leg === 'left' ? -1 : 1)

  // Layout children first (post-order)
  const laid = []
  for (const child of children) {
    const sub = layoutTree(child, depth + 1, offset)
    if (sub) laid.push(sub)
  }

  // Position this node
  let cx
  if (laid.length === 0) {
    // Leaf — claim the next slot
    cx = offset.x + NODE_W / 2
    offset.x += NODE_W + H_GAP
  } else if (laid.length === 1) {
    // Single child — sit directly above it
    cx = laid[0].cx
  } else {
    // Two children — center between leftmost and rightmost
    cx = (laid[0].cx + laid[laid.length - 1].cx) / 2
  }

  return {
    ...node,
    cx,
    cy: depth * (NODE_H + V_GAP) + 50,
    laidChildren: laid,
  }
}

function collectNodes(node, edges = [], rects = []) {
  if (!node) return
  rects.push(node)
  for (const child of node.laidChildren || []) {
    edges.push({
      x1: node.cx, y1: node.cy + NODE_H / 2,
      x2: child.cx, y2: child.cy - NODE_H / 2,
      leg: child.leg,
    })
    collectNodes(child, edges, rects)
  }
}

// ── Component ──────────────────────────────────────────────────────────────

export default function TreeView() {
  const [nodes, setNodes] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [zoom, setZoom] = useState(1)

  useEffect(() => {
    api.tree().then(r => setNodes(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-gray-400">Loading tree…</div>

  // Build adjacency structure
  const byId = {}
  nodes.forEach(n => { byId[n.position_id] = { ...n, children: [] } })
  const roots = []
  nodes.forEach(n => {
    if (n.parent_id && byId[n.parent_id]) {
      byId[n.parent_id].children.push(byId[n.position_id])
    } else if (!n.parent_id) {
      roots.push(byId[n.position_id])
    }
  })

  const offset = { x: 20 }
  const laidRoots = roots.map(r => layoutTree(r, 0, offset))

  const edges = [], rects = []
  laidRoots.forEach(r => collectNodes(r, edges, rects))

  const maxX = rects.reduce((m, n) => Math.max(m, n.cx + NODE_W / 2 + 40), 600)
  const maxY = rects.reduce((m, n) => Math.max(m, n.cy + NODE_H + 40), 200)

  return (
    <div className="p-6 flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-gray-900">Binary Tree</h2>
        <div className="flex items-center gap-4">
          {/* Legend */}
          <div className="flex gap-3 text-xs text-gray-600">
            {[1, 2, 3].map(n => (
              <span key={n} className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full inline-block" style={{ background: CENTER_COLORS[n] }} />
                Center {n}{n === 1 ? ' (Primary)' : n === 2 ? ' (Left)' : ' (Right)'}
              </span>
            ))}
          </div>
          {/* Zoom controls */}
          <div className="flex items-center gap-1">
            <button onClick={() => setZoom(z => Math.max(0.3, z - 0.1))}
              className="w-7 h-7 flex items-center justify-center bg-gray-100 rounded hover:bg-gray-200 text-sm">−</button>
            <button onClick={() => setZoom(1)}
              className="px-2 h-7 bg-gray-100 rounded hover:bg-gray-200 text-xs font-medium">
              {Math.round(zoom * 100)}%
            </button>
            <button onClick={() => setZoom(z => Math.min(2, z + 0.1))}
              className="w-7 h-7 flex items-center justify-center bg-gray-100 rounded hover:bg-gray-200 text-sm">+</button>
          </div>
        </div>
      </div>

      {/* Tree canvas */}
      <div className="flex-1 bg-white border border-gray-200 rounded-xl overflow-auto">
        {rects.length === 0 ? (
          <div className="flex items-center justify-center h-64 text-gray-400">No tree nodes yet</div>
        ) : (
          <svg
            width={maxX * zoom + 40}
            height={maxY * zoom + 40}
            className="block mx-auto"
          >
            <g transform={`scale(${zoom})`}>
              {/* Edges */}
              {edges.map((e, i) => (
                <line key={i}
                  x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2}
                  stroke={e.leg === 'left' ? '#a5b4fc' : '#c4b5fd'}
                  strokeWidth={1.5}
                  strokeDasharray={e.leg === 'right' ? '5 3' : undefined}
                />
              ))}

              {/* Nodes */}
              {rects.map(n => {
                const isRoot = !n.distributor_id || n.distributor_ref === 'ROOT'
                const isSelected = selected?.position_id === n.position_id
                const color = CENTER_COLORS[n.center_number] || '#9ca3af'
                const x = n.cx - NODE_W / 2
                const y = n.cy - NODE_H / 2

                return (
                  <g key={n.position_id} style={{ cursor: 'pointer' }}
                    onClick={() => setSelected(isSelected ? null : n)}>
                    {/* Card */}
                    <rect
                      x={x} y={y} width={NODE_W} height={NODE_H} rx={8}
                      fill={isSelected ? color : isRoot ? '#f9fafb' : 'white'}
                      stroke={color}
                      strokeWidth={isSelected ? 2.5 : 1.5}
                    />

                    {/* Center badge */}
                    {n.center_number && !isRoot && (
                      <>
                        <circle cx={x + 16} cy={y + 16} r={11} fill={color} />
                        <text x={x + 16} y={y + 20} textAnchor="middle"
                          fill="white" fontSize={9} fontWeight="bold">
                          C{n.center_number}
                        </text>
                      </>
                    )}

                    {/* Name */}
                    <text
                      x={n.cx} y={n.cy - 6}
                      textAnchor="middle" fontSize={12} fontWeight="600"
                      fill={isSelected ? 'white' : isRoot ? '#9ca3af' : '#1e1b4b'}>
                      {isRoot ? 'ROOT' : (n.distributor_name?.split(' ')[0] || '?')}
                    </text>

                    {/* BA ID */}
                    <text
                      x={n.cx} y={n.cy + 12}
                      textAnchor="middle" fontSize={9}
                      fill={isSelected ? '#e0e7ff' : '#6b7280'}>
                      {isRoot ? 'Company root' : (n.distributor_ref || `#${n.position_id}`)}
                    </text>

                    {/* Leg label */}
                    {n.leg && (
                      <text
                        x={n.leg === 'left' ? x + 6 : x + NODE_W - 6}
                        y={y + NODE_H - 5}
                        textAnchor={n.leg === 'left' ? 'start' : 'end'}
                        fontSize={8} fill={isSelected ? '#c7d2fe' : '#d1d5db'}>
                        {n.leg}
                      </text>
                    )}
                  </g>
                )
              })}
            </g>
          </svg>
        )}
      </div>

      {/* Detail panel */}
      {selected && (
        <div className="mt-3 bg-indigo-50 border border-indigo-200 rounded-xl p-4">
          <p className="font-semibold text-indigo-900 text-sm mb-2">
            {selected.distributor_name || 'Unknown'} — {selected.distributor_ref}
          </p>
          <div className="grid grid-cols-3 gap-2 text-xs text-gray-600">
            <span>Position: <strong>#{selected.position_id}</strong></span>
            <span>Leg: <strong>{selected.leg || 'root'}</strong></span>
            <span>Depth: <strong>{selected.depth}</strong></span>
            <span>Center ID: <strong>{selected.center_id || '—'}</strong></span>
            <span>Center #: <strong>{selected.center_number ? `C${selected.center_number}` : '—'}</strong></span>
            <span>Active: <strong>{selected.is_active ? 'Yes' : 'No'}</strong></span>
          </div>
        </div>
      )}
    </div>
  )
}
