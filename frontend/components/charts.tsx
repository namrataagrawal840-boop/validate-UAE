'use client';
import { ResponsiveContainer, ComposedChart, AreaChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, LineChart, BarChart, Bar, Cell } from 'recharts';
import { monthLabel, aed, num, pct } from '@/lib/fmt';

const short = (v: number) => { const a = Math.abs(v); const s = a >= 1e6 ? (a / 1e6).toFixed(1) + 'M' : a >= 1e3 ? Math.round(a / 1e3) + 'k' : Math.round(a) + ''; return (v < 0 ? '−' : '') + s; };

export function FanChart({ band, money, height = 300 }: { band: { p10: number[]; p50: number[]; p90: number[] }; money?: boolean; height?: number }) {
  const data = band.p50.map((m, i) => ({ t: monthLabel(i), range: [band.p10[i], band.p90[i]], mid: m }));
  const fmt = money ? aed : (v: number) => num(v);
  return (
    <div style={{ width: '100%', height }} role="img" aria-label={`Median ends at ${fmt(band.p50[band.p50.length - 1])}`}>
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
          <CartesianGrid stroke="#e9ecf3" vertical={false} />
          <XAxis dataKey="t" tick={{ fontSize: 12, fill: '#586079' }} interval={5} tickLine={false} />
          <YAxis tickFormatter={short} tick={{ fontSize: 12, fill: '#586079' }} width={52} tickLine={false} axisLine={false} />
          <Tooltip formatter={(v: any, n: string) => (Array.isArray(v) ? `${fmt(v[0])} to ${fmt(v[1])}` : fmt(v))} labelStyle={{ fontWeight: 600 }} />
          <Area dataKey="range" name="Bad case to good case" stroke="none" fill="#2348d6" fillOpacity={0.14} isAnimationActive={false} />
          {money && <ReferenceLine y={0} stroke="#a86a00" strokeDasharray="5 4" />}
          <Line dataKey="mid" name="Typical future" stroke="#2348d6" strokeWidth={2.5} dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CurveChart({ data, x, y, yFmt = (v: number) => pct(v), xFmt = (v: any) => String(v), height = 240, refLine: refY, color = '#2348d6' }: any) {
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
          <CartesianGrid stroke="#e9ecf3" vertical={false} />
          <XAxis dataKey={x} tickFormatter={xFmt} tick={{ fontSize: 12, fill: '#586079' }} tickLine={false} />
          <YAxis tickFormatter={yFmt} tick={{ fontSize: 12, fill: '#586079' }} width={52} tickLine={false} axisLine={false} />
          <Tooltip formatter={(v: any) => yFmt(v)} labelFormatter={xFmt} />
          {refY != null && <ReferenceLine y={refY} stroke="#a86a00" strokeDasharray="5 4" />}
          <Line dataKey={y} stroke={color} strokeWidth={2.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Tornado({ rows }: { rows: { name: string; variance_share: number }[] }) {
  const data = rows.slice(0, 8).map(r => ({ name: r.name, share: r.variance_share }));
  return (
    <div style={{ width: '100%', height: 40 + data.length * 34 }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 0 }}>
          <XAxis type="number" hide domain={[0, 'dataMax']} />
          <YAxis type="category" dataKey="name" width={190} tick={{ fontSize: 13, fill: '#121833' }} tickLine={false} axisLine={false} />
          <Tooltip formatter={(v: any) => pct(v)} />
          <Bar dataKey="share" barSize={18} radius={[0, 4, 4, 0]} isAnimationActive={false} label={{ position: 'right', formatter: (v: any) => pct(v), fontSize: 12, fill: '#586079' }}>
            {data.map((_, i) => <Cell key={i} fill={i === 0 ? '#2348d6' : '#9fb3f0'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function StateChart({ bands, height = 280 }: { bands: any; height?: number }) {
  const keys = [['customers', 'Customers', '#2348d6'], ['left', 'Left', '#c43b3b'], ['said_no', 'Heard, said no', '#d9a441'], ['unaware', 'Not heard yet', '#c9cfdd']];
  const data = bands.customers.p50.map((_: any, i: number) => Object.fromEntries([['t', monthLabel(i)], ...keys.map(([k]) => [k, bands[k].p50[i]])]));
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
          <CartesianGrid stroke="#e9ecf3" vertical={false} />
          <XAxis dataKey="t" tick={{ fontSize: 12, fill: '#586079' }} interval={5} tickLine={false} />
          <YAxis tickFormatter={short} tick={{ fontSize: 12, fill: '#586079' }} width={52} tickLine={false} axisLine={false} />
          <Tooltip formatter={(v: any) => num(v)} />
          {keys.map(([k, n, col]) => <Area key={k} dataKey={k} name={n} stackId="1" stroke={col} fill={col} fillOpacity={0.85} isAnimationActive={false} />)}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
