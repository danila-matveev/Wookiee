/**
 * Запуск обновления листа "Фин данные NEW".
 *
 * Устанавливает чекбокс D1 = TRUE, Python-сервис (control_panel.py) обнаружит его
 * в течение ~60 секунд и запустит sync_fin_data_new.
 *
 * Привязать к кнопке: Вставка → Рисунок → ⋮ → Назначить скрипт → refreshFinDataNew
 */
function refreshFinDataNew() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Фин данные NEW_TEST") || ss.getSheetByName("Фин данные NEW");
  if (!sheet) {
    SpreadsheetApp.getUi().alert("Лист 'Фин данные NEW' не найден");
    return;
  }

  // Проверить что даты заполнены
  var b1 = sheet.getRange("B1").getValue();
  var c1 = sheet.getRange("C1").getValue();
  if (!b1 || !c1) {
    SpreadsheetApp.getUi().alert("Заполните даты в B1 (начало) и C1 (конец периода)");
    return;
  }

  // Установить чекбокс D1 = TRUE → Python polling обнаружит и запустит sync
  sheet.getRange("D1").setValue(true);

  // Уведомление пользователю
  SpreadsheetApp.getActive().toast(
    "Обновление запущено. Данные обновятся в течение 1 минуты.",
    "Фин данные NEW",
    10
  );
}
