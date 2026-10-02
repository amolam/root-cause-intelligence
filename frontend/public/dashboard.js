// Dashboard Module
import { request, $ } from "./api.js";
import { pct, showToast } from "./ui.js";
import { loadReviews } from "./reviews.js";

export async function refreshDashboard() {
  try {
    const [summary, insights, categoryInsights] = await Promise.all([
      request("/api/dashboard/summary"),
      request("/api/dashboard/sku-insights?limit=20"),
      request("/api/dashboard/category-insights?limit=20"),
    ]);

    // Update Summary metrics with animation / removal of skeletons
    const totalEl = $('total-returns');
    if (totalEl) {
      totalEl.textContent = summary.total_returns ?? 0;
      totalEl.classList.remove("skeleton");
    }

    const otherShareEl = $('other-share');
    if (otherShareEl) {
      otherShareEl.textContent = pct(summary.other_return_share);
      otherShareEl.classList.remove("skeleton");
    }

    const otherCountEl = $('other-count');
    if (otherCountEl) {
      otherCountEl.textContent = `${summary.other_returns ?? 0} returns`;
    }

    const analysedEl = $('analysed');
    if (analysedEl) {
      analysedEl.textContent = `${summary.analysed_returns ?? 0} / ${summary.total_returns ?? 0}`;
      analysedEl.classList.remove("skeleton");
    }

    const pendingEl = $('pending-count');
    if (pendingEl) {
      pendingEl.textContent = summary.pending_human_reviews ?? 0;
      pendingEl.classList.remove("skeleton");
    }

    // SKU Table
    const skuRows = $('sku-rows');
    if (skuRows) {
      skuRows.replaceChildren();
      if (!insights || !insights.length) {
        skuRows.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No insight rows yet. Run the insight calculation after classification.</td></tr>';
      } else {
        for (const row of insights) {
          const tr = document.createElement("tr");
          [row.sku_id, row.analysis_period, row.total_orders, row.total_returns, pct(row.return_rate), row.top_issue || "—"].forEach((value, idx) => {
            const td = document.createElement("td");
            td.textContent = value ?? "—";
            if ([2, 3, 4].includes(idx)) td.className = "text-right";
            tr.append(td);
          });
          skuRows.append(tr);
        }
      }
    }

    // Category Table
    const categoryRows = $('category-rows');
    if (categoryRows) {
      categoryRows.replaceChildren();
      if (!categoryInsights || !categoryInsights.length) {
        categoryRows.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No category insight rows yet.</td></tr>';
      } else {
        for (const row of categoryInsights) {
          const tr = document.createElement("tr");
          [row.category, row.subcategory, row.analysis_period, row.total_orders, row.total_returns, pct(row.return_rate), row.top_fit_issue || "—"].forEach((value, idx) => {
            const td = document.createElement("td");
            td.textContent = value ?? "—";
            if ([3, 4, 5].includes(idx)) td.className = "text-right";
            tr.append(td);
          });
          categoryRows.append(tr);
        }
      }
    }

    await loadReviews();
  } catch (error) {
    showToast(error.message, "error");
    throw error;
  }
}

export function initDashboard() {
  const refreshBtn = $('refresh');
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      refreshBtn.disabled = true;
      refreshBtn.textContent = "Refreshing...";
      try {
        await refreshDashboard();
        showToast("Dashboard refreshed successfully.", "success");
      } catch (error) {
        // Error already toasted
      } finally {
        refreshBtn.disabled = false;
        refreshBtn.textContent = "Refresh";
      }
    });
  }
}
