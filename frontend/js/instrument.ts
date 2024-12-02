import * as Sentry from "@sentry/react";

if (process.env.NODE_ENV === "production") {
  Sentry.init({
    dsn: "https://0d628b6fff45463bb803d045b99aa542@o55224.ingest.sentry.io/1379883",
    allowUrls: [/bustimes\.org\/static\//],
    ignoreErrors: [
      // ignore errors in third-party advert code
      "Load failed",
        "Failed to fetch",
        "AbortError: The user aborted a request",
        "AbortError: Fetch is aborted",
        "NetworkError when attempting to fetch resource",
        "Non-Error promise rejection captured with value: undefined",
        "from accessing a cross-origin frame. Protocols, domains, and ports must",
        "Event `Event` (type=error) captured as promise rejection",
        "this.kdmw is not a function",
        "WKWebView API client did not respond to this postMessage",
        "Origin https://bustimes.org is not allowed by Access-Control-Allow-Origin.",
        "Failed to execute 'send' on 'XMLHttpRequest': Failed to load 'https://t.richaudience.com/",
        "undefined is not an object (evaluating 'navigator.connection.effectiveType')",
      ],
      integrations: [
        Sentry.globalHandlersIntegration({
          onerror: true,
          onunhandledrejection: false,
        }),
      ],
    });
  };
