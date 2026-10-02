// Connection Module – auto-connects to the default API on load
import { state, log } from "./state.js";
import { request } from "./api.js";
import { updateConnectionStatus, showToast } from "./ui.js";

const DEFAULT_API_URL = "http://localhost:8000";

export async function initConnection(onConnectSuccess) {
  const saved = localStorage.getItem("dhaga_api_url") || DEFAULT_API_URL;
  state.apiUrl = saved;

  updateConnectionStatus("connecting", "Connecting...");
  log("Auto-connecting to", state.apiUrl);

  try {
    await request("/api/dashboard/summary");
    state.isConnected = true;
    updateConnectionStatus("connected", "Connected");
    if (typeof onConnectSuccess === "function") {
      await onConnectSuccess();
    }
  } catch (error) {
    state.isConnected = false;
    updateConnectionStatus("failed", "Connection Failed");
    showToast("Could not reach API server: " + error.message, "error");
  }
}
