"use client";

import { KeyboardEvent, type ReactNode, useEffect, useRef, useState } from "react";

import { getProspectLocationSuggestions } from "@/src/lib/api";
import { useDebouncedValue } from "@/src/lib/hooks";

export type LocationSuggestion = { description: string; place_id: string };

type LocationAutocompleteFieldProps = {
  id: string;
  label: string;
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  hint?: ReactNode;
};

export function LocationAutocompleteField({
  id,
  label,
  value,
  onChange,
  placeholder,
  hint
}: LocationAutocompleteFieldProps) {
  const [suggestions, setSuggestions] = useState<LocationSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const debouncedQuery = useDebouncedValue(value.trim(), 280);
  const pickedRef = useRef<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (pickedRef.current !== null && debouncedQuery === pickedRef.current) {
      setSuggestions([]);
      return;
    }
    if (debouncedQuery.length < 2) {
      setSuggestions([]);
      setOpen(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    void getProspectLocationSuggestions(debouncedQuery)
      .then((res) => {
        if (cancelled) {
          return;
        }
        const next = res.suggestions ?? [];
        setSuggestions(next);
        setOpen(next.length > 0);
        setHighlight(-1);
      })
      .catch(() => {
        if (!cancelled) {
          setSuggestions([]);
          setOpen(false);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [debouncedQuery]);

  function handleInputChange(next: string) {
    if (next === "") {
      pickedRef.current = null;
    } else if (pickedRef.current !== null && next !== pickedRef.current) {
      pickedRef.current = null;
    }
    onChange(next);
  }

  function pick(s: LocationSuggestion) {
    pickedRef.current = s.description;
    onChange(s.description);
    setSuggestions([]);
    setOpen(false);
    setHighlight(-1);
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (!open || suggestions.length === 0) {
      return;
    }
    if (e.key === "Escape") {
      setOpen(false);
      setHighlight(-1);
      e.preventDefault();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => (h + 1 >= suggestions.length ? 0 : h + 1));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => (h <= 0 ? suggestions.length - 1 : h - 1));
      return;
    }
    if (e.key === "Enter" && highlight >= 0 && highlight < suggestions.length) {
      e.preventDefault();
      pick(suggestions[highlight]);
    }
  }

  useEffect(() => {
    if (highlight < 0 || !listRef.current) {
      return;
    }
    const row = listRef.current.querySelector<HTMLElement>(`[data-index="${highlight}"]`);
    row?.scrollIntoView({ block: "nearest" });
  }, [highlight]);

  return (
    <div className="field location-autocomplete-wrap">
      <label htmlFor={id}>{label}</label>
      <div className="location-autocomplete-inner">
        <input
          id={id}
          value={value}
          onChange={(e) => handleInputChange(e.target.value)}
          onFocus={() => {
            if (suggestions.length > 0) {
              setOpen(true);
            }
          }}
          onBlur={() => {
            window.setTimeout(() => setOpen(false), 180);
          }}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          autoComplete="off"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={`${id}-suggestions`}
          role="combobox"
        />
        {loading ? <span className="location-autocomplete-loading muted">Searching…</span> : null}
        {open && suggestions.length > 0 ? (
          <div
            id={`${id}-suggestions`}
            ref={listRef}
            className="location-suggestions-dropdown"
            role="listbox"
          >
            {suggestions.map((s, i) => (
              <button
                key={s.place_id}
                type="button"
                data-index={i}
                role="option"
                aria-selected={i === highlight}
                className={`location-suggestion-item${i === highlight ? " is-active" : ""}`}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(s)}
              >
                {s.description}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {hint ? (
        <p className="muted" style={{ marginTop: 6, fontSize: "0.85rem" }}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}
