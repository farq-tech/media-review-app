"use client";

import { usePOIContext } from "@/contexts/POIContext";

export default function FilterPanel() {
  const {
    search, setSearch,
    statusFilter, setStatusFilter,
    categoryFilter, setCategoryFilter,
    categories,
    filteredPois, perPage, setPerPage,
    page, setPage, totalPages,
  } = usePOIContext();

  return (
    <div className="bg-white rounded-xl border border-[#e5e7eb] p-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {/* Search */}
        <div>
          <label className="block text-xs text-[#6b7280] mb-1">Search</label>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Name, ID, phone..."
            className="w-full px-3 py-2 border border-[#d1d5db] rounded-lg text-sm text-[#374151] focus:outline-none focus:ring-2 focus:ring-[#22c55e]/50 focus:border-[#22c55e]"
          />
        </div>

        {/* Status */}
        <div>
          <label className="block text-xs text-[#6b7280] mb-1">Status</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full px-3 py-2 border border-[#d1d5db] rounded-lg text-sm text-[#374151] focus:outline-none focus:ring-2 focus:ring-[#22c55e]/50"
          >
            <option value="all">All</option>
            <option value="pending">Pending</option>
            <option value="reviewed">Reviewed</option>
          </select>
        </div>

        {/* Category */}
        <div>
          <label className="block text-xs text-[#6b7280] mb-1">Category</label>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="w-full px-3 py-2 border border-[#d1d5db] rounded-lg text-sm text-[#374151] focus:outline-none focus:ring-2 focus:ring-[#22c55e]/50"
          >
            <option value="all">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>

        {/* Per page */}
        <div>
          <label className="block text-xs text-[#6b7280] mb-1">Per Page</label>
          <select
            value={perPage}
            onChange={(e) => setPerPage(Number(e.target.value))}
            className="w-full px-3 py-2 border border-[#d1d5db] rounded-lg text-sm text-[#374151] focus:outline-none focus:ring-2 focus:ring-[#22c55e]/50"
          >
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
          </select>
        </div>

        {/* Results count + pagination */}
        <div className="flex flex-col justify-end">
          <p className="text-xs text-[#6b7280] mb-1">{filteredPois.length} results</p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-3 py-2 border border-[#d1d5db] rounded-lg text-sm text-[#374151] hover:bg-[#f3f4f6] disabled:opacity-50"
            >
              Prev
            </button>
            <span className="px-3 py-2 text-sm text-[#6b7280]">
              {page + 1} / {totalPages || 1}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
              className="px-3 py-2 border border-[#d1d5db] rounded-lg text-sm text-[#374151] hover:bg-[#f3f4f6] disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
