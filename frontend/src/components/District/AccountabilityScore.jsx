import { getScoreColor, getScoreLabel } from '../../utils/scoreColors';

export function AccountabilityScore({ score = 0, size = 'md' }) {
  const radius = size === 'lg' ? 54 : 40;
  const stroke = size === 'lg' ? 9 : 7;
  const dim = (radius + stroke) * 2;
  const circumference = 2 * Math.PI * radius;
  const progress = circumference - (score / 100) * circumference;
  const color = getScoreColor(score);
  const label = getScoreLabel(score);

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: dim, height: dim }}>
        <svg width={dim} height={dim} className="-rotate-90">
          {/* Track */}
          <circle cx={dim/2} cy={dim/2} r={radius} fill="none" stroke="#e5e7eb" strokeWidth={stroke} />
          {/* Progress */}
          <circle
            cx={dim/2} cy={dim/2} r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeDasharray={circumference}
            strokeDashoffset={progress}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 1s ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`font-bold ${size === 'lg' ? 'text-3xl' : 'text-2xl'}`} style={{ color }}>
            {score.toFixed(0)}
          </span>
          <span className="text-xs text-gray-500">/100</span>
        </div>
      </div>
      <span className="text-sm font-medium mt-1" style={{ color }}>{label}</span>
    </div>
  );
}
