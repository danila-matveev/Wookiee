// === НАСТРОЙКИ ЗАЩИТЫ ОТ 401 ОШИБКИ ===
const SCRIPT_NAME_OZON_GLUE = 'Обновление листа Склейки Озон';

// Новая функция для получения цен по кабинетам (исправленная версия)
function getOzonPricesForKabinet() {
  const sheetName = "Склейки Озон";
  const ozonSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
  
  if (!ozonSheet) {
    alertMessage("Лист '" + sheetName + "' не найден!");
    return;
  }
  
  // Получаем данные с листа (начиная с 3 строки)
  const lastRow = ozonSheet.getLastRow();
  if (lastRow < 3) {
    alertMessage("Нет данных для обработки на листе '" + sheetName + "'");
    return;
  }
  
  const dataRange = ozonSheet.getRange(3, 1, lastRow - 2, 5); // Колонки A-E, начиная с строки 3
  const data = dataRange.getValues();
  
  // Группируем артикулы по кабинетам
  const kabinetData = {};
  
  data.forEach((row, index) => {
    const kabinet = row[0]; // Колонка A - кабинет (ООО/ИП)
    const artikul = row[4]; // Колонка E - артикул Озон
    
    if (kabinet && artikul && artikul.toString().trim() !== '') {
      if (!kabinetData[kabinet]) {
        kabinetData[kabinet] = [];
      }
      kabinetData[kabinet].push({
        artikul: artikul.toString().trim(),
        rowIndex: index + 3 // +3 потому что начинаем с 3й строки
      });
    }
  });
  
  Logger.log('Найдено кабинетов: ' + Object.keys(kabinetData).length);
  for (const [kabinet, items] of Object.entries(kabinetData)) {
    Logger.log(`Кабинет ${kabinet}: ${items.length} товаров`);
  }
  
  // Очищаем колонки R, S и V перед записью новых данных (начиная с 3 строки)
  if (lastRow >= 3) {
    ozonSheet.getRange(3, 18, lastRow - 2, 3).clearContent(); // Колонки R, S, V
  }
  
  // Обрабатываем каждый кабинет
  for (const [kabinet, items] of Object.entries(kabinetData)) {
    if (cabinetCredentials[kabinet]) {
      toastMessageTitle(`Обрабатываю кабинет: ${kabinet}`, `Найдено ${items.length} товаров`);
      
      const prices = getPricesForKabinetCorrected(kabinet, items.map(item => item.artikul));
      
      Logger.log(`Получено цен для кабинета ${kabinet}: ${Object.keys(prices).length}`);
      
      // Записываем результаты в таблицу
      let writtenCount = 0;
      items.forEach(item => {
        const priceInfo = prices[item.artikul];
        if (priceInfo) {
          ozonSheet.getRange(item.rowIndex, 18).setValue(priceInfo.price); // Колонка R - цена до скидки (перечеркнутая)
          ozonSheet.getRange(item.rowIndex, 19).setValue(priceInfo.discountedPrice); // Колонка S - текущая цена со скидкой
          ozonSheet.getRange(item.rowIndex, 22).setValue(priceInfo.stock); // Колонка V - остаток FBO
          writtenCount++;
        }
      });
      
      Logger.log(`Записано цен для кабинета ${kabinet}: ${writtenCount}`);
      Utilities.sleep(2000); // Пауза между запросами к разным кабинетам
    } else {
      Logger.log(`Не найдены учетные данные для кабинета: ${kabinet}`);
    }
  }
  
  toastMessageTitle("Обработка завершена!", "Цены и остатки успешно получены");
}

