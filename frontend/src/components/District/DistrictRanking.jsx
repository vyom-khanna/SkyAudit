import { ArrowUp, ArrowDown, Minus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getScoreColor, formatCurrency } from '../../utils/scoreColors';

export function DistrictRankingRow({ ranking, onClick }) {
  const navigate = useNavigate();
  const color = getScoreColor(ranking.accountability_score);

  return (
    <tr
      onClick={() => onClick ? onClick(ranking) : navigate(`/district/${ranking.district_code}`)}
      className="hover:bg-gray-50 cursor-pointer border-b border-gray-100 transition-colors"
    >
      <td className="px-4 py-3 text-sm font-semibold text-gray-600">#{ranking.rank}</td>
      <td className="px-4 py-3">
        <div className="font-medium text-gray-900 text-sm">{ranking.district_name}</div>
        <div className="text-xs text-gray-500">{ranking.state_name}</div>
      </td>
      <td className="px-4 py-3">
        <span className="text-sm font-bold" style={{ color }}>{ranking.accountability_score?.toFixed(1)}</span>
      </td>
      <td className="px-4 py-3 text-sm text-gray-700">{ranking.ghost_count}</td>
      <td className="px-4 py-3">
        <span className={`text-sm font-medium ${ranking.funds_at_risk > 0 ? 'text-red-600' : 'text-gray-400'}`}>
          {ranking.funds_at_risk > 0 ? formatCurrency(ranking.funds_at_risk) : '—'}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className={`text-xs capitalize ${
          ranking.trend === 'improving' ? 'text-green-600' :
          ranking.trend === 'declining' ? 'text-red-500' : 'text-gray-400'
        }`}>
          {ranking.trend}
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-gray-600">{ranking.unresolved_notices}</td>
    </tr>
  );
}
