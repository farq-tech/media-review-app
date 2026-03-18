"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import Sidebar from "@/components/Sidebar";
import { POIProvider } from "@/contexts/POIContext";
import { ToastProvider } from "@/components/Toast";
import { SyncProvider } from "@/contexts/SyncContext";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isReady } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isReady) return;
    if (!user) {
      router.replace("/login");
    }
  }, [user, isReady, router]);

  if (!isReady || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#f2f2f2]">
        <p className="text-[#6b7280]">Loading...</p>
      </div>
    );
  }

  return (
    <POIProvider>
      <SyncProvider>
        <ToastProvider>
          <div className="flex min-h-screen bg-[#f9fafb]">
            <Sidebar />
            <main className="flex-1 overflow-auto p-6">{children}</main>
          </div>
        </ToastProvider>
      </SyncProvider>
    </POIProvider>
  );
}
