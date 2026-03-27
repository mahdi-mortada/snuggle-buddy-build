import type { RiskScore } from '@/types/crisis';
import { ChevronRight } from 'lucide-react';
import { toast } from 'sonner';

export function RegionalRiskList({ riskScores }: { riskScores: RiskScore[] }) {
  const sorted = [...riskScores].sort((a, b) => b.overallScore - a.overallScore);

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
          <button
            key={risk.region}
            onClick={() => toast.info(`${risk.region}: Score ${risk.overallScore}, Confidence ${(risk.confidence * 100).toFixed(0)}%`)}
            className="w-full text-left space-y-1.5 p-2 -mx-2 rounded-lg hover:bg-accent/30 transition-colors group"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs text-foreground font-medium">{risk.region}</span>
              <div className="flex items-center gap-1">
                <span className={`text-xs font-mono-data font-bold ${getTextColor(risk.overallScore)}`}>
                  {risk.overallScore}
                </span>
                <ChevronRight className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            </div>
            <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-1000 ${getBarColor(risk.overallScore)}`}
                style={{ width: `${risk.overallScore}%` }}
              />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
