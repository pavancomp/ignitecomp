import { useEffect, useState } from 'react'
import { cycles as cyclesApi } from '../api'

const fmt = n => '₹' + Number(n || 0).toLocaleString('en-IN')

function Stat({ label, value, sub, color = 'indigo' }) {
  const colors = { indigo: 'bg-indigo-50 text-indigo-700', green: 'bg-green-50 text-green-700', amber: 'bg-amber-50 text-amber-700', red: 'bg-red-50 text-red-700' }
  return (
    <div className={`rounded-xl p-5 ${colors[color]}`}>
      <p className="text-xs font-medium uppercase tracking-wide opacity-70">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs mt-1 opacity-70">{sub}</p>}
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    cyclesApi.list({ page: 1, page_size: 5 })
      .then(r => setData(r.data))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-gray-400">Loading…</div>

  const cycles = data?.items || []
  const latest = cycles[0]

  return (
    <div className="p-8">
      <h2 className="text-xl font-bold text-gray-900 mb-6">Dashboard</h2>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Stat label="Latest Cycle" value={latest?.cycle_code || '—'} sub={latest?.status} color="indigo" />
        <Stat label="Total Payout" value={fmt(latest?.total_payout_inr)} sub="net after TDS" color="green" />
        <Stat label="TDS Deducted" value={fmt(latest?.total_tds_inr)} sub="Section 194H" color="amber" />
        <Stat label="BAs Processed" value={latest?.distributor_count ?? '—'} sub={`${latest?.center_count ?? 0} centers`} color="indigo" />
      </div>

      <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">Recent Cycles</h3>
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
            <tr>
              {['Code','Period','BAs','Centers','Payout','TDS','Status'].map(h => (
                <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {cycles.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No cycles yet</td></tr>
            )}
            {cycles.map(c => (
              <tr key={c.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-indigo-700">{c.cycle_code}</td>
                <td className="px-4 py-3 text-gray-600">{c.start_date} → {c.end_date}</td>
                <td className="px-4 py-3">{c.distributor_count}</td>
                <td className="px-4 py-3">{c.center_count}</td>
                <td className="px-4 py-3 font-medium text-green-700">{fmt(c.total_payout_inr)}</td>
                <td className="px-4 py-3 text-amber-700">{fmt(c.total_tds_inr)}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    c.status==='approved'?'bg-green-100 text-green-700':
                    c.status==='closed'?'bg-blue-100 text-blue-700':
                    c.status==='open'?'bg-amber-100 text-amber-700':
                    'bg-gray-100 text-gray-500'}`}>
                    {c.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
