import { useState, type FormEvent } from "react";
import { uploadDataset } from "../data/api";

interface Props {
  hostedDemo?: boolean;
  onCreated: (datasetId: string) => void;
}

const HOSTED_UPLOAD_MESSAGE =
  "Dataset upload is available when running SwarmLens locally. This hosted demo uses precomputed investigations.";

export function DatasetLauncher({ hostedDemo = false, onCreated }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hostedMessageVisible, setHostedMessageVisible] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      const dataset = await uploadDataset(file);
      onCreated(dataset.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The dataset could not be uploaded.");
      setBusy(false);
    }
  };

  if (hostedDemo) {
    return (
      <div className="dataset-launcher dataset-launcher--hosted">
        <span className="dataset-launcher-label">Dataset bundle</span>
        <button
          className="outline-button"
          type="button"
          onClick={() => setHostedMessageVisible(true)}
        >
          Upload dataset
        </button>
        <small>
          Upload and runtime analysis are available in the local application.{" "}
          <a href="https://github.com/reelaughs/swarm-lens#running-locally">View local setup instructions.</a>
        </small>
        {hostedMessageVisible && (
          <p className="hosted-upload-message" role="status">{HOSTED_UPLOAD_MESSAGE}</p>
        )}
      </div>
    );
  }

  return (
    <form className="dataset-launcher" onSubmit={submit}>
      <label htmlFor="dataset-bundle">AI Village ZIP</label>
      <input
        id="dataset-bundle"
        type="file"
        accept=".zip,application/zip"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
      />
      <button className="outline-button" type="submit" disabled={!file || busy}>
        {busy ? "Uploading…" : "Add dataset"}
      </button>
      <small>
        Initial support accepts the documented AI Village tables and CHANGELOG in one ZIP. Other
        multi-agent formats are not yet supported.
      </small>
      {error && <p className="workflow-error" role="alert">{error}</p>}
    </form>
  );
}
