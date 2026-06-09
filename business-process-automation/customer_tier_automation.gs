// ============================================================
//  CUSTOMER TIER AUTOMATION — Google Apps Script
//  Portfolio-safe version
//  Version 1.0
// ============================================================
//
//  Purpose
//  -------
//  This script automates customer tier analysis in Google Sheets.
//  It evaluates customer revenue and order frequency over the last
//  12 months and assigns a recommended commercial tier.
//
//  It also generates:
//  - Results sheet
//  - Top Customers sheet
//  - Summary sheet
//  - Configuration sheet
//  - User instructions and legend modals
//
//  All company-specific names, internal terms and private business
//  labels have been replaced with generic portfolio-safe terminology.
//
// ============================================================


// ------------------------------------------------------------
// Configuration
// ------------------------------------------------------------
const CONFIG = {
  ordersSheet: "Orders",
  resultSheet: "Results",
  configSheet: "Config",
  topCustomersSheet: "Top Customers",
  summarySheet: "Summary",
  excludedCustomersSheet: "Excluded Customers",
  specialTiersSheet: "Special Tiers",
  cutoffDateCell: "B2",

  customerIdColumn: "CUSTOMER_ID",
  currentTierColumn: "CURRENT_TIER",
  orderDateColumn: "order_date",
  orderIdColumn: "order_id",
  orderTotalColumn: "Total",

  tierRules: [
    { tier: "Tier 4", minRevenue: 7900 },
    { tier: "Tier 3", minRevenue: 3450 },
    { tier: "Tier 2", minRevenue: 2000 },
    { tier: "Tier 1", minRevenue: 0 },
  ],

  tierOrder: ["Tier 1", "Tier 2", "Tier 3", "Tier 4"],
  minimumOrdersToUpgrade: 3,
};


// ============================================================
// Main entry point
// ============================================================
function analyseCustomerTiers() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();

  const cutoffDate = readCutoffDate(spreadsheet);
  if (!cutoffDate) return;

  const startDate = new Date(cutoffDate);
  startDate.setFullYear(startDate.getFullYear() - 1);

  const orders = readOrders(spreadsheet);
  if (!orders) return;

  const excludedCustomers = readExcludedCustomers(spreadsheet);
  const specialTiers = readSpecialTiers(spreadsheet);
  const currentTierByCustomer = calculateCurrentTier(orders);

  const ordersLast12Months = orders.filter(order =>
    order.date > startDate && order.date <= cutoffDate
  );

  const customerSummary = groupByCustomer(ordersLast12Months, currentTierByCustomer);
  const results = applyTierRules(customerSummary, excludedCustomers);

  writeResults(spreadsheet, results);
  writeTopCustomers(spreadsheet, results, specialTiers);
  writeSummary(spreadsheet, results);

  const upgrades = results.filter(row => row.reason === "Upgrade").length;
  const blockedByOrders = results.filter(row => row.reason === "Blocked: fewer than minimum orders").length;
  const protectedDowngrades = results.filter(row => row.reason === "Protected: no downgrade").length;
  const excluded = results.filter(row => row.reason === "Excluded: no upgrade").length;
  const topCustomers = results.filter(row =>
    !row.isExcluded &&
    row.revenue >= 3450 &&
    row.orders >= CONFIG.minimumOrdersToUpgrade
  ).length;

  SpreadsheetApp.getUi().alert(
    "Analysis completed\n\n" +
    "Customers analysed: " + results.length.toLocaleString() + "\n" +
    "Confirmed upgrades: " + upgrades.toLocaleString() + "\n" +
    "Blocked by order count: " + blockedByOrders.toLocaleString() + "\n" +
    "Protected from downgrade: " + protectedDowngrades.toLocaleString() + "\n" +
    "Excluded customers: " + excluded.toLocaleString() + "\n" +
    "Top customers: " + topCustomers.toLocaleString()
  );
}


// ============================================================
// Read cutoff date
// ============================================================
function readCutoffDate(spreadsheet) {
  let sheet = spreadsheet.getSheetByName(CONFIG.configSheet);
  if (!sheet) sheet = createConfigSheet(spreadsheet);

  const value = sheet.getRange(CONFIG.cutoffDateCell).getValue();

  if (!value) {
    SpreadsheetApp.getUi().alert(
      "Please enter a cutoff date in the Config sheet, cell B2."
    );
    return null;
  }

  const date = new Date(value);
  if (isNaN(date)) {
    SpreadsheetApp.getUi().alert(
      "The cutoff date in B2 is not valid. Please use a valid date format."
    );
    return null;
  }

  date.setHours(23, 59, 59, 0);
  return date;
}


