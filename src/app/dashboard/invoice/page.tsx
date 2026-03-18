"use client";

import { useMemo } from "react";
import { usePOIContext } from "@/contexts/POIContext";

const FIELD_VALUES: Record<string, number> = {
  Name_EN: 5, Name_AR: 5, Category: 3, Subcategory: 2,
  Phone_Number: 5, Email: 3, Website: 3,
  Working_Hours: 4, Working_Days: 3,
  Exterior_Photo_URL: 8, Interior_Photo_URL: 8,
  Menu_Photo_URL: 6, Video_URL: 10, License_Photo_URL: 5,
  Latitude: 3, Longitude: 3, District_EN: 3, District_AR: 2,
};

function calcPoiValue(poi: Record<string, unknown>): number {
  let total = 0;
  for (const [field, value] of Object.entries(FIELD_VALUES)) {
    const v = poi[field];
    if (v && String(v).trim() && String(v) !== "UNAVAILABLE" && String(v) !== "UNAPPLICABLE") {
      total += value;
    }
  }
  return total;
}

export default function InvoicePage() {
  const { allPois, loading } = usePOIContext();

  const invoiceData = useMemo(() => {
    let totalValue = 0;
    const poiValues: { gid: string; name: string; category: string; value: number }[] = [];
    const categoryTotals = new Map<string, { count: number; value: number }>();

    for (const poi of allPois) {
      const value = calcPoiValue(poi);
      totalValue += value;
      poiValues.push({
        gid: poi.GlobalID,
        name: poi.Name_EN || "Unnamed",
        category: String(poi.Category ?? "Uncategorized"),
        value,
      });

      const cat = String(poi.Category ?? "Uncategorized");
      const existing = categoryTotals.get(cat) || { count: 0, value: 0 };
      categoryTotals.set(cat, { count: existing.count + 1, value: existing.value + value });
    }

    poiValues.sort((a, b) => b.value - a.value);
    const categoryBreakdown = Array.from(categoryTotals.entries())
      .sort((a, b) => b[1].value - a[1].value);

    return { totalValue, poiValues, categoryBreakdown };
  }, [allPois]);

  const maxValue = Object.values(FIELD_VALUES).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#374151]">Invoice</h1>
        <p className="text-sm text-[#6b7280] mt-0.5">POI field value calculation</p>
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-[#e5e7eb] p-8 animate-pulse h-32" />
      ) : (
        <>
          {/* Summary */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white rounded-xl shadow-sm border border-[#e5e7eb] p-5">
              <p className="text-xs text-[#6b7280] mb-1">Total POIs</p>
              <p className="text-2xl font-bold text-[#374151]">{allPois.length.toLocaleString()}</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-[#e5e7eb] p-5">
              <p className="text-xs text-[#6b7280] mb-1">Total Value</p>
              <p className="text-2xl font-bold text-[#22c55e]">{invoiceData.totalValue.toLocaleString()} pts</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-[#e5e7eb] p-5">
              <p className="text-xs text-[#6b7280] mb-1">Avg per POI</p>
              <p className="text-2xl font-bold text-[#374151]">
                {allPois.length > 0 ? Math.round(invoiceData.totalValue / allPois.length) : 0} / {maxValue}
              </p>
            </div>
          </div>

          {/* Category breakdown */}
          <div className="bg-white rounded-xl border border-[#e5e7eb] p-5">
            <h2 className="text-sm font-semibold text-[#374151] mb-4">Value by Category</h2>
            <div className="space-y-2">
              {invoiceData.categoryBreakdown.slice(0, 15).map(([cat, data]) => (
                <div key={cat} className="flex items-center gap-3">
                  <span className="text-xs text-[#374151] w-40 truncate">{cat}</span>
                  <div className="flex-1 bg-[#f3f4f6] rounded-full h-2">
                    <div
                      className="bg-[#22c55e] h-2 rounded-full"
                      style={{ width: `${(data.value / invoiceData.totalValue) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-[#6b7280] w-20 text-right">
                    {data.count} POIs &middot; {data.value} pts
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Top POIs by value */}
          <div className="bg-white rounded-xl border border-[#e5e7eb] overflow-hidden">
            <div className="p-4 border-b border-[#e5e7eb]">
              <h2 className="text-sm font-semibold text-[#374151]">Top 20 POIs by Value</h2>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[#f9fafb] border-b border-[#e5e7eb]">
                  <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">#</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">Name</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">Category</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold text-[#6b7280]">Value</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-[#6b7280]">Completeness</th>
                </tr>
              </thead>
              <tbody>
                {invoiceData.poiValues.slice(0, 20).map((pv, i) => (
                  <tr key={pv.gid} className="border-b border-[#e5e7eb] hover:bg-[#f9fafb]">
                    <td className="px-4 py-2 text-xs text-[#6b7280]">{i + 1}</td>
                    <td className="px-4 py-2 text-xs font-medium text-[#374151]">{pv.name}</td>
                    <td className="px-4 py-2 text-xs text-[#6b7280]">{pv.category}</td>
                    <td className="px-4 py-2 text-xs font-bold text-[#374151] text-right">{pv.value} / {maxValue}</td>
                    <td className="px-4 py-2">
                      <div className="w-20 bg-[#f3f4f6] rounded-full h-1.5">
                        <div
                          className="bg-[#22c55e] h-1.5 rounded-full"
                          style={{ width: `${(pv.value / maxValue) * 100}%` }}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
