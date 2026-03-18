"use client";

import dynamic from "next/dynamic";

interface MapMarker {
  id: string;
  lat: number;
  lng: number;
  label: string;
  sublabel?: string;
  color?: string;
}

interface MapViewProps {
  markers: MapMarker[];
  center?: [number, number];
  zoom?: number;
  height?: string;
  onMarkerClick?: (id: string) => void;
}

const MapViewInner = dynamic(() => import("./MapViewInner"), {
  ssr: false,
  loading: () => (
    <div className="bg-[#f3f4f6] rounded-xl flex items-center justify-center animate-pulse" style={{ height: "420px" }}>
      <span className="text-[#6b7280]">Loading map...</span>
    </div>
  ),
});

export default function MapView(props: MapViewProps) {
  return <MapViewInner {...props} />;
}

export type { MapMarker, MapViewProps };
