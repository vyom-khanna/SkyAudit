// frontend/src/pages/School.jsx
import { useParams } from 'react-router-dom';
import { useSchool, useSchoolSatellite } from '../hooks/useSchool';
import { ModuleScores } from '../components/School/ModuleScores';
import { ResponseTracker } from '../components/Feed/ResponseTracker';
import { SatelliteViewer } from '../components/Map/SatelliteViewer';
import { ShareButton } from '../components/shared/ShareButton';
import { formatCurrency, getSeverityBg, timeAgo } from '../utils/scoreColors';
import { AccountabilityScore } from '../components/District/AccountabilityScore';
import { AlertTriangle, MapPin, Flag } from 'lucide-react';

export default function School() {
  const { udiseCode } = useParams();
  const { data, loading, error } = useSchool(udiseCode);
  const { data: satData } = useSchoolSatellite(udiseCode);



  if (loading) return (
    <div className="pt-14 h-screen flex items-center justify-center">
      <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (error || !data) return (
    <div className="pt-14 h-screen flex items-center justify-center">
      <p className="text-red-600">{error || 'School not found'}</p>
    </div>
  );

  const { school, accountability_score, module_results, anomalies, notices, is_ghost } = data;
  const totalFunds = module_results?.reduce((s, m) => s + (m.discrepancy_amount_inr || 0), 0) || 0;
  const constructionMod = module_results?.find(m => m.module_id === 2 && m.status === 'anomaly');

  return (
    <div className="pt-14 min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {/* Ghost banner */}
        {is_ghost && (
          <div className="bg-red-600 text-white rounded-xl p-4 flex items-center gap-3">
            <AlertTriangle size={24} className="shrink-0" />
            <div>
              <div className="font-bold">GHOST SCHOOL DETECTED</div>
              <div className="text-sm text-red-200">
                Satellite imagery shows no building at reported coordinates.
                All enrollment and meal claims are fraudulent.
              </div>
            </div>
          </div>
        )}

        {/* Header card */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{school.name}</h1>
              <div className="flex items-center gap-2 mt-1 text-sm text-gray-500">
                <MapPin size={14} />
                {school.block} · UDISE {school.udise_code}
              </div>
              <div className="text-sm text-gray-500">
                {school.district_code} · {school.management_type}
              </div>
            </div>
            <AccountabilityScore score={accountability_score} size="md" />
          </div>

          {totalFunds > 0 && (
            <div className="mt-4 bg-red-50 rounded-lg p-3 flex justify-between items-center">
              <span className="text-red-700 font-medium text-sm">Total Flagged Funds</span>
              <span className="text-red-700 font-bold text-lg">{formatCurrency(totalFunds)}</span>
            </div>
          )}

          <div className="flex gap-2 mt-4">
            <ShareButton title={`${school.name} — SkyAudit`} className="flex-1 justify-center" />

            <button
              className="flex items-center gap-2 px-4 py-2 border border-orange-300 text-orange-700 rounded-lg text-sm hover:bg-orange-50">
              <Flag size={14} /> Flag Issue
            </button>
          </div>
        </div>

        {/* Satellite */}
        {(satData?.before_url || data?.latest_satellite?.image_url) && (
          <div className="bg-white rounded-xl shadow-sm border p-4">
            <h2 className="font-semibold text-gray-800 mb-3">Satellite Imagery</h2>
            {constructionMod?.satellite_image_url ? (
              <SatelliteViewer
                beforeUrl={constructionMod.satellite_image_url}
                afterUrl={constructionMod.evidence_url}
                beforeLabel="Before Grant"
                afterLabel="After Grant"
              />
            ) : (
              <div className="h-56 rounded-lg overflow-hidden">
                <img src={data?.latest_satellite?.image_url} alt="Satellite" className="w-full h-full object-cover" />
              </div>
            )}
          </div>
        )}

        {/* 7 Module results */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="font-semibold text-gray-800 mb-4">Verification Results</h2>
          <ModuleScores modules={module_results} />
        </div>

        {/* Anomalies */}
        {anomalies?.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="font-semibold text-gray-800 mb-4">
              Active Anomalies ({anomalies.length})
            </h2>
            <div className="space-y-4">
              {anomalies.map(a => (
                <div key={a.id} className="border rounded-lg p-4">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded text-white ${getSeverityBg(a.severity)}`}>
                      {a.severity?.toUpperCase()}
                    </span>
                    <span className="text-xs text-gray-400">{timeAgo(a.detected_at)}</span>
                  </div>
                  <p className="text-sm text-gray-700">{a.description}</p>
                  {a.funds_at_risk_inr > 0 && (
                    <p className="text-sm font-bold text-red-600 mt-2">
                      {formatCurrency(a.funds_at_risk_inr)} at risk
                    </p>
                  )}
                  {notices?.length > 0 && (
                    <div className="mt-3">
                      <ResponseTracker anomaly={a} notices={notices.filter(n => n.anomaly_id === a.id)} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
