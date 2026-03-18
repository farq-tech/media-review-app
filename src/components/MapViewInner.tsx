"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { MapMarker } from "./MapView";

interface MapViewInnerProps {
  markers: MapMarker[];
  center?: [number, number];
  zoom?: number;
  height?: string;
  onMarkerClick?: (id: string) => void;
}

// Fix Leaflet default icon issue
const defaultIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
});

export default function MapViewInner({
  markers,
  center = [24.7136, 46.6753],
  zoom = 10,
  height = "420px",
  onMarkerClick,
}: MapViewInnerProps) {
  const mapRef = useRef<L.Map | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    mapRef.current = L.map(containerRef.current).setView(center, zoom);

    L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>',
      maxZoom: 19,
    }).addTo(mapRef.current);

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current) return;

    // Clear existing markers
    mapRef.current.eachLayer((layer) => {
      if (layer instanceof L.Marker) mapRef.current?.removeLayer(layer);
    });

    // Add markers
    for (const m of markers) {
      if (!m.lat || !m.lng || isNaN(m.lat) || isNaN(m.lng)) continue;

      const marker = L.marker([m.lat, m.lng], { icon: defaultIcon })
        .addTo(mapRef.current!);

      marker.bindPopup(`
        <div style="font-family: sans-serif;">
          <strong style="color: #374151;">${m.label}</strong>
          ${m.sublabel ? `<br><span style="color: #6b7280; font-size: 12px;">${m.sublabel}</span>` : ""}
        </div>
      `);

      if (onMarkerClick) {
        marker.on("click", () => onMarkerClick(m.id));
      }
    }

    // Fit bounds if markers exist
    if (markers.length > 0) {
      const validMarkers = markers.filter((m) => m.lat && m.lng && !isNaN(m.lat) && !isNaN(m.lng));
      if (validMarkers.length > 0) {
        const bounds = L.latLngBounds(validMarkers.map((m) => [m.lat, m.lng]));
        mapRef.current.fitBounds(bounds, { padding: [30, 30] });
      }
    }
  }, [markers, onMarkerClick]);

  return (
    <div
      ref={containerRef}
      className="rounded-xl overflow-hidden border border-[#e5e7eb]"
      style={{ height, width: "100%" }}
    />
  );
}
