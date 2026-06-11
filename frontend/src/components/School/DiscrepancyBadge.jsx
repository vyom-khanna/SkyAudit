import { formatCurrency } from '../../utils/scoreColors';

export function DiscrepancyBadge({ amount, label }) {
  if (!amount || amount <= 0) return null;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-100 text-red-700 text-xs font-medium rounded-full border border-red-200">
      {label && <span className="text-red-500">{label}:</span>}
      {formatCurrency(amount)}
    </span>
  );
}
