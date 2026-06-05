import { useEffect, useState } from 'react'
import { distributors as api } from '../api'

export default function Distributors() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [showCenters, setShowCenters] = useState(null) // distributor object
  const [centersData, setCentersData] = useState(null)

  const load = (p = 1, q = search) => {
    setLoading(true)
    api.list({ page: p, page_size: 20, search: q || undefined })
      .then(r => { setItems(r.data.items); setTotal(r.data.total) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const openCenters = async (ba) => {
    setShowCenters(ba)
    const res = await api.getCenters(ba.id)
    setCentersData(res.data)
  }

  const statusColor = s => ({
    active:'bg-green-100 text-green-700', inactive:'bg-gray-100 text-gray-500',
    pending_kyc:'bg-amber-100 text-amber-700', terminated:'bg-red-100 text-red-700'
  })[s] || 'bg-gray-100 text-gray-500'

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-900">Business Associates</h2>
        <button onClick={() => setShowCreate(true)} className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700">+ Add BA</button>
      </div>

      <div className="flex gap-3 mb-4">
        <input className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-72 focus:outline-none focus:ring-2 focus:ring-indigo-400"
          placeholder="Search name or email…" value={search} onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key==='Enter' && load(1, search)} />
        <button onClick={() => load(1)} className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg text-sm hover:bg-gray-200">Search</button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
            <tr>{['BA ID','Name','Email','Phone','Status','Centers','Actions'].map(h=><th key={h} className="px-4 py-3 text-left font-medium">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading && <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Loading…</td></tr>}
            {!loading && items.length===0 && <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No BAs found</td></tr>}
            {items.map(ba => (
              <tr key={ba.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-xs text-indigo-700">{ba.distributor_id}</td>
                <td className="px-4 py-3 font-medium">{ba.full_name}</td>
                <td className="px-4 py-3 text-gray-600">{ba.email}</td>
                <td className="px-4 py-3 text-gray-600">{ba.phone}</td>
                <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(ba.status)}`}>{ba.status}</span></td>
                <td className="px-4 py-3 text-gray-500 text-xs">—</td>
                <td className="px-4 py-3">
                  <button onClick={() => openCenters(ba)} className="text-indigo-600 hover:underline text-xs">Centers</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
          <span>{total} total BAs</span>
          <div className="flex gap-2">
            <button onClick={() => { setPage(p=>p-1); load(page-1) }} disabled={page<=1} className="px-2 py-1 rounded border disabled:opacity-40">←</button>
            <span className="px-2 py-1">Page {page}</span>
            <button onClick={() => { setPage(p=>p+1); load(page+1) }} disabled={page*20>=total} className="px-2 py-1 rounded border disabled:opacity-40">→</button>
          </div>
        </div>
      </div>

      {/* Centers modal */}
      {showCenters && (
        <Modal title={`Tracking Centers — ${showCenters.full_name}`} onClose={() => { setShowCenters(null); setCentersData(null) }}>
          {!centersData ? <p className="text-gray-400 text-sm">Loading…</p> : (
            <>
              <p className="text-sm text-gray-600 mb-4">{centersData.center_count} center(s) active</p>
              {centersData.centers.length === 0 ? (
                <CenterActivation ba={showCenters} onDone={() => { openCenters(showCenters) }} />
              ) : (
                <div className="space-y-2">
                  {centersData.centers.map(c => (
                    <div key={c.center_id} className={`flex items-center gap-4 p-3 rounded-lg border ${c.center_number===1?'border-indigo-300 bg-indigo-50':c.center_number===2?'border-blue-300 bg-blue-50':'border-violet-300 bg-violet-50'}`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold ${c.center_number===1?'bg-indigo-600':c.center_number===2?'bg-blue-600':'bg-violet-600'}`}>C{c.center_number}</div>
                      <div>
                        <p className="text-sm font-medium">Center {c.center_number} {c.center_number===1?'(Primary)':c.center_number===2?'(Left child)':'(Right child)'}</p>
                        <p className="text-xs text-gray-500">Position #{c.position_id} · Depth {c.depth}</p>
                      </div>
                      <span className={`ml-auto px-2 py-0.5 rounded-full text-xs ${c.is_active?'bg-green-100 text-green-700':'bg-gray-100 text-gray-500'}`}>{c.is_active?'Active':'Inactive'}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </Modal>
      )}

      {showCreate && <CreateBAModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load() }} />}
    </div>
  )
}

function CenterActivation({ ba, onDone }) {
  const [sponsorPos, setSponsorPos] = useState('')
  const [count, setCount] = useState('1')
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')

  const activate = async () => {
    setLoading(true); setMsg('')
    try {
      await api.activateCenters(ba.id, { sponsor_position_id: sponsorPos, center_count: parseInt(count) })
      setMsg('Centers activated!'); setTimeout(onDone, 1000)
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Error')
    } finally { setLoading(false) }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-600">This BA has no tracking centers yet. Activate them:</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Sponsor position ID</label>
          <input className="w-full border rounded-lg px-3 py-2 text-sm" type="number" value={sponsorPos} onChange={e=>setSponsorPos(e.target.value)} placeholder="e.g. 1" />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Number of centers</label>
          <select className="w-full border rounded-lg px-3 py-2 text-sm" value={count} onChange={e=>setCount(e.target.value)}>
            <option value="1">1 — Single</option>
            <option value="2">2 — Double</option>
            <option value="3">3 — Triple-header</option>
          </select>
        </div>
      </div>
      {count==='3' && <p className="text-xs text-amber-700 bg-amber-50 rounded-lg p-2">Triple-header: C2 auto-placed as left child of C1, C3 as right child. BA will need 3 product packs/week (₹1,53,000) to keep all centers active.</p>}
      {msg && <p className="text-sm text-indigo-700">{msg}</p>}
      <button onClick={activate} disabled={!sponsorPos||loading} className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
        {loading ? 'Activating…' : `Activate ${count} Center(s)`}
      </button>
    </div>
  )
}

function CreateBAModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ distributor_id:'', full_name:'', email:'', phone:'' })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const set = (k,v) => setForm(f=>({...f,[k]:v}))

  const create = async () => {
    setLoading(true); setErr('')
    try { await api.create(form); onCreated() }
    catch (e) { setErr(e.response?.data?.detail || 'Error') }
    finally { setLoading(false) }
  }

  return (
    <Modal title="Add Business Associate" onClose={onClose}>
      <div className="space-y-3">
        {[['distributor_id','BA ID','e.g. BA-1001'],['full_name','Full Name',''],['email','Email',''],['phone','Phone (10 digit)','9876543210']].map(([k,l,p])=>(
          <div key={k}>
            <label className="text-xs text-gray-500 mb-1 block">{l}</label>
            <input className="w-full border rounded-lg px-3 py-2 text-sm" value={form[k]} onChange={e=>set(k,e.target.value)} placeholder={p} />
          </div>
        ))}
        {err && <p className="text-red-600 text-sm">{err}</p>}
        <button onClick={create} disabled={loading} className="w-full bg-indigo-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
          {loading ? 'Creating…' : 'Create BA'}
        </button>
      </div>
    </Modal>
  )
}

function Modal({ title, children, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-semibold text-gray-900">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl leading-none">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}
