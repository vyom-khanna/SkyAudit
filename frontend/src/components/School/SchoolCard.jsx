import { X, AlertTriangle, Flag, ExternalLink } from 'lucide-react';
import { useSchool } from '../../hooks/useSchool';
import { SatelliteViewer } from '../Map/SatelliteViewer';
import { ModuleScores } from './ModuleScores';
import { ResponseTracker } from '../Feed/ResponseTracker';
import { ShareButton } from '../shared/ShareButton';
import { formatCurrency } from '../../utils/scoreColors';

export default function SchoolCard({ udiseCode, onClose }) {
  const { data, loading, error } = useSchool(udiseCode);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-6 text-center">
        <AlertTriangle className="text-red-400 mb-3" size={32} />
        <p className="text-gray-600">{error || 'School not found'}</p>
      </div>
    );
  }

  const { school, accountability_score, module_results, anomalies, notices, latest_satellite, is_ghost } = data;
  const constructionModule = module_results?.find(m => m.module_id === 2);
  const hasConstruction = constructionModule?.status === 'anomaly' && constructionModule?.satellite_image_url;

  const totalFunds = module_results?.reduce((sum, m) => sum + (m.discrepancy_amount_inr || 0), 0) || 0;
  const latestAnomaly = anomalies?.[0];
  const latestNotice = notices?.[0];

  return (
    <div className="h-full overflow-y-auto bg-white">
      {/* Header */}
      <div className="sticky top-0 bg-white border-b z-10 px-4 py-3 flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <h2 className="font-bold text-gray-900 text-base leading-tight truncate">{school.name}</h2>
          <p className="text-xs text-gray-500 mt-0.5">{school.udise_code} · {school.block}</p>
        </div>
        <button onClick={onClose} className="ml-3 text-gray-400 hover:text-gray-700 shrink-0 mt-0.5">
          <X size={20} />
        </button>
      </div>

      {/* Ghost school banner */}
      {is_ghost && (
        <div className="bg-red-600 text-white px-4 py-3 flex items-center gap-3">
          <AlertTriangle size={20} className="shrink-0" />
          <div>
            <div className="font-bold text-sm">GHOST SCHOOL DETECTED</div>
            <div className="text-xs text-red-200">No building found at reported coordinates</div>
          </div>
        </div>
      )}

      {/* Satellite image */}
      {latest_satellite?.image_url && (
        <div className="px-4 pt-4">
          {hasConstruction ? (
            <SatelliteViewer
              beforeUrl={constructionModule.satellite_image_url}
              afterUrl={constructionModule.evidence_url}
              beforeLabel="Before Grant"
              afterLabel="After Grant"
            />
          ) : (
            <div className="relative h-44 rounded-lg overflow-hidden">
              <img src={latest_satellite.image_url} alt="Satellite" className="w-full h-full object-cover" />
              <div className="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
                Sentinel-2 · {latest_satellite.capture_date}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Score */}
      <div className="px-4 pt-4 pb-2 flex items-center gap-3">
        <div className="text-3xl font-bold text-gray-900">{accountability_score?.toFixed(0)}</div>
        <div>
          <div className="text-xs text-gray-500">Accountability Score</div>
          <div className="w-32 h-2 bg-gray-200 rounded-full overflow-hidden mt-1">
            <div
              className="h-full rounded-full"
              style={{
                width: `${accountability_score}%`,
                background: accountability_score >= 70 ? '#16a34a' : accountability_score >= 40 ? '#f97316' : '#dc2626',
              }}
            />
          </div>
        </div>
      </div>

      {/* Module scores */}
      <div className="px-4 pb-3">
        <ModuleScores modules={module_results} />
      </div>

      {/* Funds at risk */}
      {totalFunds > 0 && (
        <div className="mx-4 mb-3 bg-red-50 border border-red-200 rounded-lg px-3 py-2 flex justify-between items-center">
          <span className="text-sm text-red-700 font-medium">Flagged funds at risk</span>
          <span className="text-red-700 font-bold">{formatCurrency(totalFunds)}</span>
        </div>
      )}

      {/* Response tracker */}
      {latestAnomaly && latestNotice && (
        <div className="px-4 pb-3">
          <ResponseTracker anomaly={latestAnomaly} notices={notices} />
        </div>
      )}

      {/* Actions */}
      <div className="px-4 pb-4 flex gap-2">
        <ShareButton
          url={`${window.location.origin}/school/${school.udise_code}`}
          title={`${school.name} — SkyAudit`}
          className="flex-1 justify-center"
        />
        <button
          onClick={() => window.open(`/school/${school.udise_code}`, '_blank')}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm border border-gray-300 hover:bg-gray-50"
        >
          <ExternalLink size={14} /> Full Report
        </button>
        <button
          onClick={() => window.open(`/school/${school.udise_code}#flag`, '_blank')}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm border border-orange-300 text-orange-700 hover:bg-orange-50"
        >
          <Flag size={14} /> Flag
        </button>
      </div>
    </div>
  );
}
