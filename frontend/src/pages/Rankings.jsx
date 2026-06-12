// frontend/src/pages/Rankings.jsx
import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDistrictRankings } from '../hooks/useDistrict';
import { DistrictRankingRow } from '../components/District/DistrictRanking';
import { getScoreColor, formatCurrency } from '../utils/scoreColors';
import { Download, ChevronUp, ChevronDown } from 'lucide-react';

const STATES = [
  '', 'UP', 'BR', 'MP', 'RJ', 'MH', 'WB', 'TN', 'KA', 'GJ', 'AP', 'TS', 'OR', 'KL', 'HR', 'PB', 'UK', 'HP', 'JH', 'CG', 'AS',
];

export default function Rankings() {
  const [stateFilter, setStateFilter] = useState('');
  const [sortBy, setSortBy] = useState('accountability_score');
  const [sortDir, setSortDir] = useState('desc');
  const navigate = useNavigate();

  const { rankings, loading } = useDistrictRankings({ state: stateFilter || undefined, sort_by: sortBy, limit: 200 });

  const sorted = useMemo(() => {
    if (!rankings?.length) return [];
    return [...rankings].sort((a, b) => {
      const va = a[sortBy] ?? 0;
      const vb = b[sortBy] ?? 0;
      return sortDir === 'asc' ? va - vb : vb - va;
    });
  }, [rankings, sortBy, sortDir]);

  const handleSort = (col) => {
    if (sortBy === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(col); setSortDir('desc'); }
  };

  const handleExportCsv = () => {
    const headers = ['Rank', 'District', 'State', 'Score', 'Ghost Schools', 'Funds at Risk', 'Trend', 'Unresolved'];
    const rows = sorted.map(r => [
      r.rank, r.district_name, r.state_name, r.accountability_score?.toFixed(1),
      r.ghost_count, r.funds_at_risk?.toFixed(0), r.trend, r.unresolved_notices,
    ]);
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'SkyAudit_Rankings.csv'; a.click();
  };

  const SortIcon = ({ col }) => {
    if (sortBy !== col) return <ChevronDown size={13} className="text-gray-300 inline ml-1" />;
    return sortDir === 'asc'
      ? <ChevronUp size={13} className="text-blue-600 inline ml-1" />
      : <ChevronDown size={13} className="text-blue-600 inline ml-1" />;
  };

  return (
    <div className="pt-14 min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">District Rankings</h1>
            <p className="text-sm text-gray-500 mt-1">
              {sorted.length} districts ranked by accountability score
            </p>
          </div>
          <div className="flex gap-2">
            <select
              value={stateFilter}
              onChange={e => setStateFilter(e.target.value)}
              className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white focus:outline-none focus:border-blue-500"
            >
              <option value="">All States</option>
              {STATES.filter(Boolean).map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <button
              onClick={handleExportCsv}
              className="flex items-center gap-1.5 px-3 py-2 border border-gray-300 bg-white rounded-lg text-sm hover:bg-gray-50"
            >
              <Download size={14} /> CSV
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 border-b">
                  {[
                    ['rank', 'Rank'],
                    ['district_name', 'District'],
                    ['accountability_score', 'Score'],
                    ['ghost_count', 'Ghost Schools'],
                    ['funds_at_risk', 'Funds at Risk'],
                    ['trend', 'Trend'],
                    ['unresolved_notices', 'Unresolved'],
                  ].map(([col, label]) => (
                    <th
                      key={col}
                      onClick={() => handleSort(col)}
                      className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide cursor-pointer hover:text-gray-900 whitespace-nowrap"
                    >
                      {label}<SortIcon col={col} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 15 }).map((_, i) => (
                    <tr key={i} className="border-b">
                      {Array.from({ length: 7 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 bg-gray-100 rounded animate-pulse" />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : sorted.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-center py-12 text-gray-400">No rankings available</td>
                  </tr>
                ) : sorted.map(r => (
                  <DistrictRankingRow
                    key={r.district_code}
                    ranking={r}
                    onClick={() => navigate(`/district/${r.district_code}`)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
