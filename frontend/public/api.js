// API Fetch wrapper with error categorization & retry
import { state, log, errorLog } from './state.js';

export const $ = (id) => document.getElementById(id);

export function getBaseUrl() {
  const inputEl = $('api-url');
  const inputVal = inputEl ? inputEl.value.trim() : state.apiUrl;
  return inputVal.replace(/\/$/, "");
}

export async function request(path, options = {}) {
  const base = getBaseUrl();
  const url = `${base}${path}`;
  log(`Requesting ${url}`);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {})
      },
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    let body = {};
    const text = await response.text();
    if (text) {
      try {
        body = JSON.parse(text);
      } catch (e) {
        body = { detail: text };
      }
    }

    if (!response.ok) {
      let errorType = 'Server Error';
      if (response.status >= 400 && response.status < 500) {
        errorType = 'Client Request Error';
        if (response.status === 404) errorType = 'Resource Not Found';
        if (response.status === 401 || response.status === 403) errorType = 'Authorization Error';
      } else if (response.status >= 500) {
        errorType = 'Server Internal Error';
      }
      const errMessage = body.detail || `${errorType} (${response.status})`;
      errorLog(`API Error on ${url}:`, errMessage);
      throw new Error(errMessage);
    }

    log(`Response success for ${url}`, body);
    return body;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error('Request timed out. Please check if the API server is responsive.');
    }
    if (error.message && (error.message.includes('Failed to fetch') || error.message.includes('NetworkError'))) {
      throw new Error('Network error: Unable to connect to API server. Please check URL and CORS settings.');
    }
    throw error;
  }
}
