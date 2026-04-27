/**
 * WB Promocodes — refresh button.
 *
 * Install:
 *   1. Extensions → Apps Script → paste this file.
 *   2. Project Settings → Script Properties:
 *        PROMOCODES_API_URL  = http://77.233.212.61:8092
 *        PROMOCODES_API_KEY  = <PROMOCODES_API_KEY from server .env>
 *   3. Sheets: Insert → Drawing «🔄 ОБНОВИТЬ» → Three-dots → Assign script → refreshPromocodes
 */
function refreshPromocodes() {
  const props = PropertiesService.getScriptProperties();
  const url = props.getProperty('PROMOCODES_API_URL');
  const token = props.getProperty('PROMOCODES_API_KEY');
  if (!url || !token) {
    SpreadsheetApp.getUi().alert('PROMOCODES_API_URL or PROMOCODES_API_KEY missing in Script Properties');
    return;
  }
  const sheet = SpreadsheetApp.getActive().getSheetByName('Промокоды_аналитика');
  sheet.getRange('B2').setValue('⏳ Запускаю...');

  const resp = UrlFetchApp.fetch(url + '/promocodes/run', {
    method: 'post',
    contentType: 'application/json',
    headers: { 'X-API-Key': token },
    muteHttpExceptions: true,
    payload: JSON.stringify({ mode: 'last_week' })
  });
  const code = resp.getResponseCode();
  let json = {};
  try { json = JSON.parse(resp.getContentText()); } catch (e) {}

  if (code === 202 || code === 200) {
    sheet.getRange('B2').setValue('⏳ Запущено: ' + (json.started_at || ''));
    sheet.getRange('B3').setValue('Жди ~5 мин и нажми ещё раз для проверки статуса');
  } else {
    sheet.getRange('B2').setValue('❌ Ошибка ' + code);
    sheet.getRange('B3').setValue(json.detail || resp.getContentText().slice(0, 200));
  }
}

/** Показать текущий статус последнего запуска */
function checkPromocodesStatus() {
  const props = PropertiesService.getScriptProperties();
  const url = props.getProperty('PROMOCODES_API_URL');
  const token = props.getProperty('PROMOCODES_API_KEY');
  const resp = UrlFetchApp.fetch(url + '/promocodes/status', {
    method: 'get',
    headers: { 'X-API-Key': token },
    muteHttpExceptions: true,
  });
  SpreadsheetApp.getUi().alert(resp.getContentText());
}
