import loadjs from "loadjs";

// https://maplibre.org/maplibre-gl-js/docs/examples/check-for-support/
function isWebglSupported() {
  if (window.WebGLRenderingContext) {
    const canvas = document.createElement("canvas");
    try {
      // Note that { failIfMajorPerformanceCaveat: true } can be passed as a second argument
      // to canvas.getContext(), causing the check to fail if hardware rendering is not available. See
      // https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/getContext
      // for more details.
      const context = canvas.getContext("webgl2") || canvas.getContext("webgl");
      if (
        context &&
        typeof context.getParameter === "function" &&
        !context.isContextLost()
      ) {
        return true;
      }
    } catch (e) {
      // WebGL is supported, but disabled
    }
    return false;
  }
  return false;
}

if (typeof window.fetch !== "undefined" && isWebglSupported()) {
  loadjs(window.NEW_JS, {
    async: false,
  });
} else {
  loadjs(window.OLD_JS, {
    async: false,
  });
}