// ============================================================
// Read orders
// ============================================================
function readOrders(spreadsheet) {
  const sheet = spreadsheet.getSheetByName(CONFIG.ordersSheet);

  if (!sheet) {
    SpreadsheetApp.getUi().alert(
      "Sheet not found: " + CONFIG.ordersSheet + ". Please create it and paste the order data."
    );
    return null;
  }

  const values = sheet.getDataRange().getValues();

  if (values.length < 2) {
    SpreadsheetApp.getUi().alert("The orders sheet is empty.");
    return null;
  }

  const header = values[0].map(column => String(column).trim());

  const customerIndex = header.indexOf(CONFIG.customerIdColumn);
  const tierIndex = header.indexOf(CONFIG.currentTierColumn);
  const dateIndex = header.indexOf(CONFIG.orderDateColumn);
  const orderIndex = header.indexOf(CONFIG.orderIdColumn);
  const totalIndex = header.indexOf(CONFIG.orderTotalColumn);

  const missingColumns = [
    [customerIndex, CONFIG.customerIdColumn],
    [tierIndex, CONFIG.currentTierColumn],
    [dateIndex, CONFIG.orderDateColumn],
    [orderIndex, CONFIG.orderIdColumn],
    [totalIndex, CONFIG.orderTotalColumn],
  ].filter(([index]) => index === -1).map(([, name]) => name);

  if (missingColumns.length > 0) {
    SpreadsheetApp.getUi().alert(
      "Missing columns: " + missingColumns.join(", ") +
      "\n\nPlease check that the column names match exactly."
    );
    return null;
  }

  const orders = [];

  for (let i = 1; i < values.length; i++) {
    const row = values[i];
    const rawDate = row[dateIndex];
    let date;

    if (rawDate instanceof Date) {
      date = rawDate;
    } else {
      const parts = String(rawDate).split("/");
      date = parts.length === 3
        ? new Date(parts[2], parts[1] - 1, parts[0])
        : new Date(rawDate);
    }

    if (isNaN(date)) continue;

    orders.push({
      customer: String(row[customerIndex]).trim(),
      currentTier: String(row[tierIndex]).trim(),
      date: date,
      orderId: String(row[orderIndex]).trim(),
      total: parseFloat(row[totalIndex]) || 0,
    });
  }

  return orders;
}


// ============================================================
// Read excluded customers
// ============================================================
function readExcludedCustomers(spreadsheet) {
  const sheet = spreadsheet.getSheetByName(CONFIG.excludedCustomersSheet);
  if (!sheet) return new Set();

  const values = sheet.getDataRange().getValues();
  if (values.length < 2) return new Set();

  const excluded = new Set();

  for (let i = 1; i < values.length; i++) {
    const customerId = String(values[i][0]).trim();
    if (customerId) excluded.add(customerId);
  }

  return excluded;
}


// ============================================================
// Read special tiers
// ============================================================
function readSpecialTiers(spreadsheet) {
  const sheet = spreadsheet.getSheetByName(CONFIG.specialTiersSheet);
  if (!sheet) return [];

  const values = sheet.getDataRange().getValues();
  if (values.length < 2) return [];

  const specialTiers = [];

  for (let i = 1; i < values.length; i++) {
    const customerId = String(values[i][0]).trim();
    const tierType = String(values[i][1]).trim();

    if (customerId) {
      specialTiers.push({
        customer: customerId,
        type: tierType,
      });
    }
  }

  return specialTiers;
}


// ============================================================
// Calculations
// ============================================================
function calculateCurrentTier(orders) {
  const latestTier = {};

  orders.forEach(order => {
    if (!latestTier[order.customer] || order.date > latestTier[order.customer].date) {
      latestTier[order.customer] = {
        tier: order.currentTier,
        date: order.date,
      };
    }
  });

  const result = {};
  Object.keys(latestTier).forEach(customer => {
    result[customer] = latestTier[customer].tier;
  });

  return result;
}