// ИСПРАВЛЕННАЯ функция для получения цен для конкретного кабинета
function getPricesForKabinetCorrected(kabinet, artikuls) {
  const credentials = cabinetCredentials[kabinet];
  const result = {};
  
  // Фильтруем артикулы - только числа
  const validArtikuls = artikuls
    .map(sku => {
      const num = parseInt(sku, 10);
      return isNaN(num) ? null : num;
    })
    .filter(sku => sku !== null && sku > 0);
  
  if (validArtikuls.length === 0) {
    Logger.log(`Нет валидных артикулов для кабинета ${kabinet}`);
    return result;
  }
  
  Logger.log(`Запрашиваем цены для кабинета ${kabinet}: ${validArtikuls.length} артикулов`);
  
  try {
    // Создаем отчет для получения цен
    const formData = {
      "language": "DEFAULT",
      "visibility": "ALL",
      "sku": validArtikuls
    };
    
    const options = {
      "method": "POST",
      "muteHttpExceptions": true,
      "headers": {
        "Client-Id": credentials.clientId,
        "Api-Key": credentials.apiKey,
        "Content-Type": "application/json"
      },
      "payload": JSON.stringify(formData)
    };
    
    const ozonApiUrl = "https://api-seller.ozon.ru/v1/report/products/create";
    const response = UrlFetchApp.fetch(ozonApiUrl, options);
    const data = JSON.parse(response.getContentText());
    
    Logger.log(`Ответ от API для ${kabinet}: ${data.result ? 'OK' : 'ERROR'}`);
    
    if (data && data.result && data.result.code) {
      const reportId = data.result.code;
      Logger.log(`Report ID для ${kabinet}: ${reportId}`);
      
      // Ждем генерации отчета
      let reportReady = false;
      let attempts = 0;
      let reportUrl = null;
      
      while (!reportReady && attempts < 12) {
        Utilities.sleep(5000); // Ждем 5 секунд
        attempts++;
        
        reportUrl = getReportLinkCSVlite(reportId, credentials);
        if (reportUrl) {
          reportReady = true;
          Logger.log(`Отчет готов! Ссылка: ${reportUrl}`);
        } else {
          Logger.log(`Попытка ${attempts}: отчет еще не готов`);
        }
      }
      
      if (reportUrl) {
        // Скачиваем и парсим CSV
        const csvData = downloadAndParseCSVCorrected(reportUrl, kabinet);
        Logger.log(`Получено строк CSV: ${csvData.length}`);
        
        if (csvData.length > 1) {
          // Находим индексы колонок по заголовкам (как в первом скрипте)
          const headers = csvData[0];
          
          // Ищем индексы ключевых колонок
          const skuIndex = headers.findIndex(h => 
            h === 'SKU' || h.includes('SKU')
          );
          
          const priceIndex = headers.findIndex(h => 
            h === 'Цена до скидки (перечеркнутая цена), ₽' || 
            h.includes('перечеркнутая цена')
          );
          
          const discountedPriceIndex = headers.findIndex(h => 
            h === 'Текущая цена с учетом скидки, ₽' || 
            h.includes('Текущая цена')
          );
          
          const stockIndex = headers.findIndex(h => 
            h === 'Доступно к продаже по схеме FBO, шт.' || 
            (h.includes('FBO') && h.includes('шт'))
          );
          
          Logger.log(`Найдены индексы для ${kabinet}:`);
          Logger.log(`- SKU: ${skuIndex} (${headers[skuIndex]})`);
          Logger.log(`- Цена до скидки: ${priceIndex} (${headers[priceIndex]})`);
          Logger.log(`- Текущая цена: ${discountedPriceIndex} (${headers[discountedPriceIndex]})`);
          Logger.log(`- Остаток FBO: ${stockIndex} (${headers[stockIndex]})`);
          
          // Парсим данные из CSV
          for (let i = 1; i < csvData.length; i++) {
            const row = csvData[i];
            
            if (skuIndex !== -1 && row[skuIndex]) {
              const sku = row[skuIndex].toString().trim();
              
              // Парсим значения с правильной обработкой (как в первом скрипте)
              let price = 0;
              let discountedPrice = 0;
              let stock = 0;
              
              // Цена до скидки (перечеркнутая цена)
              if (priceIndex !== -1 && row[priceIndex]) {
                const priceStr = row[priceIndex].toString().replace(/[']/g, '').replace(/,/g, '.');
                price = parseFloat(priceStr) || 0;
              }
              
              // Текущая цена со скидкой
              if (discountedPriceIndex !== -1 && row[discountedPriceIndex]) {
                const discountedStr = row[discountedPriceIndex].toString().replace(/[']/g, '').replace(/,/g, '.');
                discountedPrice = parseFloat(discountedStr) || 0;
              }
              
              // Остаток FBO
              if (stockIndex !== -1 && row[stockIndex]) {
                const stockStr = row[stockIndex].toString().replace(/[']/g, '');
                stock = parseInt(stockStr, 10) || 0;
              }
              
              if (sku) {
                result[sku] = {
                  price: price,
                  discountedPrice: discountedPrice,
                  stock: stock
                };
                Logger.log(`Найдены данные для SKU ${sku}: цена ${price} / со скидкой ${discountedPrice} / остаток ${stock}`);
              }
            }
          }
        }
      } else {
        Logger.log(`Не удалось получить отчет для кабинета ${kabinet}`);
      }
    } else {
      Logger.log(`Ошибка в ответе API для кабинета ${kabinet}`);
    }
  } catch (error) {
    Logger.log(`Ошибка при получении цен для кабинета ${kabinet}: ${error}`);
  }
  
  Logger.log(`Итог для кабинета ${kabinet}: найдено ${Object.keys(result).length} записей`);
  return result;
}

// ИСПРАВЛЕННАЯ функция для скачивания и парсинга CSV
function downloadAndParseCSVCorrected(csvUrl, kabinet) {
  try {
    const response = UrlFetchApp.fetch(csvUrl);
    const csvContent = response.getContentText('UTF-8');
    
    // Диагностика
    Logger.log(`=== ДИАГНОСТИКА CSV для ${kabinet} ===`);
    Logger.log(`Длина CSV: ${csvContent.length} символов`);
    
    if (csvContent.length > 0) {
      // Показываем первые 500 символов для отладки
      Logger.log(`Первые 500 символов: ${csvContent.substring(0, 500)}`);
    }
    
    // Разбиваем на строки
    const rows = csvContent.split('\n');
    Logger.log(`Всего строк: ${rows.length}`);
    
    // Убираем BOM символ из первой строки если есть
    if (rows[0] && rows[0].charCodeAt(0) === 0xFEFF) {
      rows[0] = rows[0].substring(1);
    }
    
    const result = [];
    
    // Парсим каждую строку
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      if (!row || row.trim() === '' || row === '\r' || row === '\n') {
        continue;
      }
      
      const parsedRow = parseCSVLineCorrected(row);
      result.push(parsedRow);
      
      // Выводим заголовки для отладки
      if (i === 0) {
        Logger.log('=== ЗАГОЛОВКИ CSV ===');
        parsedRow.forEach((header, idx) => {
          Logger.log(`${idx}: "${header}"`);
        });
      }
    }
    
    return result;
  } catch (error) {
    Logger.log(`Ошибка при парсинге CSV: ${error}`);
    return [];
  }
}

// Функция для парсинга строки CSV с учетом кавычек (как в первом скрипте)
function parseCSVLineCorrected(line) {
  const result = [];
  let current = '';
  let inQuotes = false;
  
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    const nextChar = i + 1 < line.length ? line[i + 1] : '';
    
    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        // Двойные кавычки внутри кавычек
        current += '"';
        i++; // Пропускаем следующую кавычку
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === ';' && !inQuotes) {
      // Очищаем от апострофов и лишних кавычек
      current = current.replace(/^['"]+|['"]+$/g, '').trim();
      result.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  
  // Последнее значение
  current = current.replace(/^['"]+|['"]+$/g, '').trim();
  result.push(current);
  
  return result;
}

// Функция для получения ссылки на отчет
function getReportLinkCSVlite(reportId, credentials) {
  try {
    const formData = { "code": reportId };
    
    const options = {
      "method": "POST",
      "muteHttpExceptions": true,
      "headers": {
        "Client-Id": credentials.clientId,
        "Api-Key": credentials.apiKey,
        "Content-Type": "application/json"
      },
      "payload": JSON.stringify(formData)
    };
    
    const ozonApiUrl = "https://api-seller.ozon.ru/v1/report/info";
    const response = UrlFetchApp.fetch(ozonApiUrl, options);
    const data = JSON.parse(response.getContentText());
    
    if (data && data.result) {
      if (data.result.status === 'success' && data.result.file) {
        return data.result.file;
      }
    }
    return null;
  } catch (error) {
    Logger.log(`Ошибка при получении ссылки на отчет ${reportId}: ${error}`);
    return null;
  }
}

// Вспомогательные функции
function toastMessageTitle(message, title) {
  SpreadsheetApp.getActiveSpreadsheet().toast(message, title, 5);
}

function alertMessage(message) {
  SpreadsheetApp.getUi().alert(message);
}

// ТЕСТОВАЯ ФУНКЦИЯ ДЛЯ ДИАГНОСТИКИ
function testKabinetFunctionWithDebug() {
  Logger.log('=== ЗАПУСК ТЕСТА С ДИАГНОСТИКОЙ ===');
  
  // Создаем тестовые данные
  const testKabinet = "ИП"; // или "ООО"
  const testSkus = ["1325307096"]; // SKU из вашего примера
  
  if (cabinetCredentials[testKabinet]) {
    const result = getPricesForKabinetCorrected(testKabinet, testSkus);
    
    Logger.log('=== РЕЗУЛЬТАТЫ ТЕСТА ===');
    Logger.log(JSON.stringify(result, null, 2));
    
    // Проверяем конкретный SKU
    if (result["1325307096"]) {
      const data = result["1325307096"];
      Logger.log(`SKU 1325307096:`);
      Logger.log(`- Цена до скидки (перечеркнутая): ${data.price}`);
      Logger.log(`- Текущая цена со скидкой: ${data.discountedPrice}`);
      Logger.log(`- Остаток FBO: ${data.stock}`);
      
      // Сравнение с ожидаемыми значениями
      Logger.log(`Ожидается: цена со скидкой ~1303, просто цена ~5100, остаток 0`);
    } else {
      Logger.log('SKU 1325307096 не найден в результатах!');
    }
  } else {
    Logger.log(`Нет учетных данных для кабинета ${testKabinet}`);
  }
}

// Альтернативная функция с жестко заданными индексами (если динамический поиск не работает)
function getPricesForKabinetFixed(kabinet, artikuls) {
  const credentials = cabinetCredentials[kabinet];
  const result = {};
  
  // Фильтруем артикулы
  const validArtikuls = artikuls
    .map(sku => parseInt(sku, 10))
    .filter(sku => !isNaN(sku) && sku > 0);
  
  if (validArtikuls.length === 0) return result;
  
  try {
    const formData = {
      "language": "DEFAULT",
      "visibility": "ALL",
      "sku": validArtikuls
    };
    
    const options = {
      "method": "POST",
      "muteHttpExceptions": true,
      "headers": {
        "Client-Id": credentials.clientId,
        "Api-Key": credentials.apiKey,
        "Content-Type": "application/json"
      },
      "payload": JSON.stringify(formData)
    };
    
    const ozonApiUrl = "https://api-seller.ozon.ru/v1/report/products/create";
    const response = UrlFetchApp.fetch(ozonApiUrl, options);
    const data = JSON.parse(response.getContentText());
    
    if (data && data.result && data.result.code) {
      const reportId = data.result.code;
      let reportUrl = null;
      let attempts = 0;
      
      while (!reportUrl && attempts < 12) {
        Utilities.sleep(5000);
        attempts++;
        reportUrl = getReportLinkCSVlite(reportId, credentials);
      }
      
      if (reportUrl) {
        const csvData = downloadAndParseCSVCorrected(reportUrl, kabinet);
        
        if (csvData.length > 1) {
          // ИСПРАВЛЕННЫЕ ИНДЕКСЫ на основе структуры из первого скрипта:
          // 2 - SKU (колонка C)
          // 24 - Цена до скидки (перечеркнутая цена), ₽ (колонка Y)
          // 23 - Текущая цена с учетом скидки, ₽ (колонка X)
          // 18 - Доступно к продаже по схеме FBO, шт. (колонка S)
          
          Logger.log(`Используем фиксированные индексы: SKU[2], Цена[24], Цена со скидкой[23], Остаток[18]`);
          
          for (let i = 1; i < csvData.length; i++) {
            const row = csvData[i];
            if (row.length > 24) {
              const sku = row[2] ? row[2].toString().trim() : '';
              
              if (sku) {
                // Парсим значения
                const priceStr = row[24] ? row[24].toString().replace(/[']/g, '').replace(/,/g, '.') : '0';
                const discountedStr = row[23] ? row[23].toString().replace(/[']/g, '').replace(/,/g, '.') : '0';
                const stockStr = row[18] ? row[18].toString().replace(/[']/g, '') : '0';
                
                const price = parseFloat(priceStr) || 0;
                const discountedPrice = parseFloat(discountedStr) || 0;
                const stock = parseInt(stockStr, 10) || 0;
                
                result[sku] = {
                  price: price,
                  discountedPrice: discountedPrice,
                  stock: stock
                };
              }
            }
          }
        }
      }
    }
  } catch (error) {
    Logger.log(`Ошибка: ${error}`);
  }
  
  return result;
}

// Обновленная основная функция с выбором метода
function getOzonPricesForKabinetFixedVersion() {
  const sheetName = "Склейки Озон";
  const ozonSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
  
  if (!ozonSheet) {
    alertMessage("Лист '" + sheetName + "' не найден!");
    return;
  }
  
  const lastRow = ozonSheet.getLastRow();
  if (lastRow < 3) {
    alertMessage("Нет данных для обработки");
    return;
  }
  
  const dataRange = ozonSheet.getRange(3, 1, lastRow - 2, 5);
  const data = dataRange.getValues();
  
  const kabinetData = {};
  
  data.forEach((row, index) => {
    const kabinet = row[0];
    const artikul = row[4];
    
    if (kabinet && artikul && artikul.toString().trim() !== '') {
      if (!kabinetData[kabinet]) kabinetData[kabinet] = [];
      kabinetData[kabinet].push({
        artikul: artikul.toString().trim(),
        rowIndex: index + 3
      });
    }
  });
  
  // Очищаем старые данные
  if (lastRow >= 3) {
    ozonSheet.getRange(3, 18, lastRow - 2, 3).clearContent();
  }
  
  // Обрабатываем каждый кабинет
  for (const [kabinet, items] of Object.entries(kabinetData)) {
    if (cabinetCredentials[kabinet]) {
      toastMessageTitle(`Обрабатываю ${kabinet}`, `${items.length} товаров`);
      
      // Используем фиксированную версию
      const prices = getPricesForKabinetFixed(kabinet, items.map(item => item.artikul));
      
      // Записываем результаты
      items.forEach(item => {
        const priceInfo = prices[item.artikul];
        if (priceInfo) {
          ozonSheet.getRange(item.rowIndex, 18).setValue(priceInfo.price); // Колонка R
          ozonSheet.getRange(item.rowIndex, 19).setValue(priceInfo.discountedPrice); // Колонка S
          ozonSheet.getRange(item.rowIndex, 22).setValue(priceInfo.stock); // Колонка V
        }
      });
      
      Utilities.sleep(2000);
    }
  }
  
  toastMessageTitle("Готово!", "Цены обновлены");
}

/**
 * Проверяет ошибку на 401/400 с неверным API-ключом для скрипта Склейки Озон
 * @param {Error} error - Объект ошибки
 * @param {string} accountName - Название кабинета (ИП/ООО)
 */
function checkAndHandle401ErrorOzonGlue(error, accountName = '') {
  console.log("🔍 checkAndHandle401ErrorOzonGlue вызвана!");
  console.log("🔍 Ошибка:", error.toString());
  console.log("🔍 Кабинет:", accountName);
  
  const errorStr = error.toString();
  const responseText = error.message || '';
  
  // Проверяем различные варианты ошибок авторизации Ozon
  const isAuthError = 
    // Коды ошибок
    errorStr.includes('401') || 
    errorStr.includes('403') ||
    errorStr.includes('400') ||
    
    // Текстовые ошибки Ozon
    errorStr.includes('Invalid Api-Key') ||
    errorStr.includes('Invalid Client-Id') ||
    errorStr.includes('Api-Key') ||
    errorStr.includes('Client-Id') ||
    errorStr.includes('Unauthorized') ||
    errorStr.includes('Not authorized') ||
    errorStr.includes('Auth Error') ||
    errorStr.includes('authentication') ||
    errorStr.includes('Authentication failed') ||
    
    // Проверяем содержимое сообщения об ошибке
    responseText.includes('Invalid Api-Key') ||
    responseText.includes('Invalid Client-Id') ||
    responseText.includes('Api-Key') ||
    responseText.includes('Client-Id');
  
  console.log("🔍 Это ошибка авторизации Ozon?", isAuthError);
  
  if (isAuthError) {
    console.log("✅ Обнаружена ошибка авторизации Ozon, вызываю handle401Error...");
    
    // Добавляем информацию о кабинете к ошибке
    const enhancedError = accountName 
      ? new Error(`Ozon API (Склейки): ${error.message} (Кабинет: ${accountName})`)
      : new Error(`Ozon API (Склейки): ${error.message}`);
    
    handle401Error(enhancedError, SCRIPT_NAME_OZON_GLUE);
  } else {
    console.log("⏭️ Это не ошибка авторизации Ozon, пропускаем.");
  }
}