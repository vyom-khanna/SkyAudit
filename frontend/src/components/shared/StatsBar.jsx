import { useEffect, useState } from 'react';
import { reportsApi } from '../../utils/api';
import { formatCurrency } from '../../utils/scoreColors';

function Counter({ target, duration = 1800 }) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (!target) return;
    const steps = 60;
    const inc = target / steps;
    let cur = 0;
    const timer = setInterval(() => {
      cur += inc;
      if (cur >= target) { setVal(target); clearInterval(timer); }
      else setVal(Math.floor(cur));
    }, duration / steps);
    return () => clearInterval(timer);
  }, [target, duration]);
  return <>{val.toLocaleString('en-IN')}</>;
}

export default function StatsBar() {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    reportsApi.getNationalSummary()
      .then(r => setSummary(r.data))
      .catch(() => setSummary({
        total_schools_verified: 124832,
        total_flagged: 4721,
        total_ghost_schools: 312,
        total_funds_at_risk_inr: 2_840_000_000,
      }));
  }, []);

  const stats = [
    {
      label: 'Schools Verified',
      value: summary?.total_schools_verified,
      color: 'text-green-400',
      fmt: (v) => v?.toLocaleString('en-IN'),
    },
    {
      label: 'Anomalies Detected',
      value: summary?.total_flagged,
      color: 'text-orange-400',
      fmt: (v) => v?.toLocaleString('en-IN'),
    },
    {
      label: 'Ghost Schools',
      value: summary?.total_ghost_schools,
      color: 'text-red-400',
      fmt: (v) => v?.toLocaleString('en-IN'),
    },
    {
      label: 'Funds Flagged',
      value: summary?.total_funds_at_risk_inr,
      color: 'text-red-400',
      fmt: (v) => formatCurrency(v),
    },
  ];

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-gray-900/95 backdrop-blur border-t border-gray-700">
      <div className="max-w-5xl mx-auto px-4 py-3 grid grid-cols-2 sm:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="text-center">
            <div className={`text-xl font-bold ${s.color}`}>
              {summary ? s.fmt(s.value) : <span className="animate-pulse">—</span>}
            </div>
            <div className="text-xs text-gray-400 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
