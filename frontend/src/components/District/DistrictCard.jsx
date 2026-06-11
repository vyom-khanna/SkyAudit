import { TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle, School } from 'lucide-react';
import { AccountabilityScore } from './AccountabilityScore';
import { formatCurrency } from '../../utils/scoreColors';

const MODULE_NAMES = {
  1: 'Ghost Detection', 2: 'Construction', 3: 'Enrollment',
  4: 'Mid-Day Meals', 5: 'Outcomes', 6: 'Teachers', 7: 'Budget',
};

export function DistrictCard({ data }) {
  if (!data) return null;
  const { district, accountability_score, national_rank, total_districts,
          anomaly_counts, module_stats, total_funds_at_risk_inr, trend } = data;

  const TrendIcon = trend === 'improving' ? TrendingUp : trend === 'declining' ? TrendingDown : Minus;
  const trendColor = trend === 'improving' ? 'text-green-600' : trend === 'declining' ? 'text-red-500' : 'text-gray-400';

  return (
    <div className="h-full overflow-y-auto p-5 space-y-5">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-gray-900">{district?.district_name}</h2>
        <p className="text-sm text-gray-500">{district?.state_name}</p>
      </div>

      {/* Score + rank */}
      <div className="flex items-center gap-6">
        <AccountabilityScore score={accountability_score} size="lg" />
        <div className="space-y-2">
          <div>
            <p className="text-xs text-gray-500">National Rank</p>
            <p className="text-lg font-bold text-gray-900">
              #{national_rank} <span className="text-sm font-normal text-gray-400">of {total_districts}</span>
            </p>
          </div>
          <div className="flex items-center gap-1">
            <TrendIcon size={14} className={trendColor} />
            <span className={`text-xs font-medium capitalize ${trendColor}`}>{trend || 'stable'}</span>
          </div>
        </div>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Total Schools', val: district?.total_schools, icon: School, color: 'text-blue-600' },
          { label: 'Flagged', val: district?.flagged_schools, icon: AlertTriangle, color: 'text-orange-500' },
          { label: 'Verified', val: district?.verified_schools, icon: CheckCircle, color: 'text-green-600' },
        ].map(s => (
          <div key={s.label} className="bg-gray-50 rounded-lg p-3 text-center">
            <s.icon size={16} className={`mx-auto mb-1 ${s.color}`} />
            <div className="text-lg font-bold text-gray-900">{s.val?.toLocaleString('en-IN') || '—'}</div>
            <div className="text-xs text-gray-500">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Funds */}
      {total_funds_at_risk_inr > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 flex justify-between">
          <span className="text-sm text-red-700 font-medium">Total Funds at Risk</span>
          <span className="text-red-700 font-bold">{formatCurrency(total_funds_at_risk_inr)}</span>
        </div>
      )}

      {/* Module breakdown */}
      {module_stats && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Module Breakdown</h3>
          <div className="space-y-2">
            {Object.entries(module_stats).map(([id, stat]) => (
              <div key={id} className="flex items-center gap-2">
                <span className="text-xs text-gray-500 w-28 shrink-0">{MODULE_NAMES[id]}</span>
                <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${stat.pct_ok}%`,
                      background: stat.pct_ok >= 80 ? '#16a34a' : stat.pct_ok >= 60 ? '#f97316' : '#dc2626',
                    }}
                  />
                </div>
                <span className="text-xs text-gray-500 w-10 text-right">{stat.pct_ok}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Anomaly type breakdown */}
      {anomaly_counts && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Anomaly Types</h3>
          <div className="space-y-1">
            {Object.entries(anomaly_counts)
              .filter(([, v]) => v > 0)
              .sort(([, a], [, b]) => b - a)
              .map(([type, count]) => (
                <div key={type} className="flex items-center justify-between text-xs">
                  <span className="text-gray-600 capitalize">{type.replace(/_/g, ' ')}</span>
                  <span className="font-semibold text-gray-800">{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
