import type { AppError } from "../../utils/errors";
import { Button } from "../ui/Button";
import { Alert } from "../ui/Alert";
import { FileUploadZone } from "./FileUploadZone";
import "./UploadSection.css";

interface UploadSectionProps {
  selectedFile: File | null;
  onFileSelect: (file: File) => void;
  onClear: () => void;
  onSubmit: () => void;
  onValidationError?: (error: AppError) => void;
  disabled?: boolean;
  loading?: boolean;
  error?: AppError | null;
}

export function UploadSection({
  selectedFile,
  onFileSelect,
  onClear,
  onSubmit,
  onValidationError,
  disabled = false,
  loading = false,
  error,
}: UploadSectionProps) {
  return (
    <div className="upload-section">
      <div className="upload-section__inner">
        <div className="upload-section__icon-row">
          <div className="upload-section__icon" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path
                d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div className="upload-section__heading">
            <h2 className="upload-section__title">New Analysis</h2>
            <p className="upload-section__subtitle">
              Upload a Henry Schein order PDF to generate price match reports
            </p>
          </div>
        </div>

        <div className="upload-section__body">
          <FileUploadZone
            file={selectedFile}
            onFileSelect={onFileSelect}
            onClear={onClear}
            onValidationError={onValidationError}
            disabled={disabled}
          />

          {error && (
            <Alert variant="error" title={error.title}>
              {error.message}
              <p className="upload-section__suggestion">{error.suggestion}</p>
            </Alert>
          )}

          <Button
            fullWidth
            size="lg"
            loading={loading}
            disabled={!selectedFile || disabled}
            onClick={onSubmit}
            className="upload-section__submit"
          >
            {loading ? "Starting analysis…" : "Run Price Analysis →"}
          </Button>

          <p className="upload-section__hint">
            PDF only
            <span className="upload-section__hint-dot" />
            Max 25 MB
            <span className="upload-section__hint-dot" />
            Henry Schein orders
          </p>
        </div>
      </div>
    </div>
  );
}
