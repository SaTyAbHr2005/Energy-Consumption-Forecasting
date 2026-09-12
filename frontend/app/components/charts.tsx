"use client";

import { 
  LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine
} from "recharts";

const COLORS = {
  blue: "#2878c8",
  green: "#138a68",
  amber: "#e39a29",
  red: "#d95b55",
  ink: "#10221f",
  muted: "#71807c",
  line: "#e4ece8"
};

export function ConsumptionAreaChart({ data, dataKey = "energy_kwh", timeKey = "timestamp", color = COLORS.blue }: { data: any[], dataKey?: string, timeKey?: string, color?: string }) {
  if (!data || data.length === 0) return <div className="h-64 flex items-center justify-center text-muted">No data available</div>;
  
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id={`color-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.8}/>
            <stop offset="95%" stopColor={color} stopOpacity={0}/>
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.line} />
        <XAxis 
          dataKey={timeKey} 
          tickFormatter={(tick: any) => {
            try {
              const d = new Date(tick);
              return isNaN(d.getTime()) ? tick : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            } catch { return tick; }
          }}
          stroke={COLORS.muted} 
          fontSize={12} 
          tickLine={false} 
          axisLine={false} 
          minTickGap={30}
        />
        <YAxis stroke={COLORS.muted} fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val) => val.toFixed(2)} />
        <Tooltip 
          contentStyle={{ borderRadius: '12px', border: '1px solid #e4ece8', boxShadow: '0 4px 12px rgba(16,34,31,0.05)' }}
          labelStyle={{ color: COLORS.muted, marginBottom: '4px' }}
          formatter={(value: number) => [`${value.toFixed(3)} kWh`, 'Consumption']}
          labelFormatter={(label: any) => {
            try {
              const d = new Date(label);
              return isNaN(d.getTime()) ? label : d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            } catch { return label; }
          }}
        />
        <Area type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} fillOpacity={1} fill={`url(#color-${dataKey})`} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function ForecastChart({ historical, forecast, threshold }: { historical: any[], forecast: any[], threshold: number }) {
  // Combine historical and forecast to create a single timeline
  // We'll show historical as solid blue, and forecast as a dashed orange line.
  
  if (!historical.length && !forecast.length) return <div className="h-64 flex items-center justify-center text-muted">No data available</div>;

  const combined = [...historical.map(h => ({ ...h, isHistorical: true })), ...forecast.map(f => ({ ...f, isForecast: true, energy_kwh: f.predicted_consumption || f.predicted }))];

  return (
    <ResponsiveContainer width="100%" height={350}>
      <LineChart data={combined} margin={{ top: 20, right: 20, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.line} />
        <XAxis 
          dataKey="timestamp" 
          tickFormatter={(tick: any) => {
            try {
              const d = new Date(tick);
              return isNaN(d.getTime()) ? tick : d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit' });
            } catch { return tick; }
          }}
          stroke={COLORS.muted} 
          fontSize={12} 
          tickLine={false} 
          axisLine={false} 
          minTickGap={40}
        />
        <YAxis stroke={COLORS.muted} fontSize={12} tickLine={false} axisLine={false} />
        <Tooltip 
          contentStyle={{ borderRadius: '12px', border: '1px solid #e4ece8', boxShadow: '0 4px 12px rgba(16,34,31,0.05)' }}
          labelFormatter={(label: any) => label}
          formatter={(value: number, name: string) => {
            return [`${value.toFixed(3)} kWh`, name === 'energy_kwh' ? 'Historical' : 'Predicted'];
          }}
        />
        <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: '12px', color: COLORS.ink }} />
        
        <ReferenceLine y={threshold} label={{ position: 'top', value: `Peak Threshold (${threshold.toFixed(2)} kWh)`, fill: COLORS.red, fontSize: 11 }} stroke={COLORS.red} strokeDasharray="3 3" />
        
        <Line type="monotone" dataKey={(d) => d.isHistorical ? d.energy_kwh : null} name="Historical" stroke={COLORS.blue} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
        <Line type="monotone" dataKey={(d) => d.isForecast ? d.energy_kwh : null} name="Predicted" stroke={COLORS.amber} strokeWidth={2} strokeDasharray="5 5" dot={{ r: 3, fill: COLORS.amber }} activeDot={{ r: 6 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function SeverityDonutChart({ data }: { data: Record<string, number> }) {
  if (!data || Object.keys(data).length === 0) return <div className="h-48 flex items-center justify-center text-muted">No severity data</div>;

  const chartData = Object.entries(data).map(([name, value]) => ({ name, value }));
  const getSeverityColor = (name: string) => {
    const lower = name.toLowerCase();
    if (lower.includes('normal') || lower.includes('low')) return COLORS.green;
    if (lower.includes('high') || lower.includes('medium')) return COLORS.amber;
    if (lower.includes('critical')) return COLORS.red;
    return COLORS.blue;
  };

  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={80}
          paddingAngle={5}
          dataKey="value"
        >
          {chartData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={getSeverityColor(entry.name)} />
          ))}
        </Pie>
        <Tooltip 
          contentStyle={{ borderRadius: '8px', border: '1px solid #e4ece8', fontSize: '13px' }}
          formatter={(value: number) => [value, 'Periods']}
        />
        <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function SimpleBarChart({ data, xKey, yKey, color = COLORS.green, onClick }: { data: any[], xKey: string, yKey: string, color?: string, onClick?: (data: any) => void }) {
  if (!data || data.length === 0) return <div className="h-48 flex items-center justify-center text-muted">No data available</div>;

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }} onClick={onClick}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.line} />
        <XAxis dataKey={xKey} stroke={COLORS.muted} fontSize={12} tickLine={false} axisLine={false} />
        <YAxis stroke={COLORS.muted} fontSize={12} tickLine={false} axisLine={false} />
        <Tooltip 
          contentStyle={{ borderRadius: '8px', border: '1px solid #e4ece8', fontSize: '13px' }}
          cursor={{ fill: 'rgba(16, 34, 31, 0.05)' }}
          formatter={(value: number) => [typeof value === 'number' ? value.toFixed(2) : value, 'Value']}
        />
        <Bar dataKey={yKey} fill={color} radius={[4, 4, 0, 0]} onClick={onClick} />
      </BarChart>
    </ResponsiveContainer>
  );
}
