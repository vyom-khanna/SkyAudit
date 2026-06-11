export function getScoreColor(score) {
  if (score >= 80) return '#16a34a';  // deep green
  if (score >= 60) return '#4ade80';  // light green
  if (score >= 40) return '#facc15';  // yellow
  if (score >= 20) return '#f97316';  // orange
  return '#dc2626';                    // red
}

export function getScoreBg(score) {
  if (score >= 80) return 'bg-green-700';
  if (score >= 60) return 'bg-green-400';
  if (score >= 40) return 'bg-yellow-400';
  if (score >= 20) return 'bg-orange-500';
  return 'bg-red-600';
}

export function getScoreLabel(score) {
  if (score >= 80) return 'Good';
  if (score >= 60) return 'Fair';
  if (score >= 40) return 'Concerning';
  if (score >= 20) return 'Poor';
  return 'Critical';
}

export function getSeverityColor(severity) {
  const map = {
    critical: '#dc2626',
    high: '#f97316',
    medium: '#facc15',
    low: '#4ade80',
  };
  return map[severity] || '#9ca3af';
}

export function getSeverityBg(severity) {
  const map = {
    critical: 'bg-red-600 text-white',
    high: 'bg-orange-500 text-white',
    medium: 'bg-yellow-400 text-gray-900',
    low: 'bg-green-400 text-gray-900',
  };
  return map[severity] || 'bg-gray-200 text-gray-700';
}

export function getStatusColor(status) {
  const map = {
    verified: '#16a34a',
    anomaly: '#f97316',
    ghost: '#dc2626',
    pending: '#9ca3af',
  };
  return map[status] || '#9ca3af';
}

export function getStatusBadge(status) {
  const map = {
    verified: 'bg-green-100 text-green-800 border-green-300',
    anomaly: 'bg-orange-100 text-orange-800 border-orange-300',
    ghost: 'bg-red-100 text-red-800 border-red-300',
    pending: 'bg-gray-100 text-gray-600 border-gray-300',
  };
  return map[status] || 'bg-gray-100 text-gray-600 border-gray-300';
}

export function formatCurrency(amount) {
  if (!amount) return '₹0';
  if (amount >= 10_000_000) return `₹${(amount / 10_000_000).toFixed(1)}Cr`;
  if (amount >= 100_000) return `₹${(amount / 100_000).toFixed(1)}L`;
  if (amount >= 1000) return `₹${(amount / 1000).toFixed(0)}K`;
  return `₹${amount.toFixed(0)}`;
}

export function timeAgo(dateStr) {
  if (!dateStr) return 'Unknown';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffDay > 30) return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  if (diffDay > 0) return `${diffDay}d ago`;
  if (diffHour > 0) return `${diffHour}h ago`;
  if (diffMin > 0) return `${diffMin}m ago`;
  return 'Just now';
}
