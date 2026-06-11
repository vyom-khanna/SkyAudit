export function indiaCenter() {
  return [20.5937, 78.9629];
}

export function districtCenter(schools) {
  if (!schools?.length) return [27.5, 80.5];
  const lats = schools.filter(s => s.latitude).map(s => s.latitude);
  const lngs = schools.filter(s => s.longitude).map(s => s.longitude);
  if (!lats.length) return [27.5, 80.5];
  return [
    lats.reduce((a, b) => a + b, 0) / lats.length,
    lngs.reduce((a, b) => a + b, 0) / lngs.length,
  ];
}

export function pinColor(school) {
  if (school.status === 'ghost_school' || school.severity === 'critical') return '#dc2626';
  if (school.has_anomaly && school.severity === 'high') return '#f97316';
  if (school.has_anomaly) return '#facc15';
  return '#16a34a';
}

export function anomalyTypeLabel(type) {
  const map = {
    ghost_school: 'GHOST SCHOOL',
    construction_fraud: 'CONSTRUCTION FRAUD',
    enrollment_inflation: 'ENROLLMENT INFLATION',
    meal_fraud: 'MEAL FRAUD',
    outcome_manipulation: 'OUTCOME MANIPULATION',
    teacher_absence: 'TEACHER ABSENCE',
    budget_misuse: 'BUDGET MISUSE',
  };
  return map[type] || type?.toUpperCase().replace(/_/g, ' ') || 'ANOMALY';
}
