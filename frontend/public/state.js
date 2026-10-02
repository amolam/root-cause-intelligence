// Application State & Debug Logger
export const categories = {
  FIT: ["TOO_SMALL", "TOO_LARGE", "SIZE_MISMATCH", "LENGTH_ISSUE", "WIDTH_ISSUE", "FIT_UNCOMFORTABLE"],
  QUALITY: ["STITCHING", "FABRIC_QUALITY", "SEAM", "PRINT", "BUTTON", "ZIPPER"],
  COLOUR: ["COLOUR_MISMATCH", "FADED", "DIFFERENT_FROM_IMAGE"],
  MATERIAL: ["FABRIC_DIFFERENT", "FABRIC_UNCOMFORTABLE", "FABRIC_THICKNESS"],
  PRODUCT_MISMATCH: ["WRONG_PRODUCT", "DIFFERENT_PRODUCT"],
  DAMAGED: ["PRODUCT_DAMAGED"],
  DELIVERY: ["DELIVERY_RELATED"],
  OTHER: ["OTHER", "LOW_CONFIDENCE"],
};

export const state = {
  apiUrl: localStorage.getItem("dhaga_api_url") || "http://localhost:8000",
  isConnected: false,
  theme: localStorage.getItem("dhaga_theme") || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
};

const isDebug = window.location.search.includes("debug=1");
export function log(...args) {
  if (isDebug) {
    console.log("[DhagaDebug]", ...args);
  }
}
export function errorLog(...args) {
  if (isDebug) {
    console.error("[DhagaDebugError]", ...args);
  }
}
