"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

const DEFAULT_CENTER = "39.727132,-121.843275";

export interface LocationMapProps {
  value: string;
  onChange: (latLng: string) => void;
  placeholder?: string;
  className?: string;
}

const LocationMapInner = dynamic(
  () => import("./LocationMapInner").then((m) => m.LocationMapInner),
  { ssr: false, loading: () => <div className="location-map-placeholder">Loading map...</div> }
);

export function LocationMap({ value, onChange, placeholder = "Click map or enter lat,lng", className = "" }: LocationMapProps) {
  const [inputValue, setInputValue] = useState(value || DEFAULT_CENTER);

  useEffect(() => {
    if (value) setInputValue(value);
  }, [value]);

  function handleChange(latLng: string) {
    setInputValue(latLng);
    onChange(latLng);
  }

  return (
    <div className={`location-map-wrap ${className}`}>
      <LocationMapInner value={inputValue} onChange={handleChange} />
      <input
        type="text"
        value={inputValue}
        onChange={(e) => {
          setInputValue(e.target.value);
          onChange(e.target.value);
        }}
        onBlur={(e) => {
          const v = e.target.value.trim();
          if (v) handleChange(v);
        }}
        placeholder={placeholder}
        className="location-map-input"
      />
    </div>
  );
}
