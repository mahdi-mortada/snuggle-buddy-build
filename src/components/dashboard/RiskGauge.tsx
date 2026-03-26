import { mockStats } from '@/data/mockData';

export function RiskGauge() {
  const score = mockStats.avgRiskScore;
  const maxScore = 100;
  const percentage = score / maxScore;
  const circumference = 2 * Math.PI * 80;
  const offset = circumference - (percentage * 0.75 * circumference);

  const getColor = (s: number) => {
    if (s >= 80) return 'hsl(var(--critical))';
    if (s >= 60) return 'hsl(var(--warning))';
    if (s >= 40) return 'hsl(var(--info))';
    return 'hsl(var(--success))';
  };

  const getLabel = (s: number) => {
    if (s >= 80) return 'CRITICAL';
    if (s >= 60) return 'ELEVATED';
    if (s >= 40) return 'GUARDED';
    return 'LOW';
  };

  return (
    <div className="glass-panel h-full flex flex-col items-center justify-center p-6">
      <h3 className="text-sm font-semibold text-foreground mb-4">Overall Risk Level</h3>
      <div className="relative">
        <svg width="200" height="160" viewBox="0 0 200 180">
          {/* Background arc */}
          <circle
            cx="100"
            cy="100"
            r="80"
            fill="none"
            stroke="hsl(var(--border))"
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * 0.25}
            transform="rotate(135 100 100)"
          />
          {/* Value arc */}
          <circle
            cx="100"
            cy="100"
            r="80"
            fill="none"
            stroke={getColor(score)}
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform="rotate(135 100 100)"
            style={{
              transition: 'stroke-dashoffset 1s ease-in-out',
              filter: `drop-shadow(0 0 8px ${getColor(score)}40)`,
            }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center pt-2">
          <span className="font-mono-data text-4xl font-bold text-foreground">{score.toFixed(1)}</span>
          <span
            className="text-xs font-bold uppercase tracking-widest mt-1"
            style={{ color: getColor(score) }}
          >
            {getLabel(score)}
          </span>
        </div>
      </div>
      <div className="flex gap-4 mt-4 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-success" /> Low</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-info" /> Guarded</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-warning" /> Elevated</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-critical" /> Critical</span>
      </div>
    </div>
  );
}
