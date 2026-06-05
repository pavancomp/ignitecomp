import { useEffect, useState } from 'react'
import { compliance as api } from '../api'

const fmt = n => '₹' + Number(n||0).toLocaleString('en-IN')
const currentFY = () => { const d = new Date(); const y = d.getMonth()>=3?d.getFullYear():d.getFullYear()-1; return `${y}-${String(y+1).slice(2)}` }

export default function Compliance() {
  const [fy, setFy] = useState(currentFY())
  const [tds, setTds] = useState(null)
  const [gst, setGst] = useState(null)
  const [tab, setTab] = useState('tds')
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [tdsRes, gstRes] = await Promise.all([api.tdsReport(fy), api.gstFlags(fy)])
      setTds(tdsRes.data); setGst(gstRes.data)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [fy])

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-900">Compliance</h2>
        <select className="border border-gray-300 rounded-lg px-3 py-2 text-sm" value={fy} onChange={e=>setFy(e.target.value)}>
          {['2024-25','2025-26','2026-27'].map(y=><option key={y}>{y}</option>)}
        </select>
      </div>

      <div className="flex gap-3 mb-6">
        {['tds','gst'].map(t => (
          <button key={t} onClick={()=>setTab(t)} className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab===t?'bg-indigo-600 text-white':'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            {t==='tds'?'TDS (194H)':'GST Flags'}
          </button>
        ))}
      </div>

      {tab === 'tds' && tds && (
        <>
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-amber-50 rounded-xl p-4"><p className="text-xs text-amber-600 font-medium uppercase">Total TDS Deducted</p><p className="text-2xl font-bold text-amber-700 mt-1">{fmt(tds.items?.reduce((s,r)=>s+r.tds_deducted_inr,0))}</p></div>
            <div className="bg-indigo-50 rounded-xl p-4"><p className="text-xs text-indigo-600 font-medium uppercase">BAs Above Threshold</p><p className="text-2xl font-bold text-indigo-700 mt-1">{tds.total}</p></div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
                <tr>{['BA ID','Name','PAN','Gross Income','TDS Deducted','Net Income'].map(h=><th key={h} className="px-4 py-3 text-left font-medium">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading && <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Loading…</td></tr>}
                {!loading && (tds.items||[]).map(r=>(
                  <tr key={r.distributor_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-indigo-700 font-mono text-xs">{r.distributor_id}</td>
                    <td className="px-4 py-3 font-medium">{r.distributor_name}</td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-600">{r.pan_number || <span className="text-red-500">Missing</span>}</td>
                    <td className="px-4 py-3">{fmt(r.gross_income_inr)}</td>
                    <td className="px-4 py-3 text-amber-700 font-medium">{fmt(r.tds_deducted_inr)}</td>
                    <td className="px-4 py-3 text-green-700 font-medium">{fmt(r.net_income_inr)}</td>
                  </tr>
                ))}
                {!loading && (tds.items||[]).length===0 && <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">No TDS records for {fy}</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'gst' && gst && (
        <>
          <div className="mb-4 bg-orange-50 border border-orange-200 rounded-xl px-4 py-3 text-sm text-orange-800">
            <strong>{gst.count}</strong> BA(s) have crossed the GST registration threshold of {fmt(gst.threshold_inr)} for FY {fy}. Collect and verify GSTIN before releasing payout.
          </div>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
                <tr>{['BA ID','Name','Gross Income','GSTIN','Registered'].map(h=><th key={h} className="px-4 py-3 text-left font-medium">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(gst.distributors||[]).length===0 && <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">No GST flags for {fy}</td></tr>}
                {(gst.distributors||[]).map(d=>(
                  <tr key={d.distributor_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-indigo-700 font-mono text-xs">{d.distributor_id}</td>
                    <td className="px-4 py-3 font-medium">{d.name}</td>
                    <td className="px-4 py-3 font-bold text-orange-700">{fmt(d.gross_income_inr)}</td>
                    <td className="px-4 py-3 font-mono text-xs">{d.gstin || <span className="text-red-500">Not provided</span>}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${d.gstin_registered?'bg-green-100 text-green-700':'bg-red-100 text-red-600'}`}>
                        {d.gstin_registered ? 'Yes' : 'No'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
