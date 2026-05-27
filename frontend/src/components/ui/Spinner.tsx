import "./Spinner.css";

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  label?: string;
}

export function Spinner({ size = "md", label }: SpinnerProps) {
  return (
    <div className="spinner-wrap" role="status">
      <div className={`spinner spinner--${size}`} aria-hidden="true" />
      {label && <span className="spinner__label">{label}</span>}
    </div>
  );
}
