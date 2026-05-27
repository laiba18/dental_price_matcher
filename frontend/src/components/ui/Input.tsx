import { InputHTMLAttributes, forwardRef } from "react";
import "./Input.css";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, id, className = "", ...props }, ref) => {
    const inputId = id ?? label.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className={`input-field ${error ? "input-field--error" : ""} ${className}`}>
        <label htmlFor={inputId} className="input-field__label">
          {label}
        </label>
        <input ref={ref} id={inputId} className="input-field__input" {...props} />
        {error && <span className="input-field__error">{error}</span>}
      </div>
    );
  },
);

Input.displayName = "Input";
