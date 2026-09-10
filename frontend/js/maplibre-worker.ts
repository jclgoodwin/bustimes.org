import * as maplibreGlWorker from "maplibre-gl/dist/maplibre-gl-worker.mjs";

// @ts-expect-error prevent tree-shaking of the worker's side effects
globalThis.__maplibreGlWorker = maplibreGlWorker;
