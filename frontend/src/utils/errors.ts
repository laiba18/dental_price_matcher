export type ErrorCode =
  | "UPLOAD_FAILED"
  | "NETWORK_ERROR"
  | "TIMEOUT"
  | "API_ERROR"
  | "PDF_EXTRACTION_FAILED"
  | "NO_LINE_ITEMS"
  | "PROCESSING_FAILED"
  | "UNEXPECTED_ERROR"
  | "INVALID_FILE"
  | "FILE_TOO_LARGE"
  | "CONNECTION_LOST"
  | "UNKNOWN";

export interface AppError {
  message: string;
  code: ErrorCode;
  title: string;
  suggestion: string;
}

export function classifyError(raw: string, code?: string): AppError {
  const normalized = (code ?? inferCode(raw)).toUpperCase() as ErrorCode;

  const catalog: Record<string, Omit<AppError, "message" | "code">> = {
    UPLOAD_FAILED: {
      title: "Upload failed",
      suggestion: "Check your connection and try uploading the file again.",
    },
    NETWORK_ERROR: {
      title: "Network error",
      suggestion: "Verify your internet connection and that the backend server is running.",
    },
    TIMEOUT: {
      title: "Request timed out",
      suggestion: "The server took too long to respond. Try again with a smaller PDF or retry later.",
    },
    API_ERROR: {
      title: "Server error",
      suggestion: "Something went wrong on the server. Please try again in a few minutes.",
    },
    PDF_EXTRACTION_FAILED: {
      title: "Could not read PDF",
      suggestion: "Ensure the file is a valid Henry Schein order PDF and is not password-protected.",
    },
    NO_LINE_ITEMS: {
      title: "No order items found",
      suggestion: "Upload a Henry Schein order confirmation PDF that contains line items.",
    },
    PROCESSING_FAILED: {
      title: "Processing failed",
      suggestion: "Review the error details below and try uploading the file again.",
    },
    UNEXPECTED_ERROR: {
      title: "Unexpected error",
      suggestion: "An unexpected issue occurred. Please retry or contact support if this persists.",
    },
    INVALID_FILE: {
      title: "Invalid file",
      suggestion: "Only valid PDF files are accepted. Export your order as PDF and try again.",
    },
    FILE_TOO_LARGE: {
      title: "File too large",
      suggestion: "Reduce the file size or split the order. Maximum upload size is 25 MB.",
    },
    CONNECTION_LOST: {
      title: "Connection lost",
      suggestion: "The connection to the server was interrupted. Check if processing completed in Past Orders.",
    },
    UNKNOWN: {
      title: "Something went wrong",
      suggestion: "Please try again. If the problem continues, refresh the page.",
    },
  };

  const meta = catalog[normalized] ?? catalog.UNKNOWN;
  return {
    message: raw,
    code: catalog[normalized] ? normalized : "UNKNOWN",
    ...meta,
  };
}

function inferCode(message: string): ErrorCode {
  const m = message.toLowerCase();
  if (m.includes("network") || m.includes("fetch")) return "NETWORK_ERROR";
  if (m.includes("timeout") || m.includes("timed out")) return "TIMEOUT";
  if (m.includes("empty")) return "INVALID_FILE";
  if (m.includes("too large")) return "FILE_TOO_LARGE";
  if (m.includes("invalid") && m.includes("pdf")) return "INVALID_FILE";
  if (m.includes("extraction failed")) return "PDF_EXTRACTION_FAILED";
  if (m.includes("no line items")) return "NO_LINE_ITEMS";
  if (m.includes("connection") || m.includes("lost connection")) return "CONNECTION_LOST";
  if (m.includes("upload")) return "UPLOAD_FAILED";
  return "UNKNOWN";
}

export function validatePdfFile(file: File): AppError | null {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    return classifyError("Only PDF files are accepted.", "INVALID_FILE");
  }
  if (file.size === 0) {
    return classifyError("The selected file is empty.", "INVALID_FILE");
  }
  if (file.size > 25 * 1024 * 1024) {
    return classifyError("File exceeds the 25 MB upload limit.", "FILE_TOO_LARGE");
  }
  return null;
}
