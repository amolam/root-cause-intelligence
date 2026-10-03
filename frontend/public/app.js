const $ = (id) => document.getElementById(id);
const categories = {
  FIT: ["TOO_SMALL", "TOO_LARGE", "SIZE_MISMATCH", "LENGTH_ISSUE", "WIDTH_ISSUE", "FIT_UNCOMFORTABLE"],
  QUALITY: ["STITCHING", "FABRIC_QUALITY", "SEAM", "PRINT", "BUTTON", "ZIPPER"],
  COLOUR: ["COLOUR_MISMATCH", "FADED", "DIFFERENT_FROM_IMAGE"],
  MATERIAL: ["FABRIC_DIFFERENT", "FABRIC_UNCOMFORTABLE", "FABRIC_THICKNESS"],
  PRODUCT_MISMATCH: ["WRONG_PRODUCT", "DIFFERENT_PRODUCT"],
  DAMAGED: ["PRODUCT_DAMAGED"], DELIVERY: ["DELIVERY_RELATED"],
  CUSTOMER_PREFERENCE: ["CHANGED_MIND"], OTHER: ["OTHER", "LOW_CONFIDENCE"],
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
  const [summary, analytics] = await Promise.all([
    request("/api/dashboard/summary"), request("/api/dashboard/analytics?limit=10"),
  ]);
  $("total-returns").textContent = summary.total_returns;
  $("other-share").textContent = pct(summary.other_return_share);
  $("other-count").textContent = `${summary.other_returns} returns`;
  $("analysed").textContent = `${summary.analysed_returns} / ${summary.total_returns}`;
  $("classification-note").textContent = `${summary.unanalysed_returns} not classified`;
  $("human-reviewed-count").textContent = summary.human_reviewed_returns;
  $("pending-count").textContent = summary.pending_human_reviews;
  renderAnalytics(analytics);
  await loadReviews(summary.unanalysed_returns);
  $("connection-state").textContent = `Connected · ${new URL(base()).host}`;
}
function renderBars(containerId, rows, { label, detail, value, amount, emptyText, rate = false }) {
  const container = $(containerId); container.replaceChildren();
  if (!rows.length) {
    const empty = document.createElement("p"); empty.className = "muted"; empty.textContent = emptyText;
    container.append(empty); return;
  }
  const max = Math.max(...rows.map(amount), 0.0001);
  const list = document.createElement("ol"); list.className = `analytics-bar-list${rate ? " rate-bars" : ""}`;
  rows.forEach((row) => {
    const item = document.createElement("li"); item.className = "analytics-bar-row";
    const header = document.createElement("div"); header.className = "analytics-bar-heading";
    const title = document.createElement("strong"); title.textContent = label(row);
    const metric = document.createElement("span"); metric.textContent = value(row);
    header.append(title, metric);
    const caption = document.createElement("p"); caption.className = "analytics-bar-detail"; caption.textContent = detail(row);
    const track = document.createElement("div"); track.className = "analytics-bar-track";
    track.setAttribute("role", "img"); track.setAttribute("aria-label", `${label(row)}: ${value(row)}`);
    const fill = document.createElement("div"); fill.className = "analytics-bar-fill";
    fill.style.width = `${Math.max(1, Math.min(100, (amount(row) / max) * 100))}%`;
    track.append(fill); item.append(header, caption, track); list.append(item);
  });
  container.append(list);
}
const chartColors = ["#34715d", "#c07d3d", "#d45d4f", "#6e8ca0", "#c3a348", "#9b7160", "#779476", "#667184", "#bd7181"];
function renderPie(chartId, legendId, rows, { label, countLabel, title, emptyText = "No classified returns for this cohort." }) {
  const chart = $(chartId); const legend = $(legendId);
  chart.replaceChildren(); legend.replaceChildren();
  const total = rows.reduce((sum, row) => sum + row.return_count, 0);
  if (!rows.length || !total) {
    const empty = document.createElement("p"); empty.className = "muted"; empty.textContent = emptyText;
    legend.append(empty); chart.style.background = "#ece7dd"; chart.setAttribute("aria-label", `${title}: no classified returns`); return;
  }
  let position = 0;
  const segments = rows.map((row, index) => {
    const start = position;
    position += row.share * 100;
    return `${chartColors[index % chartColors.length]} ${start}% ${position}%`;
  });
  chart.style.background = `conic-gradient(${segments.join(", ")})`;
  chart.setAttribute("aria-label", `${title}: ${rows.map((row) => `${label(row)} ${pct(row.share)}`).join(", ")}`);
  const list = document.createElement("ul"); list.className = "pie-legend-list";
  rows.forEach((row, index) => {
    const item = document.createElement("li");
    const swatch = document.createElement("span"); swatch.className = "pie-swatch"; swatch.style.backgroundColor = chartColors[index % chartColors.length];
    const name = document.createElement("span"); name.className = "pie-legend-name"; name.textContent = label(row);
    const amount = document.createElement("strong"); amount.textContent = `${countLabel(row)} · ${pct(row.share)}`;
    item.append(swatch, name, amount); list.append(item);
  });
  legend.append(list);
}
function renderAnalytics(data) {
  const other = data.source_other;
  const summary = $("other-summary"); summary.replaceChildren();
  [
    ["Source “Other” returns", other.total_returns],
  ["AI-resolved", other.ai_classified_returns],
  ["Sent for human review", other.sent_for_human_review],
  ["AI unclassified", other.ai_unclassified_returns],
  ["AI coverage, not sent to review", pct(other.ai_prediction_coverage)],
  ].forEach(([label, value]) => {
    const stat = document.createElement("div"); stat.className = "analytics-stat";
    const name = document.createElement("span"); name.textContent = label;
    const metric = document.createElement("strong"); metric.textContent = value;
    stat.append(name, metric); summary.append(stat);
  });
  renderPie("other-pie", "other-pie-legend", other.category_mix, {
    label: (row) => row.category,
    countLabel: (row) => `${row.return_count} returns`,
    title: "AI category mix for source Other returns",
  });
  renderBars("other-chart", other.breakdown, {
    label: (row) => `${row.category} / ${row.subcategory}`,
    detail: (row) => `${row.return_count} AI-resolved returns · ${pct(row.share)} of AI-classified source “Other”`,
    value: (row) => pct(row.share),
    amount: (row) => row.share,
    emptyText: "No source-“Other” returns were AI-categorized without human review in this cohort.",
  });

  const vendorRates = data.vendors.by_rate;
  const totalVendorReturnedUnits = data.vendors.total_returned_units;
  const vendorPieCaption = $("vendor-rate-pie-caption");
  const listedVendorReturnedUnits = vendorRates.reduce((sum, vendor) => sum + vendor.returned_units, 0);
  const otherVendorReturnedUnits = totalVendorReturnedUnits - listedVendorReturnedUnits;
  const validVendorPie = totalVendorReturnedUnits > 0 && otherVendorReturnedUnits >= 0;
  const vendorPieRows = validVendorPie ? vendorRates.map((vendor) => ({
    label: vendor.vendor_name,
    return_count: vendor.returned_units,
    share: vendor.returned_units / totalVendorReturnedUnits,
  })) : [];
  if (validVendorPie && (otherVendorReturnedUnits > 0 || !vendorPieRows.length)) {
    vendorPieRows.push({
      label: "Others",
      return_count: otherVendorReturnedUnits,
      share: otherVendorReturnedUnits / totalVendorReturnedUnits,
    });
  }
  vendorPieCaption.textContent = totalVendorReturnedUnits > 0
    ? `${totalVendorReturnedUnits} returned units across all vendors; vendors outside the rate-comparison list are grouped as Others.`
    : "No returned units across vendors in this cohort.";
  renderPie("vendor-rate-pie", "vendor-rate-legend", vendorPieRows, {
    label: (row) => row.label,
    countLabel: (row) => `${row.return_count} returned ${row.return_count === 1 ? "unit" : "units"}`,
    title: "Returned-unit share across all vendors",
    emptyText: otherVendorReturnedUnits < 0 ? "The rate-comparison vendors exceed the all-vendor return total." : "No returned units across vendors in this cohort.",
  });
  renderBars("vendor-rate-chart", vendorRates, {
    label: (row) => row.vendor_name,
    detail: (row) => `${row.returned_units} returned / ${row.sold_units} sold units · ${row.return_events} return events`,
    value: (row) => pct(row.unit_return_rate),
    amount: (row) => row.unit_return_rate,
    emptyText: "No vendors meet the 30 sold-unit minimum in this cohort.",
    rate: true,
  });
  $("vendor-data-quality").textContent = `${data.data_quality.return_order_item_sku_mismatches} returns reference a different SKU than the purchased order item; vendor attribution follows the purchased item.`;

  renderPie("sku-issue-pie", "sku-issue-legend", data.ai_issue_category_mix, {
    label: (row) => row.category,
    countLabel: (row) => `${row.return_count} returns`,
    title: "AI issue category mix across classified returns",
  });
  renderBars("sku-chart", data.skus, {
    label: (row) => `${row.sku_id} · ${row.product_name}`,
    detail: (row) => {
      const issues = row.issue_breakdown.slice(0, 3).map((issue) => `${issue.category}/${issue.subcategory} ${issue.return_count}`).join(" · ");
      const quality = row.unclassified_returns ? ` · ${row.unclassified_returns} unclassified` : "";
      return `${issues || "No classified issue labels"} · ${pct(row.return_rate)} of ${row.sold_orders} selling orders${row.small_sample ? " · low volume" : ""}${quality}`;
    },
    value: (row) => `${row.return_events} returns`,
    amount: (row) => row.return_events,
    emptyText: "No SKU returns for this cohort.",
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
$("pending-count").addEventListener("click", (event) => {
  event.preventDefault();
  const panel = $("review-queue-panel");
  panel.hidden = false;
  $("review-queue-heading").focus();
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
});
$("close-review-queue").addEventListener("click", () => {
  $("review-queue-panel").hidden = true;
  $("analytics-heading").scrollIntoView({ behavior: "smooth", block: "start" });
  $("analytics-heading").focus();
});
$("classify-batch").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const sizeSelect = $("classify-batch-size");
  const target = Number(sizeSelect.value);
  const totals = { classified: 0, pending_review: 0, not_required: 0, failed: 0 };
  const failures = [];
  const insightRefreshFailures = [];
  let attempted = 0;
  let remaining = null;
  let insightsRefreshed = true;
  button.disabled = true;
  sizeSelect.disabled = true;
  try {
    while (attempted < target) {
      const limit = Math.min(5, target - attempted);
      button.textContent = `Classifying ${Math.min(attempted + limit, target)} / ${target}…`;
      const result = await request(`/api/returns/classify-batch?limit=${limit}`, { method: "POST" });
      attempted += result.attempted;
      remaining = result.remaining_unclassified;
      totals.classified += result.classified;
      totals.pending_review += result.pending_review;
      totals.not_required += result.not_required;
      totals.failed += result.failed;
      failures.push(...result.failures);
      insightRefreshFailures.push(...result.insight_refresh_failures);
      insightsRefreshed = insightsRefreshed && result.insights_refreshed;

      if (result.failed > 0 || result.attempted < limit || result.remaining_unclassified === 0) break;
    }
    const failureNote = failures.length ? ` Failed returns: ${failures.map((failure) => failure.return_id).join(", ")}.` : "";
    const insightNote = insightsRefreshed ? " Monthly insights updated." : ` Insight refresh failed for ${insightRefreshFailures.length} item(s); rerun the insight calculation.`;
    notice(`Batch finished: ${totals.classified} classified from ${attempted} attempted, ${totals.pending_review} sent to review, ${totals.not_required} resolved, ${totals.failed} failed. ${remaining ?? "Unknown"} remain unclassified.${failureNote}${insightNote}`, totals.failed === 0 && insightsRefreshed);
  } catch (error) {
    notice(`Classification stopped after ${attempted} of ${target} attempted: ${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "Classify returns";
    sizeSelect.disabled = false;
  }
  if (attempted > 0) refreshDashboard().catch((error) => notice(`Classification finished, but dashboard refresh failed: ${error.message}`));
});
const analyticsTabs = [...document.querySelectorAll(".analytics-tab")];
function activateAnalyticsTab(selected, focus = false) {
  analyticsTabs.forEach((tab) => {
    const active = tab === selected;
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
    $(tab.getAttribute("aria-controls")).hidden = !active;
  });
  if (focus) selected.focus();
}
analyticsTabs.forEach((tab, index) => {
  tab.addEventListener("click", () => activateAnalyticsTab(tab));
  tab.addEventListener("keydown", (event) => {
    const nextIndex = event.key === "ArrowRight" ? (index + 1) % analyticsTabs.length
      : event.key === "ArrowLeft" ? (index - 1 + analyticsTabs.length) % analyticsTabs.length
        : event.key === "Home" ? 0 : event.key === "End" ? analyticsTabs.length - 1 : -1;
    if (nextIndex >= 0) { event.preventDefault(); activateAnalyticsTab(analyticsTabs[nextIndex], true); }
  });
});
if (base()) {
  refreshDashboard().catch((error) => { $("connection-state").textContent = "Connection failed"; notice(error.message); });
} else {
  $("connection-state").textContent = "API_BASE_URL is not configured";
}
