import React, { type ReactElement } from "react";

export default function LoadingSorry({
  text,
}: {
  text?: string | ReactElement;
}) {
  return <div className="sorry">{text || "Loading…"}</div>;
}
