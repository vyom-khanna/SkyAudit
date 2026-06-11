import { MapPin, ExternalLink, Share2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getSeverityColor, formatCurrency, timeAgo } from '../../utils/scoreColors';
import { anomalyTypeLabel } from '../../utils/mapUtils';

export function AnomalyCard({ event, isNew = false }) {
  const navigate = useNavigate();

  const severityFromType = (type) => {
    if (type === 'ghost_school') return 'critical';
    if (type === 'construction_fraud') return 'high';
    if (type === 'meal_fraud' || type === 'enrollment_inflation') return 'high';
    return 'medium';
  };

  const severity = severityFromType(event.event_type);
  const borderColor = getSeverityColor(severity);
  const typeLabel = anomalyTypeLabel(event.event_type);

  return (
    <div
      className={`
        relative bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden
        transition-all duration-300
        ${isNew ? 'animate-slide-in ring-2 ring-blue-300' : ''}
      `}
      style={{ borderLeftColor: borderColor, borderLeftWidth: 4 }}
    >
      <div className="px-4 py-3">
        {/* Type badge + time */}
        <div className="flex items-center justify-between mb-1.5">
          <span
            className="text-xs font-bold px-2 py-0.5 rounded text-white"
            style={{ background: borderColor }}
          >
            {typeLabel}
          </span>
          <span className="text-xs text-gray-400">{timeAgo(event.created_at)}</span>
        </div>

        {/* Headline */}
        <h3 className="text-sm font-semibold text-gray-900 leading-snug mb-1">
          {event.headline}
        </h3>

        {/* Summary */}
        <p className="text-xs text-gray-600 leading-relaxed line-clamp-2 mb-2">
          {event.summary}
        </p>

        {/* Location */}
        <div className="flex items-center gap-1 text-xs text-gray-500 mb-2">
          <MapPin size={11} className="shrink-0" />
          {event.school_name} · {event.district_name}, {event.state_name}
        </div>

        {/* Funds at risk */}
        {event.funds_mentioned_inr > 0 && (
          <div className="text-sm font-bold text-red-600 mb-3">
            {formatCurrency(event.funds_mentioned_inr)} at risk
          </div>
        )}

        {/* Satellite thumbnail */}
        {event.satellite_url && (
          <div className="mb-3 h-28 rounded-lg overflow-hidden bg-gray-100">
            <img src={event.satellite_url} alt="Satellite" className="w-full h-full object-cover" />
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={() => navigate(`/school/${event.anomaly_id}`)}
            className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            <MapPin size={12} /> View on Map
          </button>
          <button
            onClick={async () => {
              await navigator.clipboard.writeText(`${window.location.origin}/anomaly/${event.anomaly_id}`);
            }}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 ml-auto"
          >
            <Share2 size={12} /> Share
          </button>
        </div>
      </div>
    </div>
  );
}
