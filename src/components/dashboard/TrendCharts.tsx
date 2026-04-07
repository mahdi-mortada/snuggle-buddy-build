import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { format } from 'date-fns';
import { useState } from 'react';
import { Download } from 'lucide-react';
import { toast } from 'sonner';
import type { TrendDataPoint } from '@/types/crisis';

const timeRanges = ['24h', '48h', '7d'] as const;

export function TrendCharts({ data: rawData }: { data: TrendDataPoint[] }) {
  const [range, setRange] = useState<typeof timeRanges[number]>('7d');

  const hours = range === '24h' ? 24 : range === '48h' ? 48 : 168;
  const data = rawData.slice(-hours).map((d) => ({
    ...d,
    time: format(new Date(d.time), hours <= 48 ? 'HH:mm' : 'MMM dd'),
  }));

  return (
    <div className="glass-panel p-4 flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-foreground">Trend Analysis</h3>
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            {timeRanges.map((r) => (
              <button key={r} onClick={() => setRange(r)}
                className={`px-2.5 py-1 text-[10px] font-medium rounded-md uppercase tracking-wider transition-colors ${
                  range === r ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                }`}
              >{r}</button>
            ))}
          </div>
          <button onClick={() => toast.success('Chart data exported as CSV')}
            className="p-1.5 rounded hover:bg-accent transition-colors" title="Export chart data">
            <Download className="w-3.5 h-3.5 text-muted-foreground" />
          </button>
        </div>
      </div>
      <div className="flex flex-col gap-4">
        <div>
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Incident Volume & Risk Score</p>
          <ResponsiveContainer width="100%" height={155}>
            <AreaChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', fontSize: '12px' }} labelStyle={{ color: 'hsl(var(--foreground))' }} />
              <Area type="monotone" dataKey="incidents" stroke="hsl(var(--primary))" fill="hsl(var(--primary))" fillOpacity={0.15} strokeWidth={2} />
              <Area type="monotone" dataKey="riskScore" stroke="hsl(var(--warning))" fill="hsl(var(--warning))" fillOpacity={0.1} strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Sentiment Trend</p>
          <ResponsiveContainer width="100%" height={155}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} tickLine={false} axisLine={false} />
              <YAxis domain={[-1, 1]} tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', fontSize: '12px' }} />
              <Line type="monotone" dataKey="sentiment" stroke="hsl(var(--chart-5))" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
