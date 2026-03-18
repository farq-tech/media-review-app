"use client";

import { useMemo } from "react";
import Link from "next/link";
import { usePOIContext } from "@/contexts/POIContext";
import StatsCard from "@/components/StatsCard";

export default function DashboardPage() {
  const { allPois, loading } = usePOIContext();

  const stats = useMemo(() => {
    let reviewed = 0, pending = 0, flagged = 0, rejected = 0;
    for (const p of allPois) {
      if (p.Review_Status === "Rejected") rejected++;
      else if (p.Flagged === "Yes") flagged++;
      else if (p.Review_Status === "Reviewed" || p.Review_Status === "Approved") reviewed++;
      else pending++;
    }
    return { total: allPois.length, reviewed, pending, flagged, rejected };
  }, [allPois]);

  // Category breakdown
  const categoryBreakdown = useMemo(() => {
    const map = new Map<string, number>();
    for (const p of allPois) {
      const cat = p.Category || "Uncategorized";
      map.set(cat, (map.get(cat) || 0) + 1);
    }
    return Array.from(map.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);
  }, [allPois]);

  const cards = [
    { label: "Total POIs", value: stats.total, color: "bg-purple-100 text-purple-800", icon: "📍" },
    { label: "Pending", value: stats.pending, color: "bg-amber-100 text-amber-800", icon: "⏳" },
    { label: "Reviewed", value: stats.reviewed, color: "bg-green-100 text-green-800", icon: "✅" },
    { label: "Flagged", value: stats.flagged, color: "bg-red-100 text-red-800", icon: "🚩" },
    { label: "Rejected", value: stats.rejected, color: "bg-blue-100 text-blue-800", icon: "❌" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#374151]">Dashboard</h1>
          <p className="text-[#6b7280] text-sm mt-1">Overview of POI review progress</p>
        </div>
        <Link
          href="/dashboard/review"
          className="px-4 py-2 bg-[#22c55e] hover:bg-[#16a34a] text-white text-sm font-medium rounded-lg transition-colors"
        >
          Start Reviewing
        </Link>
      </div>

      {/* Stats cards */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-[#e5e7eb] p-5 h-28 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {cards.map((card) => (
            <StatsCard
              key={card.label}
              label={card.label}
              value={card.value}
              icon={card.icon}
              color={card.color}
              total={stats.total}
            />
          ))}
        </div>
      )}

      {/* Category breakdown */}
      {!loading && categoryBreakdown.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-[#e5e7eb] p-5">
          <h2 className="text-lg font-semibold text-[#374151] mb-4">Top Categories</h2>
          <div className="space-y-2">
            {categoryBreakdown.map(([cat, count]) => (
              <div key={cat} className="flex items-center gap-3">
                <span className="text-sm text-[#374151] w-48 truncate">{cat}</span>
                <div className="flex-1 bg-[#f3f4f6] rounded-full h-2">
                  <div
                    className="bg-[#22c55e] h-2 rounded-full transition-all"
                    style={{ width: `${(count / stats.total) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-[#6b7280] w-12 text-right">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick links */}
      {!loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { href: "/dashboard/review", label: "Review Queue", desc: "Review POIs one by one", icon: "📋" },
            { href: "/dashboard/excel", label: "Excel View", desc: "Bulk edit in table", icon: "📊" },
            { href: "/dashboard/map", label: "Map View", desc: "Geospatial exploration", icon: "🗺️" },
            { href: "/dashboard/duplicates", label: "Duplicates", desc: "Find & merge duplicates", icon: "🔍" },
          ].map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="bg-white rounded-xl shadow-sm border border-[#e5e7eb] p-5 hover:shadow-md hover:border-[#22c55e]/30 transition-all"
            >
              <div className="text-2xl mb-2">{link.icon}</div>
              <h3 className="text-sm font-semibold text-[#374151]">{link.label}</h3>
              <p className="text-xs text-[#6b7280] mt-1">{link.desc}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
