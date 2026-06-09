// ============================================================
// CUSTOMER TIER AUTOMATION — Google Apps Script
// Portfolio-safe version
// ============================================================
// Purpose:
//   Automate customer tier recommendations based on last-12-month revenue
//   and order frequency.
//
// Privacy note:
//   No proprietary company names, credentials, document IDs or private URLs
//   are included.
// ============================================================

const CONFIG = {
  ordersSheet: "Orders",
  resultSheet: "Results",
  configSheet: "Config",
  summarySheet: "Summary",
  cutoffDateCell: "B2",

  customerCol: "customer_id",
  tierCol: "current_tier",
  dateCol: "order_date",
  orderCol: "order_id",
  totalCol: "total_revenue",

  tierRules: [
    { tier: "Diamond", minRevenue: 7900 },
    { tier: "Platinum", minRevenue: 3450 },
    { tier: "Gold", minRevenue: 2000 },
    { tier: "Silver", minRevenue: 0 },
  ],

  tierOrder: ["Silver", "Gold", "Platinum", "Diamond"],
  minOrders: 3,
};

function analyzeCustomerTiers() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const cutoffDate = readCutoffDate_(ss);
  if (!cutoffDate) return;

  const startDate = new Date(cutoffDate);
  startDate.setFullYear(startDate.getFullYear() - 1);

  const orders = readOrders_(ss);
  if (!orders) return;

  const currentTier = getLatestTierByCustomer_(orders);
  const orders12m = orders.filter(o => o.date > startDate && o.date <= cutoffDate);
  const customerSummary = groupByCustomer_(orders12m, currentTier);
  const results = applyTierRules_(customerSummary);

  writeResults_(ss, results);
  writeSummary_(ss, results);

  SpreadsheetApp.getUi().alert(
    "Analysis completed\n\n" +
    "Customers analysed: " + results.length.toLocaleString() + "\n" +
    "Tier upgrades: " + results.filter(r => r.status === "Upgrade").length.toLocaleString() + "\n" +
    "Blocked by minimum orders: " + results.filter(r => r.status === "Blocked: low order frequency").length.toLocaleString()
  );
}

function readCutoffDate_(ss) {
  const sheet = ss.getSheetByName(CONFIG.configSheet);
  if (!sheet) {
    SpreadsheetApp.getUi().alert("Config sheet not found.");
    return null;
  }

  const value = sheet.getRange(CONFIG.cutoffDateCell).getValue();
  const date = new Date(value);
  if (!value || isNaN(date)) {
    SpreadsheetApp.getUi().alert("Enter a valid cutoff date in Config!" + CONFIG.cutoffDateCell);
    return null;
  }
  date.setHours(23, 59, 59, 0);
  return date;
}

function readOrders_(ss) {
  const sheet = ss.getSheetByName(CONFIG.ordersSheet);
  if (!sheet) {
    SpreadsheetApp.getUi().alert("Orders sheet not found.");
    return null;
  }

  const values = sheet.getDataRange().getValues();
  if (values.length < 2) return [];

  const header = values[0].map(h => String(h).trim());
  const idx = {
    customer: header.indexOf(CONFIG.customerCol),
    tier: header.indexOf(CONFIG.tierCol),
    date: header.indexOf(CONFIG.dateCol),
    order: header.indexOf(CONFIG.orderCol),
    total: header.indexOf(CONFIG.totalCol),
  };

  const missing = Object.keys(idx).filter(k => idx[k] === -1);
  if (missing.length > 0) {
    SpreadsheetApp.getUi().alert("Missing required columns: " + missing.join(", "));
    return null;
  }

  return values.slice(1).map(row => ({
    customer: String(row[idx.customer]).trim(),
    tier: String(row[idx.tier]).trim(),
    date: new Date(row[idx.date]),
    order: String(row[idx.order]).trim(),
    total: Number(row[idx.total]) || 0,
  })).filter(o => o.customer && o.order && !isNaN(o.date));
}

function getLatestTierByCustomer_(orders) {
  const latest = {};
  orders.forEach(o => {
    if (!latest[o.customer] || o.date > latest[o.customer].date) {
      latest[o.customer] = { tier: o.tier, date: o.date };
    }
  });

  const result = {};
  Object.keys(latest).forEach(customer => result[customer] = latest[customer].tier);
  return result;
}

function groupByCustomer_(orders, currentTier) {
  const map = {};
  orders.forEach(o => {
    if (!map[o.customer]) {
      map[o.customer] = {
        customer: o.customer,
        currentTier: currentTier[o.customer] || "Unknown",
        revenue: 0,
        orders: new Set(),
      };
    }
    map[o.customer].revenue += o.total;
    map[o.customer].orders.add(o.order);
  });

  return Object.values(map).map(r => ({
    customer: r.customer,
    currentTier: r.currentTier,
    revenue: r.revenue,
    orderCount: r.orders.size,
  }));
}

function applyTierRules_(summary) {
  return summary.map(row => {
    const recommendedTier = CONFIG.tierRules.find(rule => row.revenue >= rule.minRevenue).tier;
    const blocked = row.orderCount < CONFIG.minOrders;

    let status = "Maintain";
    if (blocked) status = "Blocked: low order frequency";
    else if (tierRank_(recommendedTier) > tierRank_(row.currentTier)) status = "Upgrade";
    else if (tierRank_(recommendedTier) < tierRank_(row.currentTier)) status = "Protected: no downgrade";

    return {
      customer: row.customer,
      currentTier: row.currentTier,
      recommendedTier: recommendedTier,
      revenue: row.revenue,
      orderCount: row.orderCount,
      status: status,
    };
  });
}

function tierRank_(tier) {
  const rank = CONFIG.tierOrder.indexOf(tier);
  return rank === -1 ? -1 : rank;
}

function writeResults_(ss, results) {
  let sheet = ss.getSheetByName(CONFIG.resultSheet);
  if (!sheet) sheet = ss.insertSheet(CONFIG.resultSheet);
  sheet.clearContents();

  const rows = [["customer_id", "current_tier", "recommended_tier", "revenue_12m", "orders_12m", "status"]];
  results.forEach(r => rows.push([r.customer, r.currentTier, r.recommendedTier, r.revenue, r.orderCount, r.status]));
  sheet.getRange(1, 1, rows.length, rows[0].length).setValues(rows);
}

function writeSummary_(ss, results) {
  let sheet = ss.getSheetByName(CONFIG.summarySheet);
  if (!sheet) sheet = ss.insertSheet(CONFIG.summarySheet);
  sheet.clearContents();

  const statusCounts = {};
  results.forEach(r => statusCounts[r.status] = (statusCounts[r.status] || 0) + 1);

  const rows = [["status", "customers"]];
  Object.keys(statusCounts).forEach(status => rows.push([status, statusCounts[status]]));
  sheet.getRange(1, 1, rows.length, rows[0].length).setValues(rows);
}
