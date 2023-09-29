import * as esbuild from "esbuild";



let context = await esbuild.context({
  entryPoints: ["busstops/static/js/src/app.tsx", "busstops/static/js/src/bigmap.js", "busstops/static/js/src/bigmap-classic.js"],
  outdir: "busstops/static/js/dist",
  bundle: true,

  sourcemap: true,


  loader: { ".png": "dataurl" },
  define: {
    "process.env.API_ROOT": '"https://bustimes.org/"'
  }
});

await context.watch();
