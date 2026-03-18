"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

export default function HomePage() {
  const { user, isReady } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isReady) return;
    if (user) router.replace("/dashboard");
    else router.replace("/login");
  }, [user, isReady, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f2f2f2]">
      <p className="text-[#6b7280]">Loading...</p>
    </div>
  );
}
