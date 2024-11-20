import React from "react";

export default function LoadingSorry({ text }: { text?: string }) {
  return <div className="sorry">{ text || "Loading…" }</div>;
}
