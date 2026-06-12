import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi, anomaliesApi } from '../utils/api';
import { useAnomalies } from '../hooks/useAnomaly';
import { formatCurrency, getSeverityBg, timeAgo } from '../utils/scoreColors';
import { AlertTriangle, CheckCircle, Clock, TrendingUp, X } from 'lucide-react';

function LoginForm({ onLogin }) {
  const [email, setEmail] = useState('demo@skyaudit.in');
  const [password, setPassword] = useState('demo1234');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await authApi.login(email, password);
      localStorage.setItem('skyaudit_token', res.data.access_token);
      const me = await authApi.getMe();
      onLogin(me.data);
    } catch {
      setError('Invalid credentials. Try demo@skyaudit.in / demo1234');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="pt-14 min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-lg border p-8 w-full max-w-sm">
        <div className="text-center mb-6">
          <div className="w-12 h-12 bg-blue-600 rounded-xl mx-auto flex items-center justify-center mb-3">
            <AlertTriangle size={22} className="text-white" />
          </div>
          <h2 className="text-xl font-bold text-gray-900">Officer Login</h2>
          <p className="text-sm text-gray-500 mt-1">SkyAudit Accountability Portal</p>
        </div>
        {error && <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <button type="submit" disabled={loading}
            className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
        <p className="text-xs text-gray-400 text-center mt-4">Demo: demo@skyaudit.in / demo1234</p>
      </div>
    </div>
  );
}

