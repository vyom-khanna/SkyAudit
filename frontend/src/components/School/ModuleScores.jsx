export function ModuleScores({ modules = [] }) {
  const statusConfig = {
    verified: { label: 'Verified', bg: 'bg-green-100', text: 'text-green-700', dot: 'bg-green-500' },
    anomaly: { label: 'Anomaly', bg: 'bg-orange-100', text: 'text-orange-700', dot: 'bg-orange-500' },
    ghost: { label: 'Ghost', bg: 'bg-red-100', text: 'text-red-700', dot: 'bg-red-600' },
    pending: { label: 'Pending', bg: 'bg-gray-100', text: 'text-gray-500', dot: 'bg-gray-400' },
  };

  return (
    <div className="space-y-1.5">
      {modules.map((m) => {
        const cfg = statusConfig[m.status] || statusConfig.pending;
        return (
          <div key={m.module_id} className="flex items-center gap-2 py-1.5 border-b border-gray-100 last:border-0">
            <div className={`w-2 h-2 rounded-full shrink-0 ${cfg.dot}`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium text-gray-700 truncate">{m.module_name}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded font-medium shrink-0 ${cfg.bg} ${cfg.text}`}>
                  {cfg.label}
                </span>
              </div>
              {m.status !== 'verified' && m.reported_value && (
                <div className="text-xs text-gray-500 truncate mt-0.5">
                  Reported: {m.reported_value} → {m.verified_value}
                </div>
              )}
              {m.discrepancy_amount_inr > 0 && (
                <div className="text-xs text-red-600 font-medium mt-0.5">
                  ₹{(m.discrepancy_amount_inr / 100_000).toFixed(1)}L at risk
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
