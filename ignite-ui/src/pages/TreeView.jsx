import { useEffect, useState, useRef } from 'react'
import { distributors as api } from '../api'

const CENTER_COLORS = { 1: '#4f46e5', 2: '#2563eb', 3: '#7c3aed' }
const CENTER_LABELS = { 1: 'C1', 2: 'C2', 3: 'C3' }

const NODE_W = 140, NODE_H = 56, H_GAP = 24, V_GAP = 80

function buildTree(nodes) {
  const byId = {}
  nodes.forEach(n => { byId[n.position_id] = { ...n, children: [] } })
  const roots = []
  nodes.forEach(n => {
    if (n.parent_id && byId[n.parent_id]) byId[n.parent_id].children.push(byId[n.position_id])
    else if (!n.parent_id) roots.push(byId[n.position_id])
  })
  return roots
}

function layoutTree(node, depth = 0, offset = { x: 0 }) {
  if (!node) return null
  const children = (node.children || []).sort((a,b) => (a.leg==='left'?-1:1))
  const laid = []
  let totalW = 0
  for (const child of children) {
    const sub = layoutTree(child, depth+1, offset)
    if (sub) { laid.push(sub); totalW += sub.width }
    totalW += H_GAP
  }
  if (totalW > 0) totalW -= H_GAP
  const width = Math.max(NODE_W, totalW)
  const cx = offset.x + width / 2
  offset.x += width + H_GAP
  return { ...node, cx, cy: depth * (NODE_H + V_GAP) + 40, width, depth, laidChildren: laid }
}

function renderTree(node, edges = [], rects = []) {
  if (!node) return
  rects.push(node)
  for (const child of node.laidChildren || []) {
    edges.push({ x1: node.cx, y1: node.cy + NODE_H/2, x2: child.cx, y2: child.cy - NODE_H/2, leg: child.leg })
    renderTree(child, edges, rects)
  }
}

export default function TreeView() {
  const [nodes, setNodes] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const svgRef = useRef(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 40, y: 20 })

  useEffect(() => {
    api.tree().then(r => setNodes(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-gray-400">Loading tree…</div>

  const roots = buildTree(nodes)
  const offset = { x: 0 }
  const laidRoots = roots.map(r => layoutTree(r, 0, offset))

  const edges = [], rects = []
  laidRoots.forEach(r => renderTree(r, edges, rects))

  const maxX = rects.reduce((m,n) => Math.max(m, n.cx + NODE_W/2), 0) + 40
  const maxY = rects.reduce((m,n) => Math.max(m, n.cy + NODE_H), 0) + 40

  return (
    <div className="p-8 flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-gray-900">Binary Tree</h2>
        <div className="flex items-center gap-3">
          <div className="flex gap-2 text-xs">
            {[1,2,3].map(n => (
              <span key={n} className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full inline-block" style={{background:CENTER_COLORS[n]}}></span>
                Center {n}{n===1?' (Primary)':n===2?' (Left)':' (Right)'}
              </span>
            ))}
          </div>
          <div className="flex gap-1">
            <button onClick={() => setZoom(z=>Math.max(0.3,z-0.15))} className="px-2 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200">−</button>
            <button onClick={() => setZoom(1)} className="px-2 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200">{Math.round(zoom*100)}%</button>
            <button onClick={() => setZoom(z=>Math.min(2,z+0.15))} className="px-2 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200">+</button>
          </div>
        </div>
      </div>

      <div className="flex-1 bg-white border border-gray-200 rounded-xl overflow-auto">
        {rects.length === 0 ? (
          <div className="flex items-center justify-center h-64 text-gray-400">No tree nodes yet</div>
        ) : (
          <svg
            ref={svgRef}
            width={maxX * zoom + pan.x * 2}
            height={maxY * zoom + pan.y * 2}
            className="block"
          >
            <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
              {/* Edges */}
              {edges.map((e,i) => (
                <line key={i} x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2}
                  stroke={e.leg==='left'?'#a5b4fc':'#c4b5fd'} strokeWidth={1.5} strokeDasharray={e.leg==='right'?'4 3':undefined} />
              ))}

              {/* Nodes */}
              {rects.map(n => {
                const isSelected = selected?.position_id === n.position_id
                const color = CENTER_COLORS[n.center_number] || '#9ca3af'
                const isRoot = !n.distributor_id || n.distributor_ref === 'ROOT'
                return (
                  <g key={n.position_id} style={{cursor:'pointer'}} onClick={() => setSelected(isSelected ? null : n)}>
                    <rect
                      x={n.cx - NODE_W/2} y={n.cy - NODE_H/2}
                      width={NODE_W} height={NODE_H} rx={8}
                      fill={isRoot?'#f9fafb':isSelected?color:'white'}
                      stroke={isSelected?color:color}
                      strokeWidth={isSelected?2:1.5}
                      opacity={isRoot?0.6:1}
                    />
                    {/* Center badge */}
                    {n.center_number && !isRoot && (
                      <circle cx={n.cx - NODE_W/2 + 14} cy={n.cy - NODE_H/2 + 14} r={11} fill={color} />
                    )}
                    {n.center_number && !isRoot && (
                      <text x={n.cx - NODE_W/2 + 14} y={n.cy - NODE_H/2 + 18} textAnchor="middle" fill="white" fontSize={9} fontWeight="bold">
                        {CENTER_LABELS[n.center_number]}
                      </text>
                    )}
                    <text x={n.cx} y={n.cy - 5} textAnchor="middle" fontSize={11} fontWeight="600" fill={isSelected?'white':isRoot?'#9ca3af':'#1e1b4b'}>
                      {isRoot ? 'ROOT' : (n.distributor_name?.split(' ')[0] || '?')}
                    </text>
                    <text x={n.cx} y={n.cy + 11} textAnchor="middle" fontSize={9} fill={isSelected?'#e0e7ff':'#6b7280'}>
                      {isRoot ? 'Company root' : n.distributor_ref || `P#${n.position_id}`}
                    </text>
                  </g>
                )
              })}
            </g>
          </svg>
        )}
      </div>

      {/* Detail panel */}
      {selected && (
        <div className="mt-4 bg-indigo-50 border border-indigo-200 rounded-xl p-4 text-sm">
          <p className="font-semibold text-indigo-900 mb-2">{selected.distributor_name || 'Unknown'} — {selected.distributor_ref}</p>
          <div className="grid grid-cols-3 gap-3 text-xs text-gray-600">
            <span>Position: <strong>#{selected.position_id}</strong></span>
            <span>Depth: <strong>{selected.depth}</strong></span>
            <span>Leg: <strong>{selected.leg || 'root'}</strong></span>
            <span>Center: <strong>C{selected.center_number || '—'}</strong></span>
            <span>Center ID: <strong>{selected.center_id || '—'}</strong></span>
            <span>Active: <strong>{selected.is_active ? 'Yes' : 'No'}</strong></span>
          </div>
        </div>
      )}
    </div>
  )
}
