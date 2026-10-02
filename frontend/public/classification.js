// Classification Module
import { request, $ } from "./api.js";
import { showToast } from "./ui.js";

export function initClassification() {
  const form = $('classify-form');
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const returnIdInput = $('return-id');
    const returnId = returnIdInput ? returnIdInput.value.trim() : '';
    const errorEl = $('return-id-error');
    const resultEl = $('classification-result');
    const submitBtn = form.querySelector('button[type="submit"]');

    // Clear previous error
    if (errorEl) errorEl.classList.add("hidden");
    if (resultEl) resultEl.classList.add("hidden");

    // Validate Return ID format
    if (!returnId) {
      showError("Please enter a return ID.");
      return;
    }

    if (!/^RET-/.test(returnId)) {
      showError("Return ID must start with 'RET-'");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Classifying...";

    try {
      const result = await request(`/api/returns/${encodeURIComponent(returnId)}/classify`, { method: "POST" });
      resultEl.classList.remove("hidden");
      const categoryText = `${result.predicted_category || ''}/${result.predicted_subcategory || ''}`;
      const conf = Math.round((Number(result.confidence_score) || 0) * 100);
      resultEl.textContent = `${result.return_id}: ${categoryText} · ${conf}% confidence`;
      showToast("Classification complete.", "success");
    } catch (error) {
      showError(error.message);
      showToast(error.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Classify";
    }
  });

  function showError(message) {
    const errorEl = $('return-id-error');
    if (errorEl) {
      errorEl.textContent = message;
      errorEl.classList.remove("hidden");
    }
  }
}
