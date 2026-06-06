import { useEffect, useState } from 'react'
import { distributors as api, products as productsApi, cycles as cyclesApi, orders as ordersApi } from '../api'

export default function Distributors() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [showCenters, setShowCenters] = useState(null)
  const [centersData, setCentersData] = useState(null)
  const [showOrders, setShowOrders] = useState(null)

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
    active: 'bg-green-100 text-green-700',
    inactive: 'bg-gray-100 text-gray-500',
    pending_kyc: 'bg-amber-100 text-amber-700',
    terminated: 'bg-red-100 text-red-700',
  })[s] || 'bg-gray-100 text-gray-500'

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-900">Business Associates</h2>
        <button onClick={() => setShowCreate(true)}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700">
          + Add BA
        </button>
      </div>

      <div className="flex gap-3 mb-4">
        <input
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-72 focus:outline-none focus:ring-2 focus:ring-indigo-400"
          placeholder="Search name or email…" value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && load(1, search)} />
        <button onClick={() => load(1)}
          className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg text-sm hover:bg-gray-200">
          Search
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
            <tr>
              {['BA ID', 'Name', 'Email', 'Phone', 'Status', 'Actions'].map(h => (
                <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading && <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Loading…</td></tr>}
            {!loading && items.length === 0 && <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">No BAs found</td></tr>}
            {items.map(ba => (
              <tr key={ba.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-xs text-indigo-700">{ba.distributor_id}</td>
                <td className="px-4 py-3 font-medium">{ba.full_name}</td>
                <td className="px-4 py-3 text-gray-600">{ba.email}</td>
                <td className="px-4 py-3 text-gray-600">{ba.phone}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(ba.status)}`}>
                    {ba.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-3">
                    <button onClick={() => openCenters(ba)}
                      className="text-indigo-600 hover:underline text-xs font-medium">
                      Centers
                    </button>
                    <button onClick={() => setShowOrders(ba)}
                      className="text-green-600 hover:underline text-xs font-medium">
                      Orders
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
          <span>{total} total BAs</span>
          <div className="flex gap-2">
            <button onClick={() => { setPage(p => p - 1); load(page - 1) }} disabled={page <= 1}
              className="px-2 py-1 rounded border disabled:opacity-40">←</button>
            <span className="px-2 py-1">Page {page}</span>
            <button onClick={() => { setPage(p => p + 1); load(page + 1) }} disabled={page * 20 >= total}
              className="px-2 py-1 rounded border disabled:opacity-40">→</button>
          </div>
        </div>
      </div>

      {showCenters && (
        <Modal title={`Tracking Centers — ${showCenters.full_name}`}
          onClose={() => { setShowCenters(null); setCentersData(null) }}>
          {!centersData ? <p className="text-gray-400 text-sm">Loading…</p> : (
            <>
              <p className="text-sm text-gray-600 mb-4">{centersData.center_count} center(s) active</p>
              {centersData.centers.length === 0 ? (
                <CenterActivation ba={showCenters} onDone={() => openCenters(showCenters)} />
              ) : (
                <div className="space-y-2">
                  {centersData.centers.map(c => (
                    <div key={c.center_id} className={`flex items-center gap-4 p-3 rounded-lg border
                      ${c.center_number === 1 ? 'border-indigo-300 bg-indigo-50' :
                        c.center_number === 2 ? 'border-blue-300 bg-blue-50' : 'border-violet-300 bg-violet-50'}`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold
                        ${c.center_number === 1 ? 'bg-indigo-600' : c.center_number === 2 ? 'bg-blue-600' : 'bg-violet-600'}`}>
                        C{c.center_number}
                      </div>
                      <div>
                        <p className="text-sm font-medium">
                          Center {c.center_number} {c.center_number === 1 ? '(Primary)' : c.center_number === 2 ? '(Left child)' : '(Right child)'}
                        </p>
                        <p className="text-xs text-gray-500">Position #{c.position_id} · Depth {c.depth}</p>
                      </div>
                      <span className={`ml-auto px-2 py-0.5 rounded-full text-xs
                        ${c.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                        {c.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </Modal>
      )}

      {showOrders && (
        <OrdersModal ba={showOrders} onClose={() => setShowOrders(null)} />
      )}

      {showCreate && (
        <CreateBAModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load() }} />
      )}
    </div>
  )
}

// ── Orders Modal ───────────────────────────────────────────────────────────

function OrdersModal({ ba, onClose }) {
  const [orders, setOrders] = useState([])
  const [products, setProducts] = useState([])
  const [cycles, setCycles] = useState([])
  const [centers, setCenters] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ product_id: '', quantity: '1', cycle_id: '', center_id: '' })
  const [adding, setAdding] = useState(false)
  const [msg, setMsg] = useState({ text: '', ok: true })
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const fmt = n => '₹' + Number(n || 0).toLocaleString('en-IN')

  const load = async () => {
    setLoading(true)
    try {
      const [ordRes, prodRes, cycRes, cenRes] = await Promise.all([
        api.getOrders(ba.id),
        productsApi.list(),
        cyclesApi.list({ page: 1, page_size: 20 }),
        api.getCenters(ba.id),
      ])
      setOrders(ordRes.data)
      setProducts(prodRes.data)
      setCycles((cycRes.data.items || []).filter(c => c.status === 'open'))
      setCenters(cenRes.data.centers || [])
    } catch (e) {
      setMsg({ text: 'Failed to load data', ok: false })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [ba.id])

  const addOrder = async () => {
    if (!form.product_id) return setMsg({ text: 'Select a product', ok: false })
    if (!form.cycle_id)   return setMsg({ text: 'Select an open cycle', ok: false })
    if (centers.length > 1 && !form.center_id)
      return setMsg({ text: 'This BA has multiple centers — select which center to allocate BV to', ok: false })

    setAdding(true); setMsg({ text: '', ok: true })
    try {
      const params = {
        product_id: form.product_id,
        quantity: form.quantity,
        cycle_id: form.cycle_id,
        ...(form.center_id ? { center_id: form.center_id } : {}),
      }
      const res = await api.addOrder(ba.id, params)
      setMsg({ text: `Order ${res.data.order_ref} added — CV: ${res.data.cv_total}`, ok: true })
      setForm(f => ({ ...f, product_id: '', quantity: '1', center_id: '' }))
      load()
    } catch (e) {
      const detail = e.response?.data?.detail
      setMsg({ text: Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : detail || 'Error adding order', ok: false })
    } finally {
      setAdding(false)
    }
  }

  const verifyOrder = async (orderId) => {
    try {
      await ordersApi.verify(orderId)
      setMsg({ text: 'Order verified ✓', ok: true })
      load()
    } catch (e) {
      const detail = e.response?.data?.detail
      setMsg({ text: detail || 'Failed to verify order', ok: false })
    }
  }

  const statusColor = s => ({
    pending: 'text-amber-600 bg-amber-50',
    verified: 'text-green-600 bg-green-50',
    rejected: 'text-red-600 bg-red-50',
  })[s] || 'text-gray-500 bg-gray-50'

  return (
    <Modal title={`Orders — ${ba.full_name}`} onClose={onClose} wide>
      {/* Add order form */}
      <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4 mb-5">
        <p className="text-xs font-semibold text-indigo-700 uppercase tracking-wide mb-3">Add New Order</p>

        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Product *</label>
            <select className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
              value={form.product_id} onChange={e => set('product_id', e.target.value)}>
              <option value="">Select product…</option>
              {products.map(p => (
                <option key={p.id} value={p.id}>
                  {p.name} — {fmt(p.ba_price_inr)} (CV {p.cv})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Quantity *</label>
            <input type="number" min="1" max="10"
              className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
              value={form.quantity} onChange={e => set('quantity', e.target.value)} />
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Open Cycle *</label>
            <select className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
              value={form.cycle_id} onChange={e => set('cycle_id', e.target.value)}>
              <option value="">Select cycle…</option>
              {cycles.length === 0
                ? <option disabled>No open cycles — create one first</option>
                : cycles.map(c => <option key={c.id} value={c.id}>{c.cycle_code}</option>)
              }
            </select>
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">
              Allocate to Center {centers.length > 1 && <span className="text-red-500">*</span>}
            </label>
            <select className="w-full border rounded-lg px-3 py-2 text-sm bg-white"
              value={form.center_id} onChange={e => set('center_id', e.target.value)}>
              <option value="">
                {centers.length <= 1 ? 'Auto (single center)' : 'Select center…'}
              </option>
              {centers.map(c => (
                <option key={c.center_id} value={c.center_id}>
                  C{c.center_number} — {c.center_number === 1 ? 'Primary' : c.center_number === 2 ? 'Left child' : 'Right child'}
                </option>
              ))}
            </select>
            {centers.length > 1 && !form.center_id && (
              <p className="text-xs text-amber-600 mt-1">Required — BV must be allocated to a specific center</p>
            )}
          </div>
        </div>

        {msg.text && (
          <p className={`text-sm mb-2 ${msg.ok ? 'text-green-700' : 'text-red-600'}`}>{msg.text}</p>
        )}

        <button onClick={addOrder} disabled={adding}
          className="bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
          {adding ? 'Adding…' : 'Add Order'}
        </button>
      </div>

      {/* Orders list */}
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Order History ({orders.length})
      </p>

      {loading ? (
        <p className="text-gray-400 text-sm py-4 text-center">Loading…</p>
      ) : orders.length === 0 ? (
        <p className="text-gray-400 text-sm py-4 text-center">No orders yet for this BA</p>
      ) : (
        <div className="max-h-64 overflow-y-auto rounded-lg border border-gray-100">
          <table className="w-full text-xs">
            <thead className="bg-gray-50 sticky top-0">
              <tr>
                {['Ref', 'Date', 'Amount', 'CV', 'Center', 'Status', ''].map(h => (
                  <th key={h} className="px-3 py-2 text-left font-medium text-gray-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {orders.map(o => (
                <tr key={o.id} className="hover:bg-gray-50">
                  <td className="px-3 py-2 font-mono text-indigo-600">{o.order_ref}</td>
                  <td className="px-3 py-2 text-gray-600">{o.order_date}</td>
                  <td className="px-3 py-2 font-medium">{fmt(o.amount_inr)}</td>
                  <td className="px-3 py-2">{o.cv_total}</td>
                  <td className="px-3 py-2">
                    {o.center_id ? <span className="px-1.5 py-0.5 bg-indigo-100 text-indigo-700 rounded text-xs">C{o.center_id}</span> : '—'}
                  </td>
                  <td className="px-3 py-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(o.status)}`}>
                      {o.status}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    {o.status === 'pending' && (
                      <button onClick={() => verifyOrder(o.id)}
                        className="text-xs text-green-600 hover:underline">
                        Verify
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  )
}

// ── Center Activation ──────────────────────────────────────────────────────

function CenterActivation({ ba, onDone }) {
  const [sponsorPos, setSponsorPos] = useState('')
  const [count, setCount] = useState('1')
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')

  const activate = async () => {
    setLoading(true); setMsg('')
    try {
      await api.activateCenters(ba.id, { sponsor_position_id: sponsorPos, center_count: parseInt(count) })
      setMsg('Centers activated!')
      setTimeout(onDone, 1000)
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Error')
    } finally { setLoading(false) }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-600">This BA has no tracking centers yet.</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Sponsor position ID</label>
          <input className="w-full border rounded-lg px-3 py-2 text-sm" type="number"
            value={sponsorPos} onChange={e => setSponsorPos(e.target.value)} placeholder="e.g. 1" />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Number of centers</label>
          <select className="w-full border rounded-lg px-3 py-2 text-sm"
            value={count} onChange={e => setCount(e.target.value)}>
            <option value="1">1 — Single</option>
            <option value="2">2 — Double</option>
            <option value="3">3 — Triple-header</option>
          </select>
        </div>
      </div>
      {count === '3' && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded-lg p-2">
          Triple-header: C2 placed as left child of C1, C3 as right child. Requires 3 product packs/week (₹1,53,000).
        </p>
      )}
      {msg && <p className="text-sm text-indigo-700">{msg}</p>}
      <button onClick={activate} disabled={!sponsorPos || loading}
        className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
        {loading ? 'Activating…' : `Activate ${count} Center(s)`}
      </button>
    </div>
  )
}

// ── Create BA Modal ────────────────────────────────────────────────────────

function CreateBAModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    distributor_id: '', full_name: '', email: '', phone: '',
    pan_number: '', bank_account: '', ifsc_code: '', gstin: '', sponsor_id: '',
  })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const create = async () => {
    setLoading(true); setErr('')
    try {
      const payload = { ...form }
      Object.keys(payload).forEach(k => { if (payload[k] === '') delete payload[k] })
      await api.create(payload)
      onCreated()
    } catch (e) {
      const detail = e.response?.data?.detail
      setErr(Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : detail || 'Error creating BA')
    } finally { setLoading(false) }
  }

  const fields = [
    { k: 'distributor_id', l: 'BA ID *',              p: 'BA-1001',         req: true,  span: 1 },
    { k: 'full_name',      l: 'Full Name *',           p: 'Ravi Shankar',    req: true,  span: 2 },
    { k: 'email',          l: 'Email *',               p: 'ravi@email.com',  req: true,  span: 2 },
    { k: 'phone',          l: 'Mobile (10-digit) *',   p: '9876543210',      req: true,  span: 1 },
    { k: 'pan_number',     l: 'PAN',                   p: 'ABCDE1234F',      req: false, span: 1 },
    { k: 'bank_account',   l: 'Bank Account No',       p: '1234567890',      req: false, span: 1 },
    { k: 'ifsc_code',      l: 'IFSC Code',             p: 'HDFC0001234',     req: false, span: 1 },
    { k: 'gstin',          l: 'GSTIN',                 p: '29ABCDE1234F1Z5', req: false, span: 1 },
  ]

  return (
    <Modal title="Add Business Associate" onClose={onClose}>
      <div className="grid grid-cols-2 gap-3 max-h-96 overflow-y-auto pr-1">
        {fields.map(({ k, l, p, req, span }) => (
          <div key={k} className={span === 2 ? 'col-span-2' : ''}>
            <label className="text-xs text-gray-500 mb-1 block">{l}</label>
            <input
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              value={form[k]} onChange={e => set(k, e.target.value)} placeholder={p} />
          </div>
        ))}
      </div>
      <p className="text-xs text-gray-400 mt-2">* Required. KYC fields can be updated later via the backend API.</p>
      {err && <p className="text-red-600 text-sm mt-2">{err}</p>}
      <button onClick={create}
        disabled={loading || !form.distributor_id || !form.full_name || !form.email || !form.phone}
        className="mt-4 w-full bg-indigo-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
        {loading ? 'Creating…' : 'Create BA'}
      </button>
    </Modal>
  )
}

// ── Modal wrapper ──────────────────────────────────────────────────────────

function Modal({ title, children, onClose, wide = false }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className={`bg-white rounded-2xl shadow-2xl w-full ${wide ? 'max-w-2xl' : 'max-w-lg'} p-6`}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-semibold text-gray-900">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl leading-none">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}
