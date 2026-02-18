/**
 * Запуск обновления листа "Фин данные".
 *
 * Устанавливает чекбокс D1 = TRUE, Python-сервис (control_panel.py) обнаружит его
 * в течение ~60 секунд и запустит sync_fin_data.
 *
 * Привязать к кнопке: Вставка → Рисунок → ⋮ → Назначить скрипт → refreshFinData
 */
function refreshFinData() {
  // Ищем лист — сначала TEST, потом основной
  var sheet = activeSpreadsheet.getSheetByName("Фин данные_TEST")
           || activeSpreadsheet.getSheetByName("Фин данные");
  if (!sheet) {
    SpreadsheetApp.getUi().alert("Лист 'Фин данные' не найден");
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
    "Фин данные",
    10
  );
}
