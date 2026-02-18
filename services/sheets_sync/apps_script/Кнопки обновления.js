/**
 * Trigger functions for update buttons.
 * Writes TRUE to a trigger cell -> Python control_panel.py detects it and runs sync.
 *
 * Instructions:
 * 1. On each sheet: Insert -> Drawing -> refresh icon
 * 2. Right-click drawing -> Assign script -> enter function name from the list below
 */

function triggerSync_(sheetBaseName, cell) {
  cell = cell || "C1";
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ws = ss.getSheetByName(sheetBaseName + "_TEST") || ss.getSheetByName(sheetBaseName);
  if (!ws) {
    SpreadsheetApp.getActive().toast("Sheet not found: " + sheetBaseName, "Error");
    return;
  }
  ws.getRange(cell).setValue(true);
  SpreadsheetApp.getActive().toast("Update started. Please wait ~1 min.", sheetBaseName);
}

function updateWbStocks()    { triggerSync_("WB остатки"); }
function updateWbPrices()    { triggerSync_("WB Цены"); }
function updateMoysklad()    { triggerSync_("МойСклад_АПИ"); }
function updateOzon()        { triggerSync_("Ozon остатки и цены"); }
function updateFeedbacksOOO() { triggerSync_("Отзывы ООО"); }
function updateFeedbacksIP()  { triggerSync_("Отзывы ИП"); }
function updateFinData()     { triggerSync_("Фин данные", "D1"); }
