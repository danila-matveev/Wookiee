const ALERT_EMAILS = ['reg@wookiee.shop', 'mlukovnikow@rambler.ru'];

// === УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ОБРАБОТКИ 401 ОШИБКИ ===
/**
 * Обработчик 401 ошибок для всех скриптов
 * @param {Error} error - Объект ошибки
 * @param {string} scriptName - Название скрипта, в котором произошла ошибка
 */
function handle401Error(error, scriptName) {
  try {
    // Получаем информацию о таблице
    const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    const spreadsheetUrl = spreadsheet ? spreadsheet.getUrl() : 'Не доступна';
    const spreadsheetName = spreadsheet ? spreadsheet.getName() : 'Нет названия';
    
    // Проверяем наличие названия скрипта
    if (!scriptName || scriptName.trim() === '') {
      scriptName = 'Неизвестный скрипт';
      console.warn('Внимание: функция handle401Error вызвана без указания scriptName');
    }
    
    // Формируем тему и текст письма
    const subject = `🚨 401 Ошибка в скрипте "${scriptName}"`;
    const body = `
Внимание! Обнаружена ошибка 401 (ошибка авторизации/аутентификации) в GoogleSheets Wookie.

ДЕТАЛИ ОШИБКИ:
• Скрипт: ${scriptName}
• Таблица: ${spreadsheetName}
• Ссылка на таблицу: ${spreadsheetUrl}
• Время ошибки: ${new Date().toLocaleString('ru-RU')}
• Текст ошибки: ${error.toString()}

НЕОБХОДИМЫЕ ДЕЙСТВИЯ:
1. Проверить API-ключи или токены доступа
2. Проверить срок действия аутентификационных данных
3. Убедиться, что сервис API доступен и учетные данные корректны
4. Обратиться к разработчику https://t.me/mishachitalnik
`;
    
    // Отправляем письмо на все указанные адреса
    ALERT_EMAILS.forEach(email => {
      MailApp.sendEmail({
        to: email,
        subject: subject,
        body: body
      });
    });
    
    console.log(`Письма об ошибке 401 отправлены на: ${ALERT_EMAILS.join(', ')}`);
  } catch (mailError) {
    console.error('Не удалось отправить оповещение об ошибке:', mailError);
  }
}

// === АЛЬТЕРНАТИВНЫЙ ВАРИАНТ - функция с дефолтным scriptName ===
/**
 * Обработчик 401 ошибок (устаревшая версия, для обратной совместимости)
 * Использует глобальную переменную SCRIPT_NAME если не передан scriptName
 */
function handle401ErrorLegacy(error, scriptName) {
  // Если scriptName не передан, пытаемся использовать глобальную переменную
  const finalScriptName = scriptName || (typeof SCRIPT_NAME !== 'undefined' ? SCRIPT_NAME : 'Неизвестный скрипт');
  
  // Вызываем основную функцию
  handle401Error(error, finalScriptName);
}