"use client";

import { useEffect, useRef } from "react";

const DEFAULT_CENTER: [number, number] = [39.727132, -121.843275];
const DEFAULT_ZOOM = 12;

export interface LocationMapInnerProps {
  value: string;
  onChange: (latLng: string) => void;
}

function parseLatLng(value: string): [number, number] | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parts = trimmed.split(",").map((p) => p.trim());
  if (parts.length !== 2) return null;
  const lat = parseFloat(parts[0]);
  const lng = parseFloat(parts[1]);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
  return [lat, lng];
}

function formatLatLng(lat: number, lng: number): string {
  return `${lat.toFixed(6)},${lng.toFixed(6)}`;
}

export function LocationMapInner({ value, onChange }: LocationMapInnerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    if (!containerRef.current || typeof window === "undefined") return;
    require("leaflet/dist/leaflet.css");
    require("leaflet-defaulticon-compatibility");
    const L = require("leaflet");

    const [lat, lng] = parseLatLng(value) ?? DEFAULT_CENTER;
    const map = L.map(containerRef.current).setView([lat, lng], DEFAULT_ZOOM);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap"
    }).addTo(map);

    const marker = L.marker([lat, lng], { draggable: true }).addTo(map);
    marker.on("dragend", () => {
      const pos = marker.getLatLng();
      onChangeRef.current(formatLatLng(pos.lat, pos.lng));
    });

    map.on("click", (e: L.LeafletMouseEvent) => {
      const { lat: la, lng: ln } = e.latlng;
      marker.setLatLng([la, ln]);
      onChangeRef.current(formatLatLng(la, ln));
    });

    mapRef.current = map;
    markerRef.current = marker;

    return () => {
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !markerRef.current) return;
    const parsed = parseLatLng(value);
    if (parsed) {
      mapRef.current.setView(parsed, mapRef.current.getZoom());
      markerRef.current.setLatLng(parsed);
    }
  }, [value]);

  return <div ref={containerRef} className="location-map" />;
}
