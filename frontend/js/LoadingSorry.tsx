import React, { type ReactElement } from "react";

export default function LoadingSorry({
  text,
}: {
  text?: string | ReactElement;
}) {
  return <div className="sorry">{text || "Loading…"}</div>;
}

export function ErrorFallback(error: { error?: unknown }) {
  return (
    <LoadingSorry
      text={
        <>
          <p>{error.error?.toString() || "Sorry, something has gone wrong"}</p>
          <p>
            <button
              type="button"
              className="button"
              onClick={() => window.location.reload()}
            >
              ↻ Try again
            </button>
          </p>
        </>
      }
    />
  );
}
