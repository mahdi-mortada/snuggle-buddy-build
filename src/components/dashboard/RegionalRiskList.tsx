import { mockRiskScores } from '@/data/mockData';

export function RegionalRiskList() {
  const sorted = [...mockRiskScores].sort((a, b) => b.overallScore - a.overallScore);

  const getBarColor = (score: number) => {
    if (score >= 80) return 'bg-critical';
    if (score >= 60) return 'bg-warning';
    if (score >= 40) return 'bg-info';
    return 'bg-success';
  };

  const getTextColor = (score: number) => {
    if (score >= 80) return 'text-critical';
    if (score >= 60) return 'text-warning';
    if (score >= 40) return 'text-info';
    return 'text-success';
  };

  return (
    <div className="glass-panel p-4 h-full flex flex-col">
      <h3 className="text-sm font-semibold text-foreground mb-4">Regional Risk Levels</h3>
      <div className="flex-1 space-y-3 overflow-auto scrollbar-thin">
        {sorted.map((risk) => (
          <div key={risk.region} className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-foreground font-medium">{risk.region}</span>
              <span className={`text-xs font-mono-data font-bold ${getTextColor(risk.overallScore)}`}>
                {risk.overallScore}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-1000 ${getBarColor(risk.overallScore)}`}
                style={{ width: `${risk.overallScore}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
