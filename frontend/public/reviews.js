// Reviews Module
import { request, $ } from "./api.js";
import { showToast } from "./ui.js";
import { categories } from "./state.js";

export async function loadReviews() {
  try {
    const rows = await request("/api/reviews/pending");
    const queue = $('review-queue');
    if (!queue) return;

    queue.replaceChildren();

    if (!rows || !rows.length) {
      queue.innerHTML = `
        <div class="empty-state">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <line x1="10" y1="9" x2="8" y2="9"/>
          </svg>
          <p class="text-muted">No returns are waiting for review.</p>
        </div>
      `;
      return;
    }

    for (const row of rows) {
      const card = createReviewCard(row);
      queue.append(card);
    }
  } catch (error) {
    showToast(error.message, "error");
  }
}

function createReviewCard(row) {
  const card = document.createElement("article");
  card.className = "review-card";

  const top = document.createElement("div");
  top.className = "review-meta";
  const title = document.createElement("strong");
  title.textContent = row.return_id + " \u00B7 " + row.sku_id;
  const badge = document.createElement("span");
  badge.className = "badge badge-warning";
  badge.textContent = row.predicted_category + "/" + row.predicted_subcategory + " \u00B7 " + Math.round(Number(row.confidence_score) * 100) + "%";
  top.append(title, badge);
  card.append(top);

  const comment = document.createElement("p");
  comment.className = "review-comment";
  let commentText = "Reason: " + row.return_reason;
  if (row.return_reason_text) {
    commentText += " \u00B7 \"" + row.return_reason_text + "\"";
  }
  comment.textContent = commentText;
  card.append(comment);

  const controls = document.createElement("form");
  controls.className = "review-controls";

  const reviewerLabel = document.createElement("label");
  reviewerLabel.append(document.createTextNode("Reviewer"));
  const reviewerInput = document.createElement("input");
  reviewerInput.type = "text";
  reviewerInput.placeholder = "Name or ID";
  reviewerInput.required = true;
  reviewerLabel.append(reviewerInput);
  controls.append(reviewerLabel);

  const rowDiv = document.createElement("div");
  rowDiv.className = "review-controls-row";

  const categoryLabel = document.createElement("label");
  categoryLabel.append(document.createTextNode("Correct category"));
  const categorySelect = document.createElement("select");
  categorySelect.setAttribute("aria-label", "Correct category");
  categorySelect.required = true;
  Object.keys(categories).forEach((cat) => {
    const option = new Option(cat, cat);
    categorySelect.add(option);
  });
  categoryLabel.append(categorySelect);
  rowDiv.append(categoryLabel);

  const subLabel = document.createElement("label");
  subLabel.append(document.createTextNode("Issue"));
  const subSelect = document.createElement("select");
  subSelect.setAttribute("aria-label", "Issue");
  subSelect.required = true;
  subLabel.append(subSelect);
  rowDiv.append(subLabel);

  controls.append(rowDiv);

  const syncSub = () => {
    const selectedCategory = categorySelect.value;
    const subcats = categories[selectedCategory] || [];
    subSelect.replaceChildren(...subcats.map((sub) => new Option(sub, sub)));
    if (subcats.length > 0) {
      subSelect.value = subcats[0];
    }
  };
  categorySelect.addEventListener("change", syncSub);
  syncSub();

  const submitBtn = document.createElement("button");
  submitBtn.type = "submit";
  submitBtn.textContent = "Save review";
  controls.append(submitBtn);

  controls.addEventListener("submit", async (event) => {
    event.preventDefault();

    const reviewerName = reviewerInput.value.trim();
    if (!reviewerName) {
      showToast("Please enter reviewer name.", "error");
      reviewerInput.focus();
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Saving...";

    try {
      await request("/api/reviews/" + row.analysis_id, {
        method: "POST",
        body: JSON.stringify({
          category: categorySelect.value,
          subcategory: subSelect.value,
          reviewer_id: reviewerName
        })
      });

      showToast("Review saved for " + row.return_id + ".", "success");
      await loadReviews();
    } catch (error) {
      showToast(error.message, "error");
      submitBtn.disabled = false;
      submitBtn.textContent = "Save review";
    }
  });

  card.append(controls);
  return card;
}
