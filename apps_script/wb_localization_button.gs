/**
 * wb_localization_button.gs
 * Кнопка «🔄 Обновить» на листе «Обновление» таблицы «Перестановки ВБ».
 *
 * УСТАНОВКА:
 *   1. Открыть таблицу → Расширения → Apps Script
 *   2. Вставить этот файл (заменить содержимое)
 *   3. В Script Properties добавить:
 *        WB_LOGISTICS_API_KEY  — значение из .env (WB_LOGISTICS_API_KEY)
 *        WB_LOGISTICS_API_URL  — https://matveevdanila.com/api/vasily
 *   4. Привязать кнопку к функции runLocalization()
 *
 * ПОВЕДЕНИЕ:
 *   Fire-and-forget: отправляет POST /run и сразу возвращает управление.
 *   Сервер обновит Sheets сам (~20 мин). Нет ожидания — нет таймаута Apps Script.
 */

var SHEET_NAME = "Обновление";
var STATUS_CELL = "F3";  // ячейка статуса на листе «Обновление»

function runLocalization() {
  var props = PropertiesService.getScriptProperties();
  var apiKey = props.getProperty("WB_LOGISTICS_API_KEY");
  var baseUrl = props.getProperty("WB_LOGISTICS_API_URL") || "https://matveevdanila.com/api/vasily";

  if (!apiKey) {
    SpreadsheetApp.getUi().alert("Ошибка: WB_LOGISTICS_API_KEY не задан в Script Properties.");
    return;
  }

  // Сначала проверяем — не запущен ли уже расчёт
  try {
    var statusResp = UrlFetchApp.fetch(baseUrl + "/status", {
      method: "get",
      headers: { "x-api-key": apiKey },
      muteHttpExceptions: true,
    });
    var statusData = JSON.parse(statusResp.getContentText());
    if (statusData.status === "running") {
      var startedAt = statusData.started_at || "неизвестно";
      SpreadsheetApp.getUi().alert("Расчёт уже идёт (запущен в " + startedAt + ").\nПодождите ~20 мин и обновите страницу.");
      return;
    }
  } catch (e) {
    // не критично, продолжаем
  }

  // Запускаем расчёт (fire-and-forget)
  try {
    var resp = UrlFetchApp.fetch(baseUrl + "/run", {
      method: "post",
      headers: { "x-api-key": apiKey },
      muteHttpExceptions: true,
    });

    var code = resp.getResponseCode();
    if (code === 202) {
      // Успешно запущен — обновляем статус-ячейку и уходим
      var ss = SpreadsheetApp.getActiveSpreadsheet();
      var ws = ss.getSheetByName(SHEET_NAME);
      if (ws) {
        ws.getRange(STATUS_CELL).setValue("⏳ Идёт расчёт (~20 мин)...");
      }
      SpreadsheetApp.getUi().alert("✅ Расчёт запущен!\n\nДанные обновятся автоматически через ~20 минут.\nОбновите страницу браузера чтобы увидеть результат.");
    } else if (code === 409) {
      SpreadsheetApp.getUi().alert("Расчёт уже запущен. Подождите ~20 мин и обновите страницу.");
    } else {
      SpreadsheetApp.getUi().alert("Ошибка запуска (HTTP " + code + "): " + resp.getContentText());
    }
  } catch (e) {
    SpreadsheetApp.getUi().alert("Ошибка запуска: " + e.message);
  }
}

/**
 * Проверить текущий статус расчёта вручную.
 * Привязать к отдельной кнопке «Проверить статус» если нужно.
 */
function checkStatus() {
  var props = PropertiesService.getScriptProperties();
  var apiKey = props.getProperty("WB_LOGISTICS_API_KEY");
  var baseUrl = props.getProperty("WB_LOGISTICS_API_URL") || "https://matveevdanila.com/api/vasily";

  if (!apiKey) {
    SpreadsheetApp.getUi().alert("WB_LOGISTICS_API_KEY не задан.");
    return;
  }

  try {
    var resp = UrlFetchApp.fetch(baseUrl + "/status", {
      method: "get",
      headers: { "x-api-key": apiKey },
      muteHttpExceptions: true,
    });
    var data = JSON.parse(resp.getContentText());
    var msg = "Статус: " + data.status;
    if (data.started_at) msg += "\nЗапущен: " + data.started_at;
    if (data.finished_at) msg += "\nЗавершён: " + data.finished_at;
    if (data.error) msg += "\n❌ Ошибка: " + data.error;
    if (data.summary) {
      data.summary.forEach(function(cab) {
        msg += "\n\n" + cab.cabinet + ": ИЛ " + cab.overall_index + "%, перемещений " + cab.movements_count;
      });
    }
    SpreadsheetApp.getUi().alert(msg);
  } catch (e) {
    SpreadsheetApp.getUi().alert("Ошибка: " + e.message);
  }
}
