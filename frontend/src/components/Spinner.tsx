interface SpinnerProps {
  size?: "sm" | "md";
  label?: string;
}

export function Spinner({ size = "md", label }: SpinnerProps) {
  const className = size === "sm" ? "spinner spinner-sm" : "spinner";
  return (
    <span className="spinner-wrap" role="status" aria-live="polite" aria-label={label ?? "Loading"}>
      <span className={className} />
      {label ? <span className="spinner-label">{label}</span> : null}
    </span>
  );
}
