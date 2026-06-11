import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

export function EnrollmentChart({ reported, verified_capacity, district_ceiling }) {
  const data = [
    { name: 'Reported', value: reported, fill: '#f97316' },
    { name: 'Building\nCapacity', value: verified_capacity, fill: '#4ade80' },
    { name: 'District\nCeiling', value: district_ceiling, fill: '#60a5fa' },
  ].filter(d => d.value > 0);

  return (
    <div className="h-40">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <XAxis dataKey="name" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip formatter={(v) => [v.toLocaleString('en-IN'), 'Students']} />
          <Bar dataKey="value" radius={[3, 3, 0, 0]}>
            {data.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
