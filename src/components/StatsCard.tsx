"use client";

interface StatsCardProps {
  label: string;
  value: number;
  icon: string;
  color: string;
  total?: number;
}

export default function StatsCard({ label, value, icon, color, total }: StatsCardProps) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-[#e5e7eb] p-5">
      <div className="flex items-center justify-between mb-2">
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${color}`}>
          {icon} {label}
        </span>
      </div>
      <p className="text-2xl font-bold text-[#374151]">{value.toLocaleString()}</p>
      {total && total > 0 && label !== "Total POIs" && (
        <p className="text-xs text-[#6b7280] mt-1">
          {((value / total) * 100).toFixed(1)}% of total
        </p>
      )}
    </div>
  );
}
