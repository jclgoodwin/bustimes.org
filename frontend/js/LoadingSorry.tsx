import React, { type ReactElement } from "react";

export default function LoadingSorry({
  text,
}: { text?: string | ReactElement }) {
  return <div className="sorry">{text || "Loading…"}</div>;
}

export const error = <LoadingSorry text="Sorry, something has gone wrong" />;