function groupByCustomer(ordersLast12Months, currentTierByCustomer) {
  const customerMap = {};

  ordersLast12Months.forEach(order => {
    if (!customerMap[order.customer]) {
      customerMap[order.customer] = {
        customer: order.customer,
        currentTier: currentTierByCustomer[order.customer] || "Tier 1",
        orderSet: new Set(),
        revenue: 0,
      };
    }

    customerMap[order.customer].orderSet.add(order.orderId);
    customerMap[order.customer].revenue += order.total;
  });

  return Object.values(customerMap).map(row => ({
    customer: row.customer,
    currentTier: row.currentTier,
    orders: row.orderSet.size,
    revenue: Math.round(row.revenue * 100) / 100,
  }));
}


function applyTierRules(customerSummary, excludedCustomers) {
  return customerSummary.map(row => {
    const revenueTier = tierByRevenue(row.revenue);
    const currentLevel = tierLevel(row.currentTier);
    const revenueLevel = tierLevel(revenueTier);
    const meetsOrderMinimum = row.orders >= CONFIG.minimumOrdersToUpgrade;
    const isExcluded = excludedCustomers.has(String(row.customer));

    let finalTier;
    let reason;
    let potentialTier = "";

    if (isExcluded) {
      finalTier = row.currentTier;
      reason = revenueLevel > currentLevel
        ? "Excluded: no upgrade"
        : (revenueLevel < currentLevel ? "Protected: no downgrade" : "No change");

    } else if (revenueLevel > currentLevel) {
      if (meetsOrderMinimum) {
        finalTier = revenueTier;
        reason = "Upgrade";
      } else {
        finalTier = row.currentTier;
        reason = "Blocked: fewer than minimum orders";
        potentialTier = revenueTier;
      }

    } else if (revenueLevel < currentLevel) {
      finalTier = row.currentTier;
      reason = "Protected: no downgrade";

    } else {
      finalTier = row.currentTier;
      reason = "No change";
    }

    return {
      ...row,
      finalTier,
      reason,
      potentialTier,
      isExcluded,
    };
  });
}


function tierByRevenue(revenue) {
  for (const rule of CONFIG.tierRules) {
    if (revenue >= rule.minRevenue) return rule.tier;
  }

  return "Tier 1";
}


function tierLevel(tier) {
  const index = CONFIG.tierOrder.indexOf(tier);
  return index === -1 ? 0 : index;
}


// ============================================================
// Write results
// ============================================================
function writeResults(spreadsheet, results) {
  let sheet = spreadsheet.getSheetByName(CONFIG.resultSheet);

  if (sheet) {
    sheet.clearContents();
    sheet.clearFormats();
  } else {
    sheet = spreadsheet.insertSheet(CONFIG.resultSheet);
  }

  const reasonOrder = {
    "Upgrade": 0,
    "Blocked: fewer than minimum orders": 1,
    "Protected: no downgrade": 2,
    "No change": 3,
    "Excluded: no upgrade": 4,
  };

  results.sort((a, b) => {
    const reasonDiff = (reasonOrder[a.reason] || 0) - (reasonOrder[b.reason] || 0);
    return reasonDiff !== 0 ? reasonDiff : b.revenue - a.revenue;
  });

  const headers = [[
    "CUSTOMER_ID",
    "CURRENT_TIER",
    "ORDERS_12M",
    "REVENUE_12M",
    "FINAL_TIER",
    "REASON",
    "POTENTIAL_TIER_IF_MIN_ORDERS",
  ]];

  const rows = results.map(row => [
    row.customer,
    row.currentTier,
    row.orders,
    row.revenue,
    row.finalTier,
    row.reason,
    row.potentialTier || "-",
  ]);

  sheet.getRange(1, 1, 1, 7).setValues(headers).setFontWeight("bold");

  if (rows.length > 0) {
    sheet.getRange(2, 1, rows.length, 7).setValues(rows);
    sheet.getRange(2, 4, rows.length, 1).setNumberFormat('#,##0.00');
    sheet.getRange(2, 3, rows.length, 1).setNumberFormat('#,##0');
  }

  sheet.setFrozenRows(1);
  spreadsheet.setActiveSheet(sheet);
}


