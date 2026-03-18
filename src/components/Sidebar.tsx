"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: "📊" },
  {
    label: "Review",
    href: "/dashboard/review",
    icon: "📋",
    children: [
      { href: "/dashboard/review", label: "Review Queue" },
      { href: "/dashboard/excel", label: "Excel View" },
      { href: "/dashboard/media", label: "Media Gallery" },
    ],
  },
  {
    label: "Analysis",
    href: "/dashboard/map",
    icon: "🗺️",
    children: [
      { href: "/dashboard/map", label: "Map View" },
      { href: "/dashboard/duplicates", label: "Duplicates" },
      { href: "/dashboard/match-review", label: "Match Review" },
      { href: "/dashboard/audit", label: "Audit Log" },
    ],
  },
  {
    label: "Operations",
    href: "/dashboard/drafts",
    icon: "⚙️",
    children: [
      { href: "/dashboard/drafts", label: "Drafts" },
      { href: "/dashboard/invoice", label: "Invoice" },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const isActive = (href: string) => pathname === href;
  const isSectionActive = (item: (typeof nav)[0]) => {
    if (!("children" in item) || !item.children) return pathname === item.href;
    return item.children.some((c) => pathname === c.href) || pathname === item.href;
  };

  return (
    <aside className="w-64 min-h-screen bg-white border-r border-[#e5e7eb] flex flex-col">
      {/* Logo */}
      <div className="p-4 border-b border-[#e5e7eb] flex items-center gap-2">
        <span className="w-9 h-9 rounded-lg bg-[#22c55e] flex items-center justify-center text-white font-bold text-lg">
          F
        </span>
        <span className="font-semibold text-[#374151]">Farq</span>
        <span className="ml-auto px-2 py-0.5 bg-amber-500 text-white text-xs font-medium rounded">
          Review
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        {nav.map((item) => (
          <div key={item.href}>
            {item.children ? (
              <>
                <Link
                  href={item.href}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium ${
                    isSectionActive(item)
                      ? "bg-[#22c55e]/10 text-[#22c55e]"
                      : "text-[#374151] hover:bg-[#f3f4f6]"
                  }`}
                >
                  <span>{item.icon}</span>
                  {item.label}
                  <span className="ml-auto">{isSectionActive(item) ? "▾" : "›"}</span>
                </Link>
                {isSectionActive(item) && (
                  <div className="ml-4 mt-1 space-y-0.5">
                    {item.children.map((child) => (
                      <Link
                        key={child.href}
                        href={child.href}
                        className={`block px-3 py-2 rounded-lg text-sm ${
                          isActive(child.href)
                            ? "bg-[#22c55e]/10 text-[#22c55e] font-medium"
                            : "text-[#6b7280] hover:bg-[#f3f4f6]"
                        }`}
                      >
                        {child.label}
                      </Link>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <Link
                href={item.href}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium ${
                  isActive(item.href)
                    ? "bg-[#22c55e]/10 text-[#22c55e]"
                    : "text-[#374151] hover:bg-[#f3f4f6]"
                }`}
              >
                <span>{item.icon}</span>
                {item.label}
              </Link>
            )}
          </div>
        ))}
      </nav>

      {/* User footer */}
      <div className="p-3 border-t border-[#e5e7eb]">
        <div className="flex items-center gap-2 px-2 mb-1">
          {user?.color && (
            <span
              className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold"
              style={{ backgroundColor: user.color }}
            >
              {user.username?.charAt(0).toUpperCase()}
            </span>
          )}
          <span className="text-xs text-[#6b7280] truncate">{user?.display_name || user?.username}</span>
        </div>
        <button
          onClick={logout}
          className="mt-1 w-full text-left px-3 py-2 text-sm text-[#6b7280] hover:bg-[#f3f4f6] rounded-lg"
        >
          Logout
        </button>
      </div>
    </aside>
  );
}