function ResolveModal({ anomaly, onClose, onResolved }) {
  const [status, setStatus] = useState('acknowledged');
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    try {
      await anomaliesApi.updateStatus(anomaly.id, { status, response_text: text });
      // Pass the chosen status back so dashboard can update immediately
      onResolved(anomaly.id, status);
      onClose();
    } catch {
      alert('Update failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <h3 className="font-semibold text-gray-900">Respond to Anomaly #{anomaly.id}</h3>
          <button onClick={onClose}><X size={18} className="text-gray-400" /></button>
        </div>
        <div className="px-5 py-4 space-y-4">
          <div>
            <p className="text-sm text-gray-600 mb-1 font-medium">Update Status</p>
            <select value={status} onChange={e => setStatus(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
              <option value="acknowledged">Acknowledged</option>
              <option value="resolved">Resolved — Issue Fixed</option>
              <option value="disputed">Disputed — Data Incorrect</option>
            </select>
          </div>
          <div>
            <p className="text-sm text-gray-600 mb-1 font-medium">Response / Evidence</p>
            <textarea value={text} onChange={e => setText(e.target.value)}
              placeholder="Describe actions taken, provide evidence, or dispute the finding…"
              rows={4}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 resize-none" />
          </div>
        </div>
        <div className="px-5 py-4 border-t flex gap-3 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50">
            Cancel
          </button>
          <button onClick={handleSubmit} disabled={loading}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {loading ? 'Submitting…' : 'Submit Response'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function OfficerDashboard() {
  const [officer, setOfficer] = useState(null);
  const [resolveTarget, setResolveTarget] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem('skyaudit_token');
    if (!token) return;
    authApi.getMe().then(res => setOfficer(res.data)).catch(() => {
      localStorage.removeItem('skyaudit_token');
    });
  }, []);

  const filters = officer?.district_code
    ? { district_code: officer.district_code }
    : {};
  const { anomalies, loading, refetch, updateLocalAnomaly } = useAnomalies(filters);

  if (!officer) return <LoginForm onLogin={setOfficer} />;

  const now = new Date();
  const newCount = anomalies.filter(a => a.status === 'new').length;
  const pendingCount = anomalies.filter(a => a.status === 'noticed').length;
  const resolvedCount = anomalies.filter(a => a.status === 'resolved').length;
  const approaching = anomalies.filter(a => {
    if (!a.response_due_at) return false;
    const due = new Date(a.response_due_at);
    return (due - now) / 86_400_000 <= 5 && due > now;
  });

  const greeting = () => {
    const h = now.getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  };

  // Called when modal submits successfully
  // 1. Immediately update local state (instant UI feedback)
  // 2. Then re-fetch from server to get authoritative data
  const handleResolved = (anomalyId, newStatus) => {
    updateLocalAnomaly(anomalyId, newStatus);
    refetch();
    setResolveTarget(null);
  };

  return (
    <div className="pt-14 min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{greeting()}, {officer.name.split(' ')[0]}</h1>
            <p className="text-sm text-gray-500">
              {officer.role} · {officer.district_code || officer.state_code || 'National'}
            </p>
          </div>
          <button
            onClick={() => { localStorage.removeItem('skyaudit_token'); setOfficer(null); }}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Sign out
          </button>
        </div>

        {/* Approaching deadline alert */}
        {approaching.length > 0 && (
          <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 flex items-start gap-3">
            <AlertTriangle size={18} className="text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-amber-800">
                {approaching.length} notice{approaching.length > 1 ? 's' : ''} approaching deadline
              </p>
              <p className="text-xs text-amber-600 mt-0.5">
                Response required within 5 days to avoid escalation
              </p>
            </div>
          </div>
        )}

        {/* Stat cards — derived live from anomalies array so always in sync */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'New', value: newCount, color: 'text-red-600', bg: 'bg-red-50 border-red-200', icon: AlertTriangle },
            { label: 'Pending Response', value: pendingCount, color: 'text-orange-600', bg: 'bg-orange-50 border-orange-200', icon: Clock },
            { label: 'Resolved', value: resolvedCount, color: 'text-green-600', bg: 'bg-green-50 border-green-200', icon: CheckCircle },
            { label: 'Total Tracked', value: anomalies.length, color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200', icon: TrendingUp },
          ].map(s => (
            <div key={s.label} className={`rounded-xl border p-4 ${s.bg}`}>
              <s.icon size={18} className={`mb-2 ${s.color}`} />
              <div className={`text-2xl font-bold ${s.color}`}>{loading ? '—' : s.value}</div>
              <div className="text-xs text-gray-600 mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Pending anomalies table */}
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          <div className="px-5 py-4 border-b">
            <h2 className="font-semibold text-gray-900">Pending Anomalies</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 border-b text-xs text-gray-600 uppercase tracking-wide">
                  <th className="px-4 py-3 text-left">School / UDISE</th>
                  <th className="px-4 py-3 text-left">Type</th>
                  <th className="px-4 py-3 text-left">Timeline</th>
                  <th className="px-4 py-3 text-left">Funds at Risk</th>
                  <th className="px-4 py-3 text-left">Action</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b">
                      {Array.from({ length: 5 }).map((_, j) => (
                        <td key={j} className="px-4 py-3"><div className="h-4 bg-gray-100 rounded animate-pulse" /></td>
                      ))}
                    </tr>
                  ))
                ) : anomalies.filter(a => a.status !== 'resolved').length === 0 ? (
                  <tr><td colSpan={5} className="text-center py-10 text-gray-400 text-sm">No pending anomalies 🎉</td></tr>
                ) : (
                  anomalies
                    .filter(a => a.status !== 'resolved')
                    .sort((a, b) => {
                      if (a.response_due_at && b.response_due_at)
                        return new Date(a.response_due_at) - new Date(b.response_due_at);
                      return b.funds_at_risk_inr - a.funds_at_risk_inr;
                    })
                    .map(a => {
                      const due = a.response_due_at ? new Date(a.response_due_at) : null;
                      const daysLeft = due ? Math.floor((due - now) / 86_400_000) : null;
                      const isOverdue = daysLeft !== null && daysLeft < 0;

                      return (
                        <tr key={a.id} className="border-b hover:bg-gray-50 transition-colors">
                          <td className="px-4 py-3">
                            <div className="text-sm font-medium text-gray-900">{a.udise_code}</div>
                            <div className="text-xs text-gray-500">{timeAgo(a.detected_at)}</div>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`text-xs font-bold px-2 py-0.5 rounded ${getSeverityBg(a.severity)}`}>
                              {a.anomaly_type?.replace(/_/g, ' ').toUpperCase()}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            {daysLeft !== null ? (
                              <span className={`text-xs font-medium ${isOverdue ? 'text-red-600' : daysLeft <= 5 ? 'text-orange-600' : 'text-gray-600'}`}>
                                {isOverdue ? `${Math.abs(daysLeft)}d overdue` : `${daysLeft}d remaining`}
                              </span>
                            ) : (
                              <span className="text-xs text-gray-400">No deadline</span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <span className={`text-sm font-bold ${a.funds_at_risk_inr > 0 ? 'text-red-600' : 'text-gray-400'}`}>
                              {a.funds_at_risk_inr > 0 ? formatCurrency(a.funds_at_risk_inr) : '—'}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <button
                              onClick={() => setResolveTarget(a)}
                              className="px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700"
                            >
                              Respond
                            </button>
                          </td>
                        </tr>
                      );
                    })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {resolveTarget && (
        <ResolveModal
          anomaly={resolveTarget}
          onClose={() => setResolveTarget(null)}
          onResolved={handleResolved}
        />
      )}
    </div>
  );
}
