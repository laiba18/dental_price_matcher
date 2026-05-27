import { useCallback, useRef, useState } from "react";
import { Button } from "../ui/Button";
import "./FileUploadZone.css";

interface FileUploadZoneProps {
  file: File | null;
  onFileSelect: (file: File) => void;
  onClear: () => void;
  disabled?: boolean;
}

export function FileUploadZone({
  file,
  onFileSelect,
  onClear,
  disabled = false,
}: FileUploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = useCallback(
    (next: File | undefined) => {
      if (!next || !next.name.toLowerCase().endsWith(".pdf")) return;
      onFileSelect(next);
    },
    [onFileSelect],
  );

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    handleFile(e.dataTransfer.files[0]);
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    handleFile(e.target.files?.[0]);
  }

  function clearSelection() {
    onClear();
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div className="upload-zone">
      <div
        className={`upload-zone__drop ${dragOver ? "upload-zone__drop--over" : ""} ${
          disabled ? "upload-zone__drop--disabled" : ""
        } ${file ? "upload-zone__drop--selected" : ""}`}
        onClick={() => !disabled && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        role="button"
        tabIndex={disabled ? -1 : 0}
        onKeyDown={(e) => e.key === "Enter" && !disabled && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          className="upload-zone__input"
          onChange={onInputChange}
          disabled={disabled}
        />

        <div className="upload-zone__icon" aria-hidden="true">
          {file ? (
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
              <path
                d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path d="M14 2v6h6M9 13h6M9 17h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          ) : (
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
              <path
                d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </div>

        {file ? (
          <>
            <p className="upload-zone__title">{file.name}</p>
            <p className="upload-zone__hint">
              {(file.size / 1024).toFixed(1)} KB · Ready to analyze
            </p>
          </>
        ) : (
          <>
            <p className="upload-zone__title">Drop your PDF here or click to browse</p>
            <p className="upload-zone__hint">Henry Schein order confirmation PDFs only</p>
          </>
        )}
      </div>

      {file && !disabled && (
        <Button variant="ghost" size="sm" onClick={clearSelection} className="upload-zone__clear">
          Choose a different file
        </Button>
      )}
    </div>
  );
}
