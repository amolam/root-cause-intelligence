const $ = (id) => document.getElementById(id);
const categories = {
  FIT: ["TOO_SMALL", "TOO_LARGE", "SIZE_MISMATCH", "LENGTH_ISSUE", "WIDTH_ISSUE", "FIT_UNCOMFORTABLE"],
  QUALITY: ["STITCHING", "FABRIC_QUALITY", "SEAM", "PRINT", "BUTTON", "ZIPPER"],
  COLOUR: ["COLOUR_MISMATCH", "FADED", "DIFFERENT_FROM_IMAGE"],
  MATERIAL: ["FABRIC_DIFFERENT", "FABRIC_UNCOMFORTABLE", "FABRIC_THICKNESS"],
  PRODUCT_MISMATCH: ["WRONG_PRODUCT", "DIFFERENT_PRODUCT"],
  DAMAGED: ["PRODUCT_DAMAGED"], DELIVERY: ["DELIVERY_RELATED"], OTHER: ["OTHER", "LOW_CONFIDENCE"],
};
const base = () => (window.DHAGA_CONFIG?.apiBaseUrl || "").replace(/\/$/, "");
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
  const params = new URLSearchParams();
  if ($("insight-start").value) params.set("start", $("insight-start").value);
  if ($("insight-end").value) params.set("end", $("insight-end").value);
  const [summary, categoryInsights] = await Promise.all([
    request("/api/dashboard/summary"), request(`/api/dashboard/category-insights?${params}`),
  ]);
  $("total-returns").textContent = summary.total_returns;
  $("other-share").textContent = pct(summary.other_return_share);
  $("other-count").textContent = `${summary.other_returns} returns`;
  $("analysed").textContent = `${summary.analysed_returns} / ${summary.total_returns}`;
  $("classification-note").textContent = `${summary.unanalysed_returns} not classified`;
  $("pending-count").textContent = summary.pending_human_reviews;
  renderCategoryInsights(categoryInsights);
  await loadReviews(summary.unanalysed_returns);
  $("connection-state").textContent = `Connected · ${new URL(base()).host}`;
}
function renderCategoryInsights(rows) {
  const body = $("category-rows"); body.replaceChildren();
  if (!rows.length) { body.innerHTML = '<tr><td colspan="8" class="muted">No insight rows match this date range. Run the insight calculation for the selected period.</td></tr>'; return; }
  rows.forEach((row, index) => {
    const summary = document.createElement("tr");
    [row.category, row.subcategory, row.total_orders, row.total_returns, pct(row.return_rate), pct(row.fit_return_rate), pct(row.quality_return_rate)].forEach((value) => {
      const cell = document.createElement("td"); cell.textContent = value ?? "—"; summary.append(cell);
    });
    if (row.small_sample) { const note = document.createElement("small"); note.className = "sample-warning"; note.textContent = "Small sample"; summary.children[2].append(note); }
    const related = document.createElement("td");
    const toggle = document.createElement("button"); toggle.className = "button-secondary"; toggle.textContent = `${row.skus.length} SKUs`; toggle.setAttribute("aria-expanded", "false");
    related.append(toggle); summary.append(related); body.append(summary);

    const detail = document.createElement("tr"); detail.hidden = true;
    const detailCell = document.createElement("td"); detailCell.colSpan = 8;
    if (!row.skus.length) { detailCell.textContent = "No returns for these SKUs in the selected range."; }
    else {
      const table = document.createElement("table"); table.className = "sku-detail-table";
      const head = document.createElement("thead"); const headRow = document.createElement("tr");
      ["SKU", "Product", "Orders", "Returns", "Return rate", "FIT", "QUALITY", "COLOUR", "OTHER", "Sample"].forEach((label) => { const th = document.createElement("th"); th.textContent = label; headRow.append(th); });
      head.append(headRow); table.append(head);
      const skuBody = document.createElement("tbody");
      row.skus.forEach((sku) => {
        const line = document.createElement("tr");
        [sku.sku_id, sku.product_name, sku.total_orders, sku.total_returns, pct(sku.return_rate), sku.fit_returns, sku.quality_count, sku.colour_count, sku.other_count, sku.small_sample ? "Low denominator" : "—"].forEach((value) => { const cell = document.createElement("td"); cell.textContent = value ?? "—"; line.append(cell); });
        skuBody.append(line);
      });
      table.append(skuBody); detailCell.append(table);
    }
    detail.append(detailCell); body.append(detail);
    toggle.addEventListener("click", () => { detail.hidden = !detail.hidden; toggle.setAttribute("aria-expanded", String(!detail.hidden)); toggle.textContent = detail.hidden ? `${row.skus.length} SKUs` : "Hide SKUs"; });
  });
}
async function loadReviews(unanalysedReturns = 0) {
  const rows = await request("/api/reviews/pending");
  const queue = $("review-queue"); queue.replaceChildren();
  if (!rows.length) { const p = document.createElement("p"); p.className = "muted"; p.textContent = unanalysedReturns ? `No returns are waiting for review. ${unanalysedReturns} returns have not been classified yet.` : "All returns are classified; none are waiting for review."; queue.append(p); return; }
  for (const row of rows) {
    const card = document.createElement("article"); card.className = "review-card";
    const top = document.createElement("div"); top.className = "review-meta";
    const title = document.createElement("strong"); title.textContent = `${row.return_id} · ${row.sku_id}`;
    const badge = document.createElement("span"); badge.className = "badge"; badge.textContent = `${row.predicted_category}/${row.predicted_subcategory} · ${Math.round(Number(row.confidence_score) * 100)}%`;
    top.append(title, badge); card.append(top);
    const reasons = row.review_reasons || [];
    const rationale = document.createElement("p"); rationale.className = "muted review-rationale";
    rationale.textContent = [
      reasons.includes("LOW_CONFIDENCE") ? "Below the 75% review threshold." : "",
      reasons.includes("OTHER_CATEGORY") ? "OTHER always requires human review, even at high confidence; the score describes confidence in this label, not whether review is complete." : "",
    ].filter(Boolean).join(" ");
    if (rationale.textContent) card.append(rationale);
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
$("refresh").addEventListener("click", async () => { try { await refreshDashboard(); } catch (error) { notice(error.message); } });
$("insight-range-form").addEventListener("submit", async (event) => { event.preventDefault(); try { await refreshDashboard(); } catch (error) { notice(error.message); } });
$("refresh-insights").addEventListener("click", async (event) => {
  const button = event.currentTarget; button.disabled = true; button.textContent = "Recalculating…";
  try {
    const result = await request("/api/dashboard/refresh-insights", { method: "POST" });
    await refreshDashboard();
    notice(`Insights recalculated: ${result.sku_rows} SKU rows and ${result.category_rows} category rows. Classifications were unchanged.`, true);
  } catch (error) { notice(error.message); }
  finally { button.disabled = false; button.textContent = "Recalculate insights"; }
});
$("reset-classifications").addEventListener("click", () => {
  $("reset-dialog").showModal();
});
$("cancel-reset").addEventListener("click", () => $("reset-dialog").close());
$("reset-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("confirm-reset");
  button.disabled = true; button.textContent = "Resetting…";
  let shouldRefresh = false;
  try {
    const result = await request("/api/admin/reset-classifications", { method: "POST" });
    notice(`Reset complete: ${result.analyses_deleted} analyses and ${result.human_reviews_deleted} reviews removed; insights refreshed.`, true);
    shouldRefresh = true;
  } catch (error) { notice(error.message); }
  finally {
    button.disabled = false; button.textContent = "Reset classifications";
    $("reset-dialog").close();
  }
  if (shouldRefresh) refreshDashboard().catch((error) => notice(`Reset completed, but dashboard refresh failed: ${error.message}`));
});
$("classify-batch").addEventListener("click", async (event) => {
  const button = event.currentTarget; button.disabled = true; button.textContent = "Classifying…";
  let shouldRefresh = false;
  try {
    const result = await request("/api/returns/classify-batch?limit=5", { method: "POST" });
    const failureNote = result.failures.length ? ` ${result.failures.length} failed: ${result.failures.map((failure) => failure.return_id).join(", ")}.` : "";
    const insightNote = result.insights_refreshed ? " Monthly insights updated." : ` Insight refresh failed for ${result.insight_refresh_failures.length} item(s); rerun the insight calculation.`;
    notice(`Batch finished: ${result.classified} classified, ${result.pending_review} sent to review, ${result.not_required} resolved, ${result.failed} failed. ${result.remaining_unclassified} remain unclassified.${failureNote}${insightNote}`, result.failed === 0 && result.insights_refreshed);
    shouldRefresh = true;
  } catch (error) { notice(error.message); }
  finally { button.disabled = false; button.textContent = "Classify next 5"; }
  if (shouldRefresh) refreshDashboard().catch((error) => notice(`Classification finished, but dashboard refresh failed: ${error.message}`));
});
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
if (base()) {
  refreshDashboard().catch((error) => { $("connection-state").textContent = "Connection failed"; notice(error.message); });
} else {
  $("connection-state").textContent = "API_BASE_URL is not configured";
}
