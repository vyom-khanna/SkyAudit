// frontend/src/pages/Home.jsx
import { useState } from 'react';
import IndiaMap from '../components/Map/IndiaMap';
import StatsBar from '../components/shared/StatsBar';

export default function Home() {
  const [selectedDistrict, setSelectedDistrict] = useState(null);

  return (
    <div className="fixed inset-0 pt-14 pb-16 flex flex-col bg-gray-900">
      <div className="flex-1 relative">
        <IndiaMap onDistrictSelect={setSelectedDistrict} />

        {/* Legend */}
        <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur rounded-xl shadow-lg p-3 text-xs">
          <div className="font-semibold text-gray-700 mb-2">Accountability Score</div>
          {[
            ['#16a34a', '80–100', 'Good'],
            ['#4ade80', '60–79', 'Fair'],
            ['#facc15', '40–59', 'Concerning'],
            ['#f97316', '20–39', 'Poor'],
            ['#dc2626', '0–19', 'Critical'],
          ].map(([color, range, label]) => (
            <div key={range} className="flex items-center gap-2 mb-1">
              <div className="w-3 h-3 rounded" style={{ background: color }} />
              <span className="text-gray-600">{range} — {label}</span>
            </div>
          ))}
        </div>
      </div>
      <StatsBar />
    </div>
  );
}