// ============================================================
// Write top customers
// ============================================================
function writeTopCustomers(spreadsheet, results, specialTiers) {
  let sheet = spreadsheet.getSheetByName(CONFIG.topCustomersSheet);

  if (sheet) {
    sheet.clearContents();
    sheet.clearFormats();
  } else {
    sheet = spreadsheet.insertSheet(CONFIG.topCustomersSheet);
  }

  const topCustomers = results
    .filter(row =>
      !row.isExcluded &&
      row.revenue >= 3450 &&
      row.orders >= CONFIG.minimumOrdersToUpgrade
    )
    .sort((a, b) => {
      const tierDiff = tierLevel(b.finalTier) - tierLevel(a.finalTier);
      return tierDiff !== 0 ? tierDiff : b.revenue - a.revenue;
    });

  const existingIds = new Set(topCustomers.map(row => String(row.customer)));

  specialTiers.forEach(item => {
    if (!existingIds.has(item.customer)) {
      topCustomers.push({
        customer: item.customer,
        currentTier: item.type,
        orders: "",
        revenue: "",
        finalTier: item.type,
        reason: "Special tier",
      });
    }
  });

  const headers = [[
    "CUSTOMER_ID",
    "CURRENT_TIER",
    "ORDERS_12M",
    "REVENUE_12M",
    "FINAL_TIER",
    "REASON",
  ]];

  sheet.getRange(1, 1, 1, 6).setValues(headers).setFontWeight("bold");

  if (topCustomers.length > 0) {
    const rows = topCustomers.map(row => [
      row.customer,
      row.currentTier,
      row.orders,
      row.revenue,
      row.finalTier,
      row.reason,
    ]);

    sheet.getRange(2, 1, rows.length, 6).setValues(rows);
    sheet.getRange(2, 4, rows.length, 1).setNumberFormat('#,##0.00');
    sheet.getRange(2, 3, rows.length, 1).setNumberFormat('#,##0');
  }

  sheet.setFrozenRows(1);
}


// ============================================================
// Write summary
// ============================================================
function writeSummary(spreadsheet, results) {
  let sheet = spreadsheet.getSheetByName(CONFIG.summarySheet);

  if (sheet) {
    sheet.clearContents();
    sheet.clearFormats();
  } else {
    sheet = spreadsheet.insertSheet(CONFIG.summarySheet);
  }

  const upgrades = results.filter(row => row.reason === "Upgrade");

  const movements = {
    "Tier 1 to Tier 2": upgrades.filter(row => row.currentTier === "Tier 1" && row.finalTier === "Tier 2").length,
    "Tier 1 to Tier 3": upgrades.filter(row => row.currentTier === "Tier 1" && row.finalTier === "Tier 3").length,
    "Tier 1 to Tier 4": upgrades.filter(row => row.currentTier === "Tier 1" && row.finalTier === "Tier 4").length,
    "Tier 2 to Tier 3": upgrades.filter(row => row.currentTier === "Tier 2" && row.finalTier === "Tier 3").length,
    "Tier 2 to Tier 4": upgrades.filter(row => row.currentTier === "Tier 2" && row.finalTier === "Tier 4").length,
    "Tier 3 to Tier 4": upgrades.filter(row => row.currentTier === "Tier 3" && row.finalTier === "Tier 4").length,
  };

  function averageRevenue(fromTier, toTier) {
    const group = upgrades.filter(row => row.currentTier === fromTier && row.finalTier === toTier);
    if (group.length === 0) return 0;

    return Math.round(
      group.reduce((sum, row) => sum + row.revenue, 0) / group.length * 100
    ) / 100;
  }

  const headers = [["MOVEMENT", "CUSTOMERS", "AVERAGE_REVENUE_12M"]];
  sheet.getRange(1, 1, 1, 3).setValues(headers).setFontWeight("bold");

  const rows = [
    ["--- Tier 1 ---", "", ""],
    ["Tier 1 → Tier 2", movements["Tier 1 to Tier 2"], averageRevenue("Tier 1", "Tier 2")],
    ["Tier 1 → Tier 3", movements["Tier 1 to Tier 3"], averageRevenue("Tier 1", "Tier 3")],
    ["Tier 1 → Tier 4", movements["Tier 1 to Tier 4"], averageRevenue("Tier 1", "Tier 4")],
    ["TOTAL from Tier 1", movements["Tier 1 to Tier 2"] + movements["Tier 1 to Tier 3"] + movements["Tier 1 to Tier 4"], ""],

    ["--- Tier 2 ---", "", ""],
    ["Tier 2 → Tier 3", movements["Tier 2 to Tier 3"], averageRevenue("Tier 2", "Tier 3")],
    ["Tier 2 → Tier 4", movements["Tier 2 to Tier 4"], averageRevenue("Tier 2", "Tier 4")],
    ["TOTAL from Tier 2", movements["Tier 2 to Tier 3"] + movements["Tier 2 to Tier 4"], ""],

    ["--- Tier 3 ---", "", ""],
    ["Tier 3 → Tier 4", movements["Tier 3 to Tier 4"], averageRevenue("Tier 3", "Tier 4")],
    ["TOTAL from Tier 3", movements["Tier 3 to Tier 4"], ""],

    ["", "", ""],
    ["TOTAL UPGRADES", upgrades.length, ""],
  ];

  sheet.getRange(2, 1, rows.length, 3).setValues(rows);

  rows.forEach((row, index) => {
    if (typeof row[2] === "number" && row[2] > 0) {
      sheet.getRange(2 + index, 3).setNumberFormat('#,##0.00');
    }

    if (String(row[0]).startsWith("---") || String(row[0]).startsWith("TOTAL")) {
      sheet.getRange(2 + index, 1, 1, 3).setFontWeight("bold");
    }

    if (typeof row[1] === "number") {
      sheet.getRange(2 + index, 2).setNumberFormat('#,##0');
    }
  });

  sheet.setColumnWidth(1, 220);
  sheet.setColumnWidth(2, 100);
  sheet.setColumnWidth(3, 160);
  sheet.setFrozenRows(1);
}


