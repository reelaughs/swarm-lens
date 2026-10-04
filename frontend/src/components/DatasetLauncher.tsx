import { useState, type FormEvent } from "react";
import { uploadDataset } from "../data/api";

interface Props {
  onCreated: (datasetId: string) => void;
}

export function DatasetLauncher({ onCreated }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
