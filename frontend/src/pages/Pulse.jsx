// frontend/src/pages/Pulse.jsx
import { useState } from 'react';
import { PulseFeed } from '../components/Feed/PulseFeed';
import { Radio } from 'lucide-react';

const STATES = ['All States', 'Uttar Pradesh', 'Bihar', 'Madhya Pradesh', 'Rajasthan', 'Maharashtra'];
const TYPES = ['All Types', 'ghost_school', 'meal_fraud', 'construction_fraud', 'enrollment_inflation', 'outcome_manipulation'];
const SEVERITIES = ['All', 'critical', 'high', 'medium', 'low'];

export default function Pulse() {
  const [state, setState] = useState('');
  const [type, setType] = useState('');
  const [severity, setSeverity] = useState('');

  const filters = {};
  if (state && state !== 'All States') filters.state = state;
  if (type && type !== 'All Types') filters.event_type = type;

  return (
    <div className="pt-14 min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-5">
          <div className="w-9 h-9 bg-red-600 rounded-lg flex items-center justify-center">
            <Radio size={18} className="text-white animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Live Anomaly Pulse</h1>
            <p className="text-xs text-gray-500">Real-time satellite-detected irregularities across India</p>
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex gap-2 mb-5 overflow-x-auto pb-1">
          <select value={state} onChange={e => setState(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:border-blue-500 shrink-0">
            {STATES.map(s => <option key={s} value={s === 'All States' ? '' : s}>{s}</option>)}
          </select>
          <select value={type} onChange={e => setType(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:border-blue-500 shrink-0">
            {TYPES.map(t => (
              <option key={t} value={t === 'All Types' ? '' : t}>
                {t === 'All Types' ? 'All Types' : t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
              </option>
            ))}
          </select>
          <select value={severity} onChange={e => setSeverity(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:border-blue-500 shrink-0">
            {SEVERITIES.map(s => <option key={s} value={s === 'All' ? '' : s}>{s === 'All' ? 'All Severities' : s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
          </select>
        </div>

        {/* Feed */}
        <PulseFeed filters={filters} />
      </div>
    </div>
  );
}
