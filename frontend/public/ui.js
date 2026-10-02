// UI Utilities: Toasts, Theme, Connection Status Pill, Skeletons
import { state } from './state.js';
import { $ } from './api.js';

export function initTheme() {
  const root = document.documentElement;
  const toggleBtn = $('theme-toggle');
  
  // Set initial state
  if (state.theme === 'dark') {
    root.setAttribute('data-theme', 'dark');
  } else {
    root.setAttribute('data-theme', 'light');
  }
  updateThemeToggleIcon(toggleBtn, state.theme);

  if (toggleBtn) {
    toggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const current = root.getAttribute('data-theme');
      const nextTheme = current === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', nextTheme);
      state.theme = nextTheme;
      localStorage.setItem('dhaga_theme', state.theme);
      updateThemeToggleIcon(toggleBtn, nextTheme);
      console.log("Theme toggled to:", state.theme);
    });
  } else {
    console.error("Theme toggle button not found!");
  }
}

function updateThemeToggleIcon(btn, theme) {
  if (!btn) return;
  if (theme === 'dark') {
    btn.setAttribute('title', 'Switch to light mode');
    btn.setAttribute('aria-label', 'Switch to light mode');
    // Sun Icon when dark mode active
    btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>';
  } else {
    btn.setAttribute('title', 'Switch to dark mode');
    btn.setAttribute('aria-label', 'Switch to dark mode');
    // Moon Icon when light mode active
    btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>';
  }
}

export function showToast(message, type = 'success') {
  const container = $('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast ' + type;
  
  let iconSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>';
  if (type === 'error') {
    iconSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
  } else if (type === 'warning') {
    iconSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
  }

  toast.innerHTML = '<div>' + iconSvg + '</div><div style="flex:1"><p style="margin:0;font-size:0.9rem;font-weight:500;">' + message + '</p></div>';
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(1rem)';
    toast.style.transition = 'all 200ms ease-in';
    setTimeout(() => toast.remove(), 200);
  }, 4000);
}

export function updateConnectionStatus(status, text) {
  const pill = $('connection-state');
  if (!pill) return;

  pill.className = 'status-pill ' + status;
  let dotHtml = '<span class="status-dot"></span>';
  pill.innerHTML = dotHtml + '<span>' + text + '</span>';
}

export function pct(ratio) {
  return (Number(ratio || 0) * 100).toFixed(1) + '%';
}
