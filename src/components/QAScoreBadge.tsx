"use client";

export default function QAScoreBadge({ score }: { score: number }) {
  let color = "bg-red-100 text-red-800";
  if (score >= 80) color = "bg-green-100 text-green-800";
  else if (score >= 50) color = "bg-amber-100 text-amber-800";

  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      QA: {score}
    </span>
  );
}
