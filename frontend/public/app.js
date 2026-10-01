const $ = (id) => document.getElementById(id);
const categories = {
  FIT: ["TOO_SMALL", "TOO_LARGE", "SIZE_MISMATCH", "LENGTH_ISSUE", "WIDTH_ISSUE", "FIT_UNCOMFORTABLE"],
  QUALITY: ["STITCHING", "FABRIC_QUALITY", "SEAM", "PRINT", "BUTTON", "ZIPPER"],
  COLOUR: ["COLOUR_MISMATCH", "FADED", "DIFFERENT_FROM_IMAGE"],
  MATERIAL: ["FABRIC_DIFFERENT", "FABRIC_UNCOMFORTABLE", "FABRIC_THICKNESS"],
  PRODUCT_MISMATCH: ["WRONG_PRODUCT", "DIFFERENT_PRODUCT"],
  DAMAGED: ["PRODUCT_DAMAGED"], DELIVERY: ["DELIVERY_RELATED"], OTHER: ["OTHER", "LOW_CONFIDENCE"],
};
const savedApi = localStorage.getItem("dhaga_api_url");
if (savedApi) $("api-url").value = savedApi;
const base = () => $("api-url").value.trim().replace(/\/$/, "");
function notice(message, good = false) { const n = $("notice"); n.textContent = message; n.className = `notice${good ? " success" : ""}`; n.hidden = false; }
function clearNotice() { $("notice").hidden = true; }
async function request(path, options = {}) {
  const response = await fetch(`${base()}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}
function pct(ratio) { return `${(Number(ratio || 0) * 100).toFixed(1)}%`; }
async function refreshDashboard() {
  clearNotice();
  const [summary, insights, categoryInsights] = await Promise.all([
    request("/api/dashboard/summary"), request("/api/dashboard/sku-insights?limit=20"),
    request("/api/dashboard/category-insights?limit=20"),
  ]);
  $("total-returns").textContent = summary.total_returns;
  $("other-share").textContent = pct(summary.other_return_share);
  $("other-count").textContent = `${summary.other_returns} returns`;
  $("analysed").textContent = `${summary.analysed_returns} / ${summary.total_returns}`;
  $("pending-count").textContent = summary.pending_human_reviews;
  $("sku-rows").replaceChildren();
  if (!insights.length) { $("sku-rows").innerHTML = '<tr><td colspan="6" class="muted">No insight rows yet. Run the insight calculation after classification.</td></tr>'; }
  for (const row of insights) {
    const tr = document.createElement("tr");
    [row.sku_id, row.analysis_period, row.total_orders, row.total_returns, pct(row.return_rate), row.top_issue || "—"].forEach((value) => {
      const td = document.createElement("td"); td.textContent = value ?? "—"; tr.append(td);
    });
    $("sku-rows").append(tr);
  }
  $("category-rows").replaceChildren();
  if (!categoryInsights.length) { $("category-rows").innerHTML = '<tr><td colspan="7" class="muted">No category insight rows yet.</td></tr>'; }
  for (const row of categoryInsights) {
    const tr = document.createElement("tr");
    [row.category, row.subcategory, row.analysis_period, row.total_orders, row.total_returns, pct(row.return_rate), row.top_fit_issue || "—"].forEach((value) => {
      const td = document.createElement("td"); td.textContent = value ?? "—"; tr.append(td);
    });
    $("category-rows").append(tr);
  }
  await loadReviews();
  $("connection-state").textContent = `Connected · ${base()}`;
}
async function loadReviews() {
  const rows = await request("/api/reviews/pending");
  const queue = $("review-queue"); queue.replaceChildren();
  if (!rows.length) { const p = document.createElement("p"); p.className = "muted"; p.textContent = "No returns are waiting for review."; queue.append(p); return; }
  for (const row of rows) {
    const card = document.createElement("article"); card.className = "review-card";
    const top = document.createElement("div"); top.className = "review-meta";
    const title = document.createElement("strong"); title.textContent = `${row.return_id} · ${row.sku_id}`;
    const badge = document.createElement("span"); badge.className = "badge"; badge.textContent = `${row.predicted_category}/${row.predicted_subcategory} · ${Math.round(Number(row.confidence_score) * 100)}%`;
    top.append(title, badge); card.append(top);
    const comment = document.createElement("p"); comment.className = "review-comment"; comment.textContent = `Reason: ${row.return_reason}${row.return_reason_text ? ` · “${row.return_reason_text}”` : ""}`; card.append(comment);
    const controls = document.createElement("form"); controls.className = "review-controls";
    const reviewer = document.createElement("label"); reviewer.textContent = "Reviewer";
    const reviewerInput = document.createElement("input"); reviewerInput.placeholder = "Name or ID"; reviewerInput.required = true; reviewer.append(reviewerInput);
    const categoryLabel = document.createElement("label"); categoryLabel.textContent = "Correct category";
    const categorySelect = document.createElement("select"); categorySelect.setAttribute("aria-label", "Correct category");
    Object.keys(categories).forEach((cat) => { const option = new Option(cat, cat); categorySelect.add(option); }); categoryLabel.append(categorySelect);
    const subLabel = document.createElement("label"); subLabel.textContent = "Issue";
    const subSelect = document.createElement("select"); subSelect.setAttribute("aria-label", "Issue"); subLabel.append(subSelect);
    const syncSub = () => { subSelect.replaceChildren(...categories[categorySelect.value].map((sub) => new Option(sub, sub))); };
    categorySelect.addEventListener("change", syncSub); syncSub();
    const submit = document.createElement("button"); submit.textContent = "Save review";
    controls.append(reviewer, categoryLabel, subLabel, submit);
    controls.addEventListener("submit", async (event) => {
      event.preventDefault(); submit.disabled = true;
      try {
        await request(`/api/reviews/${row.analysis_id}`, { method: "POST", body: JSON.stringify({ category: categorySelect.value, subcategory: subSelect.value, reviewer_id: reviewerInput.value }) });
        notice(`Review saved for ${row.return_id}.`, true); await refreshDashboard();
      } catch (error) { notice(error.message); submit.disabled = false; }
    });
    card.append(controls); queue.append(card);
  }
}
$("connect").addEventListener("click", async () => { localStorage.setItem("dhaga_api_url", base()); try { await refreshDashboard(); } catch (error) { $("connection-state").textContent = "Connection failed"; notice(error.message); } });
$("refresh").addEventListener("click", async () => { try { await refreshDashboard(); } catch (error) { notice(error.message); } });
$("classify-form").addEventListener("submit", async (event) => {
  event.preventDefault(); clearNotice();
  const button = event.submitter; button.disabled = true; button.textContent = "Classifying…";
  try {
    const result = await request(`/api/returns/${encodeURIComponent($("return-id").value.trim())}/classify`, { method: "POST" });
    const box = $("classification-result"); box.hidden = false;
    box.textContent = `${result.return_id}: ${result.predicted_category}/${result.predicted_subcategory} · ${Math.round(result.confidence_score * 100)}% confidence · ${result.human_review_status === "PENDING" ? "sent to human review" : "no review needed"}${result.already_classified ? " · showing saved result" : ""}`;
    await refreshDashboard();
  } catch (error) { notice(error.message); }
  finally { button.disabled = false; button.textContent = "Classify"; }
});
