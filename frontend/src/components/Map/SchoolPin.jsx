export function SchoolPinDot({ status, severity, size = 12 }) {
  const colors = {
    ghost_school: '#dc2626',
    critical: '#dc2626',
    high: '#f97316',
    medium: '#facc15',
    low: '#4ade80',
    verified: '#16a34a',
  };
  const color = severity ? colors[severity] : colors[status] || '#9ca3af';
  return (
    <div
      style={{ width: size, height: size, background: color, borderRadius: '50%', border: '2px solid white', boxShadow: '0 1px 3px rgba(0,0,0,0.3)' }}
    />
  );
}
