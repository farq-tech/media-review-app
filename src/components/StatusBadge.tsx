"use client";

const STATUS_STYLES: Record<string, string> = {
  Draft: "bg-amber-100 text-amber-800",
  Pending: "bg-amber-100 text-amber-800",
  Reviewed: "bg-green-100 text-green-800",
  Approved: "bg-green-100 text-green-800",
  Rejected: "bg-red-100 text-red-800",
  Archived: "bg-gray-100 text-gray-800",
  Flagged: "bg-orange-100 text-orange-800",
};

export default function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] || "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${style}`}>
      {status || "Draft"}
    </span>
  );
}
