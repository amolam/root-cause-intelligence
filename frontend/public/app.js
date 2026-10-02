// Main Application Entry Point
import { initTheme } from './ui.js';
import { initConnection } from './connection.js';
import { initDashboard, refreshDashboard } from './dashboard.js';
import { initClassification } from './classification.js';
import { log } from './state.js';

document.addEventListener('DOMContentLoaded', async () => {
  log('Initializing Dhaga Return Intelligence v2.0.0');

  // Initialize UI theme toggle
  initTheme();

  // Initialize dashboard refresh triggers
  initDashboard();

  // Initialize return classification form
  initClassification();

  // Initialize connection handler with automatic dashboard refresh on success
  initConnection(async () => {
    await refreshDashboard();
  });

  // Attempt auto-connect if saved API URL exists
  const savedApi = localStorage.getItem('dhaga_api_url');
  if (savedApi) {
    log('Found saved API URL, auto-connecting...');
    const connectBtn = document.getElementById('connect');
    if (connectBtn) {
      connectBtn.click();
    }
  }
});
