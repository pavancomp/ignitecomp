import { useEffect, useState } from 'react'
import { cycles as api } from '../api'

const fmt = n => '₹' + Number(n||0).toLocaleString('en-IN')
const statusBadge = s => ({
  open: 'bg-amber-100 text-amber-700',
  closed: 'bg-blue-100 text-blue-700',
  approved: 'bg-green-100 text-green-700',
  cancelled: 'bg-red-100 text-red-700',
})[s] || 'bg-gray-100 text-gray-500'

export default function Cycles() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [polling, setPolling] = useState(null)
  const [msg, setMsg] = useState('')

  const load = () => {
    setLoading(true)
    api.list({ page: 1, page_size: 20 }).then(r => setItems(r.data.items)).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  // Poll while a cycle is processing
  useEffect(() => {
    if (!polling) return
    const id = setInterval(async () => {
      const res = await api.get(polling)
      setItems(prev => prev.map(c => c.id === polling ? res.data : c))
      if (res.data.status !== 'open') { setPolling(null); setMsg(`Cycle closed — ${res.data.distributor_count} BAs, ${res.data.center_count} centers`) }
    }, 3000)
    return () => clearInterval(id)
  }, [polling])

  const close = async (id) => {
    setMsg('Engine started — processing in background…')
    await api.close(id)
    setPolling(id)
    load()
  }

  const approve = async (id) => {
    await api.approve(id)
    setMsg('Payout approved ✓')
    load()
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-900">Cycles</h2>
        <button onClick={() => setShowCreate(true)} className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700">+ New Cycle</button>
      </div>

      {msg && (
        <div className="mb-4 bg-indigo-50 border border-indigo-200 text-indigo-800 text-sm rounded-xl px-4 py-3 flex justify-between">
          {msg}
          <button onClick={() => setMsg('')} className="text-indigo-400 hover:text-indigo-700">×</button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
            <tr>{['Code','Period','BAs','Centers','Payout','TDS','Status','Actions'].map(h=><th key={h} className="px-4 py-3 text-left font-medium">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading && <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">Loading…</td></tr>}
            {!loading && items.length===0 && <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">No cycles yet</td></tr>}
            {items.map(c => (
              <tr key={c.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-indigo-700">{c.cycle_code}</td>
                <td className="px-4 py-3 text-gray-600 text-xs">{c.start_date} → {c.end_date}</td>
                <td className="px-4 py-3">{c.distributor_count}</td>
                <td className="px-4 py-3">{c.center_count}</td>
                <td className="px-4 py-3 font-medium text-green-700">{fmt(c.total_payout_inr)}</td>
                <td className="px-4 py-3 text-amber-700">{fmt(c.total_tds_inr)}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusBadge(c.status)}`}>{c.status}</span>
                  {polling === c.id && <span className="ml-2 text-xs text-indigo-500 animate-pulse">processing…</span>}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    {c.status === 'open' && <button onClick={() => close(c.id)} className="text-xs text-amber-700 border border-amber-300 px-2 py-1 rounded hover:bg-amber-50">Close</button>}
                    {c.status === 'closed' && <button onClick={() => approve(c.id)} className="text-xs text-green-700 border border-green-300 px-2 py-1 rounded hover:bg-green-50">Approve</button>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreate && <CreateCycleModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load() }} />}
    </div>
  )
}

function CreateCycleModal({ onClose, onCreated }) {
  const today = new Date().toISOString().slice(0,10)
  const nextWeek = new Date(Date.now()+7*86400000).toISOString().slice(0,10)
  const [form, setForm] = useState({ cycle_code: `W${new Date().getFullYear()}-${String(Math.ceil((new Date().getTime()-new Date(new Date().getFullYear(),0,1).getTime())/(7*86400000))).padStart(2,'0')}`, cycle_type: 'weekly', start_date: today, end_date: nextWeek })
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
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-semibold">Create Cycle</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl">×</button>
        </div>
        <div className="space-y-3">
          {[['cycle_code','Cycle code',''],['start_date','Start date','date'],['end_date','End date','date']].map(([k,l,t])=>(
            <div key={k}>
              <label className="text-xs text-gray-500 mb-1 block">{l}</label>
              <input type={t||'text'} className="w-full border rounded-lg px-3 py-2 text-sm" value={form[k]} onChange={e=>set(k,e.target.value)} />
            </div>
          ))}
          {err && <p className="text-red-600 text-sm">{err}</p>}
          <button onClick={create} disabled={loading} className="w-full bg-indigo-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
            {loading?'Creating…':'Create Cycle'}
          </button>
        </div>
      </div>
    </div>
  )
}