// ============================================================
// Create config sheet
// ============================================================
function createConfigSheet(spreadsheet) {
  const sheet = spreadsheet.insertSheet(CONFIG.configSheet);

  sheet.getRange("A1")
    .setValue("CUSTOMER TIER AUTOMATION CONFIGURATION")
    .setFontWeight("bold")
    .setFontSize(12);

  sheet.setRowHeight(1, 28);

  sheet.getRange("A2")
    .setValue("Cutoff date")
    .setFontWeight("bold");

  sheet.getRange("B2")
    .setValue(new Date())
    .setNumberFormat("dd/MM/yyyy")
    .setHorizontalAlignment("center");

  sheet.getRange("A4")
    .setValue("Enter the cutoff date used to analyse the previous 12 months.")
    .setFontStyle("italic")
    .setFontColor("#555555");

  sheet.getRange("A6")
    .setValue("Tier rules:")
    .setFontWeight("bold");

  const rules = [
    ["Tier 4", ">= 7,900 revenue + minimum order threshold"],
    ["Tier 3", "3,450 - 7,899 revenue + minimum order threshold"],
    ["Tier 2", "2,000 - 3,449 revenue + minimum order threshold"],
    ["Tier 1", "< 2,000 revenue"],
    ["-", "Customers are not downgraded automatically"],
    ["-", "Excluded customers keep their current tier"],
  ];

  rules.forEach((rule, index) => {
    sheet.getRange(7 + index, 1).setValue(rule[0]).setFontWeight("bold");
    sheet.getRange(7 + index, 2).setValue(rule[1]);
  });

  sheet.setColumnWidth(1, 120);
  sheet.setColumnWidth(2, 420);

  return sheet;
}


