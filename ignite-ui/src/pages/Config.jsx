import { useEffect, useState } from 'react'
import { config as api } from '../api'

export default function Config() {
  const [plan, setPlan] = useState(null)
  const [ranks, setRanks] = useState([])
  const [editing, setEditing] = useState(null)
  const [editVal, setEditVal] = useState({})
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.getPlan().then(r => setPlan(r.data))
    api.getRanks().then(r => setRanks(r.data))
  }, [])

  const saveRank = async (id) => {
    setSaving(true)
    try {
      const res = await api.updateRank(id, editVal)
      setRanks(prev => prev.map(r => r.id === id ? res.data : r))
      setEditing(null); setMsg('Rank updated ✓')
    } finally { setSaving(false) }
  }

  return (
    <div className="p-8">
      <h2 className="text-xl font-bold text-gray-900 mb-6">Configuration</h2>

      {msg && <div className="mb-4 bg-green-50 border border-green-200 text-green-800 text-sm rounded-xl px-4 py-3">{msg}</div>}

      {/* Plan config summary */}
      {plan && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-5 mb-8">
          <h3 className="text-sm font-semibold text-indigo-900 mb-3">Plan Parameters (read-only — edit via API)</h3>
          <div className="grid grid-cols-3 gap-3 text-xs text-indigo-800">
            <span>CV per step: <strong>{plan.cv_per_step}</strong></span>
            <span>Flush ratio: <strong>{plan.flush_ratio}×</strong></span>
            <span>TDS rate: <strong>{(plan.tds_rate*100).toFixed(1)}% (Section 194H)</strong></span>
            <span>TDS threshold: <strong>₹{Number(plan.tds_threshold_inr).toLocaleString('en-IN')}</strong></span>
            <span>GST threshold: <strong>₹{Number(plan.gst_threshold_inr).toLocaleString('en-IN')}</strong></span>
            <span>INR rounding: <strong>₹{plan.inr_rounding}</strong></span>
            <span>Coin cap: <strong>{plan.coin_lifetime_cap} lifetime</strong></span>
            <span>Yellow coin interval: <strong>every {plan.yellow_coin_step_interval} steps</strong></span>
            <span>Max centers/BA: <strong>{plan.max_centers_per_ba}</strong></span>
          </div>
        </div>
      )}

      {/* Rank config table */}
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">Rank Configuration (all INR)</h3>
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
            <tr>{['Rank','Min Steps','Min CV','Step Rate (₹)','Max Weekly','Matching Lvls','Maint Bonus','Maint Months','Actions'].map(h=><th key={h} className="px-4 py-3 text-left font-medium">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {ranks.map(r => (
              <tr key={r.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-indigo-700">{r.rank_name}</td>
                <td className="px-4 py-3">{r.min_cumulative_steps}</td>
                <td className="px-4 py-3">{r.min_direct_cv}</td>
                <td className="px-4 py-3 font-medium">
                  {editing===r.id ? (
                    <input type="number" className="border rounded px-2 py-1 w-28 text-sm" defaultValue={r.step_rate_inr}
                      onChange={e => setEditVal(v=>({...v,step_rate_inr:parseInt(e.target.value)}))} />
                  ) : `₹${Number(r.step_rate_inr).toLocaleString('en-IN')}`}
                </td>
                <td className="px-4 py-3">{r.max_weekly_steps ?? '∞'}</td>
                <td className="px-4 py-3">{r.matching_bonus_levels || '—'}</td>
                <td className="px-4 py-3">{r.maintenance_bonus_inr > 0 ? `₹${Number(r.maintenance_bonus_inr).toLocaleString('en-IN')}` : '—'}</td>
                <td className="px-4 py-3">{r.maintenance_hold_months || '—'}</td>
                <td className="px-4 py-3">
                  {editing === r.id ? (
                    <div className="flex gap-1">
                      <button onClick={() => saveRank(r.id)} disabled={saving} className="text-xs text-green-700 border border-green-300 px-2 py-1 rounded hover:bg-green-50">Save</button>
                      <button onClick={() => setEditing(null)} className="text-xs text-gray-500 border px-2 py-1 rounded hover:bg-gray-50">Cancel</button>
                    </div>
                  ) : (
                    <button onClick={() => { setEditing(r.id); setEditVal({}) }} className="text-xs text-indigo-600 hover:underline">Edit</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-400 mt-3">Changes take effect in the next cycle close. Current cycles use the rates that were active when the cycle opened.</p>
    </div>
  )
}
