import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { cycles as cyclesApi } from '../api'

const fmt = n => '₹' + Number(n||0).toLocaleString('en-IN')

export default function CommissionReport() {
  const { cycleId } = useParams()
  const [cycleList, setCycleList] = useState([])
  const [selectedCycle, setSelectedCycle] = useState(cycleId || '')
  const [commissions, setCommissions] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    cyclesApi.list({ page: 1, page_size: 50 }).then(r => {
      setCycleList(r.data.items || [])
      if (!selectedCycle && r.data.items?.length) setSelectedCycle(r.data.items[0].id)
    })
  }, [])

  useEffect(() => {
    if (!selectedCycle) return
    setLoading(true)
    cyclesApi.commissions(selectedCycle, { page: 1, page_size: 500 })
      .then(r => setCommissions(r.data.items || []))
      .finally(() => setLoading(false))
  }, [selectedCycle])

  // Group by distributor to show BA-level totals
  const byBA = {}
  commissions.forEach(c => {
    if (!byBA[c.distributor_id]) byBA[c.distributor_id] = { rows: [], gross: 0, tds: 0, net: 0 }
    byBA[c.distributor_id].rows.push(c)
    byBA[c.distributor_id].gross += c.gross_commission_inr
    byBA[c.distributor_id].tds += c.tds_deducted_inr
    byBA[c.distributor_id].net += c.net_payable_inr
  })

  const totalNet = commissions.reduce((s,c) => s + c.net_payable_inr, 0)
  const totalTds = commissions.reduce((s,c) => s + c.tds_deducted_inr, 0)

  return (
    <div className="p-8">
      <div className="flex items-center gap-4 mb-6">
        <h2 className="text-xl font-bold text-gray-900">Commission Report</h2>
        <select
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
          value={selectedCycle}
          onChange={e => setSelectedCycle(e.target.value)}
        >
          <option value="">Select cycle…</option>
          {cycleList.map(c => <option key={c.id} value={c.id}>{c.cycle_code} ({c.status})</option>)}
        </select>
      </div>

      {selectedCycle && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-green-50 rounded-xl p-4">
              <p className="text-xs text-green-600 font-medium uppercase tracking-wide">Total Net Payout</p>
              <p className="text-2xl font-bold text-green-700 mt-1">{fmt(totalNet)}</p>
            </div>
            <div className="bg-amber-50 rounded-xl p-4">
              <p className="text-xs text-amber-600 font-medium uppercase tracking-wide">Total TDS</p>
              <p className="text-2xl font-bold text-amber-700 mt-1">{fmt(totalTds)}</p>
            </div>
            <div className="bg-indigo-50 rounded-xl p-4">
              <p className="text-xs text-indigo-600 font-medium uppercase tracking-wide">Centers Processed</p>
              <p className="text-2xl font-bold text-indigo-700 mt-1">{commissions.length}</p>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
                <tr>{['BA ID','Center','Rank','Steps','Step Comm','Green Coin','Matching','Maint','Gross','TDS','Net'].map(h=><th key={h} className="px-3 py-3 text-left font-medium">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading && <tr><td colSpan={11} className="px-4 py-8 text-center text-gray-400">Loading…</td></tr>}
                {!loading && commissions.length===0 && <tr><td colSpan={11} className="px-4 py-8 text-center text-gray-400">No commissions for this cycle</td></tr>}
                {!loading && commissions.map(c => (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-3 py-2.5 text-indigo-700 font-mono text-xs">{c.distributor_id}</td>
                    <td className="px-3 py-2.5">
                      <span className="px-1.5 py-0.5 rounded text-xs font-bold text-white" style={{background: [,'#4f46e5','#2563eb','#7c3aed'][c.center_number] || '#6b7280'}}>
                        C{c.center_number || '?'}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-xs text-gray-600">{c.rank_at_cycle}</td>
                    <td className="px-3 py-2.5 font-medium">{c.steps_earned}</td>
                    <td className="px-3 py-2.5">{fmt(c.step_commission_inr)}</td>
                    <td className="px-3 py-2.5 text-green-700">{c.green_coin_income_inr > 0 ? fmt(c.green_coin_income_inr) : '—'}</td>
                    <td className="px-3 py-2.5">{c.matching_bonus_inr > 0 ? fmt(c.matching_bonus_inr) : '—'}</td>
                    <td className="px-3 py-2.5">{c.maintenance_bonus_inr > 0 ? fmt(c.maintenance_bonus_inr) : '—'}</td>
                    <td className="px-3 py-2.5 font-medium">{fmt(c.gross_commission_inr)}</td>
                    <td className="px-3 py-2.5 text-amber-700">{c.tds_deducted_inr > 0 ? fmt(c.tds_deducted_inr) : '—'}</td>
                    <td className="px-3 py-2.5 font-bold text-green-700">{fmt(c.net_payable_inr)}</td>
                  </tr>
                ))}
              </tbody>
              {commissions.length > 0 && (
                <tfoot className="bg-gray-50 text-sm font-semibold">
                  <tr>
                    <td colSpan={8} className="px-3 py-3 text-right text-gray-600">Totals</td>
                    <td className="px-3 py-3">{fmt(commissions.reduce((s,c)=>s+c.gross_commission_inr,0))}</td>
                    <td className="px-3 py-3 text-amber-700">{fmt(totalTds)}</td>
                    <td className="px-3 py-3 text-green-700">{fmt(totalNet)}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </>
      )}
    </div>
  )
}
