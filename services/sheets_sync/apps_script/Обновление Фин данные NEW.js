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
  var sheetTest = ss.getSheetByName("Фин данные NEW_TEST");
  var sheetProd = ss.getSheetByName("Фин данные NEW");
  // Целевой лист: _TEST если существует, иначе основной
  var target = sheetTest || sheetProd;
  // Лист-источник дат: всегда основной (пользователь заполняет даты там)
  var dateSource = sheetProd || sheetTest;

  if (!target) {
    SpreadsheetApp.getUi().alert("Лист 'Фин данные NEW' не найден");
    return;
  }

  // Проверить что даты заполнены (читаем с листа, где пользователь их ввёл)
  var b1 = dateSource.getRange("B1").getValue();
  var c1 = dateSource.getRange("C1").getValue();
  if (!b1 || !c1) {
    SpreadsheetApp.getUi().alert("Заполните даты в B1 (начало) и C1 (конец периода)");
    return;
  }

  // Скопировать даты на целевой лист, чтобы Python control_panel их прочитал
  if (target !== dateSource) {
    target.getRange("B1").setValue(b1);
    target.getRange("C1").setValue(c1);
  }

  // Установить чекбокс D1 = TRUE → Python polling обнаружит и запустит sync
  target.getRange("D1").setValue(true);

  // Уведомление пользователю
  SpreadsheetApp.getActive().toast(
    "Обновление запущено. Данные обновятся в течение 1 минуты.",
    "Фин данные NEW",
    10
  );
}