// ============================================================
// Instruction modal
// ============================================================
function showInstructions() {
  const html = HtmlService.createHtmlOutput(`
    <style>
      body { font-family: Arial, sans-serif; font-size: 13px; color: #222; padding: 16px; }
      h2 { color: #1F3864; border-bottom: 2px solid #1F3864; padding-bottom: 6px; }
      h3 { color: #1F3864; margin-top: 18px; margin-bottom: 4px; }
      ul { margin: 6px 0 10px 18px; line-height: 1.7; }
      code { background: #f0f0f0; padding: 1px 5px; border-radius: 3px; }
      .note { background: #FFF2CC; border-left: 4px solid #F0B400; padding: 8px 12px; border-radius: 4px; margin-top: 12px; }
    </style>

    <h2>Usage instructions</h2>

    <h3>1. Prepare order data</h3>
    <ul>
      <li>Create a sheet named <b>Orders</b>.</li>
      <li>Paste a table with these exact columns:<br>
      <code>CUSTOMER_ID &nbsp; CURRENT_TIER &nbsp; order_date &nbsp; order_id &nbsp; Total</code></li>
      <li>Dates should be valid Google Sheets dates or standard date strings.</li>
    </ul>

    <h3>2. Optional: excluded customers</h3>
    <ul>
      <li>Create a sheet named <b>Excluded Customers</b>.</li>
      <li>Column A should contain customer IDs.</li>
      <li>These customers keep their current tier and are excluded from automatic upgrades.</li>
    </ul>

    <h3>3. Configure cutoff date</h3>
    <ul>
      <li>Go to <b>Customer Tiers &gt; Open configuration</b>.</li>
      <li>Enter the cutoff date in cell <b>B2</b>.</li>
    </ul>

    <h3>4. Run analysis</h3>
    <ul>
      <li>Go to <b>Customer Tiers &gt; Analyse customer tiers</b>.</li>
      <li>The script generates the Results, Top Customers and Summary sheets.</li>
    </ul>

    <div class="note"><b>Note:</b> Each run overwrites the Results, Top Customers and Summary sheets.</div>
  `).setWidth(560).setHeight(500).setTitle("Usage instructions");

  SpreadsheetApp.getUi().showModalDialog(html, "Usage instructions");
}


// ============================================================
// Legend modal
// ============================================================
function showLegend() {
  const html = HtmlService.createHtmlOutput(`
    <style>
      body { font-family: Arial, sans-serif; font-size: 13px; color: #222; padding: 16px; }
      h2 { color: #1F3864; border-bottom: 2px solid #1F3864; padding-bottom: 6px; }
      h3 { color: #1F3864; margin-top: 20px; margin-bottom: 6px; }
      table { border-collapse: collapse; width: 100%; margin-bottom: 16px; }
      th { background: #1F3864; color: #fff; padding: 7px 10px; text-align: left; font-size: 12px; }
      td { padding: 6px 10px; border-bottom: 1px solid #ddd; font-size: 12px; vertical-align: top; }
    </style>

    <h2>Results legend</h2>

    <h3>Tier rules</h3>
    <table>
      <tr><th>Tier</th><th>Revenue</th><th>Minimum orders to upgrade</th></tr>
      <tr><td><b>Tier 4</b></td><td>7,900 or more</td><td>Minimum order threshold</td></tr>
      <tr><td><b>Tier 3</b></td><td>3,450 - 7,899</td><td>Minimum order threshold</td></tr>
      <tr><td><b>Tier 2</b></td><td>2,000 - 3,449</td><td>Minimum order threshold</td></tr>
      <tr><td><b>Tier 1</b></td><td>Less than 2,000</td><td>Default base tier</td></tr>
    </table>

    <h3>Reason column</h3>
    <table>
      <tr><th>Reason</th><th>Meaning</th></tr>
      <tr><td><b>Upgrade</b></td><td>The customer meets revenue and order requirements.</td></tr>
      <tr><td><b>Blocked: fewer than minimum orders</b></td><td>The customer meets revenue requirements but not the order threshold.</td></tr>
      <tr><td><b>Protected: no downgrade</b></td><td>The customer would move down based on revenue, but downgrades are not applied automatically.</td></tr>
      <tr><td><b>No change</b></td><td>The current tier matches the calculated tier.</td></tr>
      <tr><td><b>Excluded: no upgrade</b></td><td>The customer is marked as excluded and keeps the current tier.</td></tr>
    </table>
  `).setWidth(600).setHeight(560).setTitle("Results legend");

  SpreadsheetApp.getUi().showModalDialog(html, "Results legend");
}


// ============================================================
// Menu
// ============================================================
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("Customer Tiers")
    .addItem("Analyse customer tiers", "analyseCustomerTiers")
    .addSeparator()
    .addItem("Open configuration", "openConfig")
    .addSeparator()
    .addItem("Usage instructions", "showInstructions")
    .addItem("Results legend", "showLegend")
    .addToUi();
}


function openConfig() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();

  let sheet = spreadsheet.getSheetByName(CONFIG.configSheet);
  if (!sheet) sheet = createConfigSheet(spreadsheet);

  spreadsheet.setActiveSheet(sheet);
}
