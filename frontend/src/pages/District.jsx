// frontend/src/pages/District.jsx
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useDistrict, useDistrictSchools } from '../hooks/useDistrict';
import { DistrictCard } from '../components/District/DistrictCard';
import DistrictMap from '../components/Map/DistrictMap';
import SchoolCard from '../components/School/SchoolCard';
import { AlertTriangle, CheckCircle, Building2, Utensils, GraduationCap } from 'lucide-react';

const FILTERS = [
  { key: 'all', label: 'All Schools', icon: null },
  { key: 'ghost_school', label: 'Ghost', icon: AlertTriangle },
  { key: 'construction_fraud', label: 'Construction', icon: Building2 },
  { key: 'enrollment_inflation', label: 'Enrollment', icon: GraduationCap },
  { key: 'meal_fraud', label: 'Meals', icon: Utensils },
  { key: 'verified', label: 'Verified', icon: CheckCircle },
];

export default function District() {
  const { districtCode } = useParams();
  const { data, loading, error } = useDistrict(districtCode);
  const [activeFilter, setActiveFilter] = useState('all');
  const [selectedSchool, setSelectedSchool] = useState(null);

  const filterParams = activeFilter === 'all' ? {} :
    activeFilter === 'verified' ? { status: 'verified' } : { status: activeFilter };

  const { schools } = useDistrictSchools(districtCode, filterParams);

  if (loading) {
    return (
      <div className="pt-14 h-screen flex items-center justify-center bg-gray-50">
        <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="pt-14 h-screen flex items-center justify-center bg-gray-50">
        <p className="text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="pt-14 h-screen flex flex-col overflow-hidden bg-gray-50">
      {/* Filter bar */}
      <div className="bg-white border-b px-4 py-2 flex gap-2 overflow-x-auto shrink-0">
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setActiveFilter(f.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
              activeFilter === f.key
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {f.icon && <f.icon size={12} />}
            {f.label}
          </button>
        ))}
        <div className="ml-auto text-xs text-gray-400 flex items-center shrink-0">
          {schools.length} schools
        </div>
      </div>

      {/* Main layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left panel: District info */}
        <div className="w-80 shrink-0 bg-white border-r overflow-y-auto hidden lg:block">
          <DistrictCard data={data} />
        </div>

        {/* Right: Map */}
        <div className="flex-1 relative">
          <DistrictMap
            schools={schools}
            onSchoolSelect={(school) => setSelectedSchool(school.udise_code)}
            selectedUdise={selectedSchool}
          />

          {/* School card slide-in panel */}
          {selectedSchool && (
            <div className="absolute top-0 right-0 bottom-0 w-80 bg-white shadow-2xl border-l overflow-hidden z-10 animate-slide-in-right">
              <SchoolCard
                udiseCode={selectedSchool}
                onClose={() => setSelectedSchool(null)}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
