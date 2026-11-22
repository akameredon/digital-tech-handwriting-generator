import { useEffect, useRef, useState } from "react";

type WorksheetScanUploadProps = {
  file: File | null;
  disabled?: boolean;
  onFileChange: (file: File | null) => void;
  onError: (message: string) => void;
};

const MAX_IMAGE_BYTES = 12 * 1024 * 1024;
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png"]);

export default function WorksheetScanUpload({
  file,
  disabled = false,
  onFileChange,
  onError
}: WorksheetScanUploadProps) {
  const browseInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");

  useEffect(() => {
    if (!file) {
      setPreviewUrl("");
      return;
    }

    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function chooseFile(candidate?: File) {
    if (!candidate) return;
    if (!ACCEPTED_TYPES.has(candidate.type)) {
      onError("Choose a JPG or PNG image of the completed worksheet.");
      return;
    }
    if (candidate.size > MAX_IMAGE_BYTES) {
      onError("This image is over 12 MB. Choose a smaller JPG or PNG scan.");
      return;
    }

    onError("");
    onFileChange(candidate);
  }

  function handleInputChange(event: React.ChangeEvent<HTMLInputElement>) {
    chooseFile(event.currentTarget.files?.[0]);
    event.currentTarget.value = "";
  }

  function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!disabled) chooseFile(event.dataTransfer.files[0]);
  }

  function handleDragLeave(event: React.DragEvent<HTMLDivElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setDragging(false);
    }
  }

  function removeFile() {
    onError("");
    onFileChange(null);
  }

  return (
    <div className="scan-upload">
      <input
        ref={browseInput}
        className="file-input-hidden"
        type="file"
        accept="image/jpeg,image/png"
        aria-label="Browse for a completed worksheet scan"
        onChange={handleInputChange}
        disabled={disabled}
      />
      <input
        ref={cameraInput}
        className="file-input-hidden"
        type="file"
        accept="image/jpeg,image/png"
        capture="environment"
        aria-label="Take a photo of the completed worksheet"
        onChange={handleInputChange}
        disabled={disabled}
      />

      <div
        className={`scan-dropzone${dragging ? " dragging" : ""}${file ? " has-file" : ""}`}
        role="region"
        aria-label="Worksheet scan upload area"
        aria-describedby="calibration-scan-help"
        onDragEnter={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        aria-busy={disabled}
      >
        <div className="scan-dropzone-copy">
          <span className="upload-symbol" aria-hidden="true">↑</span>
          <div>
            <strong>{file ? "Worksheet scan selected" : "Choose a worksheet scan"}</strong>
            <small>Drop a JPG or PNG here, or choose it from your device.</small>
          </div>
        </div>
        <div className="scan-actions">
          <button
            className="button button-secondary"
            type="button"
            onClick={() => browseInput.current?.click()}
            disabled={disabled}
          >
            Browse device
          </button>
          <button
            className="button button-secondary camera-button"
            type="button"
            onClick={() => cameraInput.current?.click()}
            disabled={disabled}
          >
            Take photo
          </button>
        </div>
      </div>

      {file && (
        <div className="sample-selected" aria-live="polite">
          {previewUrl && <img className="sample-preview" src={previewUrl} alt="Preview of the selected worksheet scan" />}
          <div className="sample-file-details">
            <strong title={file.name}>{file.name}</strong>
            <small>{formatFileSize(file.size)} · JPG/PNG · ready when you are</small>
          </div>
          <div className="sample-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => browseInput.current?.click()}
              disabled={disabled}
            >
              Change image
            </button>
            <button
              className="button button-quiet"
              type="button"
              onClick={removeFile}
              disabled={disabled}
            >
              Remove
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
