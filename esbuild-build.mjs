import * as esbuild from "esbuild";

import { sentryEsbuildPlugin } from "@sentry/esbuild-plugin";

await esbuild.build({
  entryPoints: ["busstops/static/js/src/app.tsx"],
  outdir: "busstops/static/js/dist",
  bundle: true,
  minify: true,
  sourcemap: true,
  target: "chrome71",

  loader: { ".png": "dataurl" },
  define: {
    "process.env.API_ROOT": '"https://bustimes.org/"'
  },

  plugins: [
    // Put the Sentry esbuild plugin after all other plugins
    sentryEsbuildPlugin({
      authToken: process.env.SENTRY_AUTH_TOKEN,
      org: "josh-goodwin",
      project: "bus-times-js",
    }),
  ],
});
