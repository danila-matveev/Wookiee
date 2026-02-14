// Глобальные переменные текущей таблицы//
let reportStockSpreadsheetOzon = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Ozon остатки и цены");
let allProductsSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Все товары");

// === НАСТРОЙКИ ЗАЩИТЫ ОТ 401 ОШИБКИ ===
const SCRIPT_NAME_OZON_STOCKS = 'Обновление цен и остатков Ozon (лист Ozon остатки и цены)';

// Функция для нормализации числовых значений
function normalizeNumber(value) {
  if (typeof value === 'string') {
    const normalized = value.replace(/\./g, ',').trim();
    const numberValue = parseFloat(normalized.replace(',', '.'));
    return isNaN(numberValue) ? 0 : numberValue;
  }
  return value || 0;
}

// Простой и точный поиск колонок
function findColumns() {
  try {
    const sheet = allProductsSheet;
    const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    
    let skuColumn = -1;
    let cabinetColumn = -1;
    
    headers.forEach((header, index) => {
      const headerStr = String(header).trim();
      const columnLetter = String.fromCharCode(64 + (index + 1));
      
      // ТОЧНЫЙ поиск колонки FBO OZON SKU ID
      if (headerStr === 'FBO OZON SKU ID') {
        skuColumn = index + 1;
        console.log(`✅ Найден FBO OZON SKU ID в колонке: ${columnLetter}`);
      }
      
      // ТОЧНЫЙ поиск колонки Импортер
      if (headerStr === 'Импортер') {
        cabinetColumn = index + 1;
        console.log(`✅ Найден Импортер в колонке: ${columnLetter}`);
      }
    });
    
    // Проверяем что обе колонки найдены
    if (skuColumn === -1) {
      console.error('❌ Колонка "FBO OZON SKU ID" не найдена!');
      return null;
    }
    
    if (cabinetColumn === -1) {
      console.error('❌ Колонка "Импортер" не найдена!');
      return null;
    }
    
    console.log(`🎯 Финальный выбор: FBO OZON SKU ID - ${String.fromCharCode(64 + skuColumn)}(${skuColumn}), Импортер - ${String.fromCharCode(64 + cabinetColumn)}(${cabinetColumn})`);
    
    return { skuColumn, cabinetColumn };
    
  } catch (error) {
    console.error("❌ Ошибка при поиске колонок:", error);
    return null;
  }
}

// Функция для получения SKU из листа "Все товары"
function getSKUfromAllProductsSheet() {
  const result = {
    ip: [],
    ooo: []
  };
  
  try {
    // Находим колонки
    const columns = findColumns();
    if (!columns) {
      alertMessage("❌ Не удалось найти необходимые колонки в таблице");
      return result;
    }
    
    const skuColumn = columns.skuColumn;
    const cabinetColumn = columns.cabinetColumn;
    
    console.log(`📊 Используем колонки: FBO OZON SKU ID - ${String.fromCharCode(64 + skuColumn)}, Импортер - ${String.fromCharCode(64 + cabinetColumn)}`);
    
    const lastRow = allProductsSheet.getLastRow();
    console.log("📈 Последняя строка в 'Все товары':", lastRow);
    
    if (lastRow < 2) {
      alertMessage("Нет данных для обработки на листе 'Все товары'");
      return result;
    }

    // Получаем данные: SKU и Кабинет
    const skuData = allProductsSheet.getRange(2, skuColumn, lastRow - 1, 1).getValues();
    const cabinetData = allProductsSheet.getRange(2, cabinetColumn, lastRow - 1, 1).getValues();
    
    console.log(`📝 Получено ${skuData.length} строк данных`);
    
    let processedCount = 0;
    let ipCount = 0;
    let oooCount = 0;
    let skippedCount = 0;
    
    for (let i = 0; i < skuData.length; i++) {
      const sku = String(skuData[i][0] || "").trim();
      const kabinet = String(cabinetData[i][0] || "").trim();
      
      // Отладочная информация для первых 5 строк
      if (i < 3) {
        console.log(`🔍 Строка ${i + 2}: SKU='${sku}', Кабинет='${kabinet}'`);
      }
      
      // Проверяем что SKU валидный (число)
      if (sku && !isNaN(parseInt(sku)) && sku !== '') {
        processedCount++;
        
        // Определяем кабинет
        if (kabinet.includes("ИП") || kabinet.includes("Медведева")) {
          result.ip.push(sku);
          ipCount++;
        } else if (kabinet.includes("ООО") || kabinet.includes("Вуки")) {
          result.ooo.push(sku);
          oooCount++;
        } else {
          skippedCount++;
          if (i < 3) {
            console.log(`⏭️ Пропущено: неизвестный кабинет '${kabinet}'`);
          }
        }
      } else {
        skippedCount++;
        if (i < 3) {
          console.log(`⏭️ Пропущено: некорректный SKU '${sku}'`);
        }
      }
    }
    
    console.log(`📊 Итог: обработано - ${processedCount}, ИП - ${ipCount}, ООО - ${oooCount}, пропущено - ${skippedCount}`);
    
    return result;
    
  } catch (error) {
    console.error("❌ Ошибка при получении SKU:", error);
    return result;
  }
}

// Основная функция для получения остатков и цен из двух кабинетов
function ozon_current_stocks_prices() {
  try {
    console.log("🔄 Ozon Stocks: Начало выгрузки остатков и цен...");
    
    if (!allProductsSheet || !reportStockSpreadsheetOzon) {
      alertMessage("Не найден лист 'Все товары' или 'Ozon остатки и цены'");
      return;
    }

    toastMessageTitle("Начинаем выгрузку остатков и цен из Ozon", "Запуск");

    // Получаем SKU разделенные по кабинетам
    const skuData = getSKUfromAllProductsSheet();
    console.log("📦 SKU ИП:", skuData.ip.length);
    console.log("📦 SKU ООО:", skuData.ooo.length);

    if (skuData.ip.length === 0 && skuData.ooo.length === 0) {
      alertMessage("⚠️ Не найдено SKU для выгрузки");
      return;
    }

    // Получаем данные из кабинета ИП (разбиваем на части по 1000 SKU)
    let ipData = [];
    if (skuData.ip.length > 0) {
      console.log("🔄 ЗАПРОС К КАБИНЕТУ ИП");
      const ipBatches = splitIntoBatches(skuData.ip, 1000);
      console.log(`ИП: разбито на ${ipBatches.length} батчей по 1000 SKU`);
      
      for (let i = 0; i < ipBatches.length; i++) {
        console.log(`Обрабатываем батч ИП ${i + 1}/${ipBatches.length}`);
        const batchData = getCabinetDataOzon(ipBatches[i], "ИП");
        ipData = ipData.concat(batchData);
        // Делаем паузу между батчами чтобы не перегружать API
        if (i < ipBatches.length - 1) {
          Utilities.sleep(2000);
        }
      }
    }

    // Получаем данные из кабинета ООО (разбиваем на части по 1000 SKU)
    let oooData = [];
    if (skuData.ooo.length > 0) {
      console.log("🔄 ЗАПРОС К КАБИНЕТУ ООО");
      const oooBatches = splitIntoBatches(skuData.ooo, 1000);
      console.log(`ООО: разбито на ${oooBatches.length} батчей по 1000 SKU`);
      
      for (let i = 0; i < oooBatches.length; i++) {
        console.log(`Обрабатываем батч ООО ${i + 1}/${oooBatches.length}`);
        const batchData = getCabinetDataOzon(oooBatches[i], "ООО");
        oooData = oooData.concat(batchData);
        // Делаем паузу между батчами чтобы не перегружать API
        if (i < oooBatches.length - 1) {
          Utilities.sleep(2000);
        }
      }
    }

    // Объединяем данные
    const combinedData = [...ipData, ...oooData];
    console.log("✅ Всего получено товаров:", combinedData.length);

    // Записываем данные в таблицу
    writeToSpreadsheetOzon(combinedData);
    
    console.log("✅ Ozon Stocks: Данные успешно обновлены!");
    toastMessageTitle(`Выгружено ${combinedData.length} товаров`, "Завершено");
    
  } catch (error) {
    console.error("💥 Ozon Stocks: Ошибка в основной функции:", error);
    
    // Проверяем ошибки авторизации
    checkAndHandle401ErrorOzonStocks(error);
    
    toastMessageTitle(`Ошибка: ${error.message}`, "❌ Ошибка выполнения");
    throw error;
  }
}

// Функция для разбивки массива на батчи
function splitIntoBatches(array, batchSize) {
  const batches = [];
  for (let i = 0; i < array.length; i += batchSize) {
    batches.push(array.slice(i, i + batchSize));
  }
  return batches;
}

// Функция для получения данных из одного кабинета (для одного батча до 1000 SKU)
function getCabinetDataOzon(skuArray, cabinetName) {
  if (skuArray.length === 0) return [];
  
  // Проверяем что не превышаем лимит
  if (skuArray.length > 1000) {
    console.error(`Ошибка: батч для ${cabinetName} содержит ${skuArray.length} SKU (максимум 1000)`);
    return [];
  }
  
  try {
    console.log(`📡 Получение данных из кабинета ${cabinetName} (${skuArray.length} SKU)`);
    
    const credentials = cabinetCredentials[cabinetName];
    const formData = {
      "language": "DEFAULT",
      "visibility": "ALL",
      "sku": skuArray.map(sku => parseInt(sku))
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
    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();
    
    // Проверяем ошибки авторизации (Ozon возвращает 400 с "Invalid Api-Key")
    if (responseCode === 401 || responseCode === 403 || responseCode === 400) {
      // Проверяем текст ошибки на наличие сообщения о неверном API-ключе
      if (responseText.includes('Invalid Api-Key') || responseText.includes('Invalid Client-Id')) {
        const errorMsg = `Ozon API вернул ${responseCode} для кабинета ${cabinetName}. API-ключ недействителен. Ответ: ${responseText}`;
        const detailedError = new Error(errorMsg);
        checkAndHandle401ErrorOzonStocks(detailedError, cabinetName);
        throw detailedError;
      }
    }
    
    if (responseCode !== 200) {
      const errorMsg = `Ошибка Ozon API ${cabinetName}: ${responseCode} - ${responseText}`;
      throw new Error(errorMsg);
    }
    
    const data = JSON.parse(responseText);
    
    if (!data || !data.result || !data.result.code) {
      throw new Error(`Неверный ответ от Ozon API для ${cabinetName}: ${responseText}`);
    }
    
    console.log(`📊 Отчёт для ${cabinetName} (${skuArray.length} SKU) отправлен на формирование`);
    const report_id = data.result.code;
    
    // Ждем формирования отчета
    let reportUrl = null;
    let attempts = 0;
    const maxAttempts = 12;
    
    while (!reportUrl && attempts < maxAttempts) {
      Utilities.sleep(5000);
      attempts++;
      reportUrl = getReportLinkCSV(report_id, credentials, cabinetName);
      if (!reportUrl) {
        console.log(`⏳ Попытка ${attempts}/${maxAttempts}: отчет еще не готов`);
      }
    }
    
    if (reportUrl) {
      console.log(`✅ Отчет готов! Ссылка: ${reportUrl}`);
      const reportData = getCsvFile(reportUrl, cabinetName);
      console.log(`📥 Получено ${reportData.length} товаров из отчета ${cabinetName}`);
      return reportData;
    } else {
      console.log(`❌ Не удалось получить отчет для кабинета ${cabinetName}`);
      return [];
    }
    
  } catch (error) {
    console.error(`❌ Ошибка при получении данных из ${cabinetName}:`, error);
    
    // Проверяем любые ошибки авторизации
    checkAndHandle401ErrorOzonStocks(error, cabinetName);
    
    return [];
  }
}

// Функция для получения ссылки на CSV отчет
function getReportLinkCSV(report_id, credentials, cabinetName) {
  try {
    const formData = { "code": report_id };
    
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
    const responseCode = response.getResponseCode();
    
    // Проверяем 401 ошибку
    if (responseCode === 401 || responseCode === 403) {
      const errorMsg = `Ozon API вернул ${responseCode} при проверке статуса отчета ${cabinetName}.`;
      const detailedError = new Error(errorMsg);
      checkAndHandle401ErrorOzonStocks(detailedError, cabinetName);
      return null;
    }
    
    if (responseCode !== 200) {
      console.error(`Ошибка Ozon API при проверке отчета: ${responseCode}`);
      return null;
    }
    
    const data = JSON.parse(response.getContentText());
    
    if (data && data.result) {
      if (data.result.status === 'success' && data.result.file) {
        return data.result.file;
      }
    }
    return null;
  } catch (error) {
    console.error(`❌ Ошибка при получении ссылки на отчет ${report_id}:`, error);
    
    // Проверяем ошибки авторизации
    checkAndHandle401ErrorOzonStocks(error, cabinetName);
    
    return null;
  }
}

// Функция для обработки CSV файла (исправленная)
function getCsvFile(report_url, cabinetName) {
  if (!report_url) {
    throw new Error("Не найден URL отчета");
  }
  
  console.log(`🔍 Начинаем обработку CSV для ${cabinetName}`);
  
  try {
    // Получаем сырой текст CSV
    const response = UrlFetchApp.fetch(report_url);
    const responseCode = response.getResponseCode();
    
    // Проверяем ошибки доступа
    if (responseCode === 401 || responseCode === 403) {
      const errorMsg = `Ошибка доступа к CSV файлу Ozon для ${cabinetName}: ${responseCode}`;
      throw new Error(errorMsg);
    }
    
    if (responseCode !== 200) {
      throw new Error(`Ошибка загрузки CSV для ${cabinetName}: ${responseCode}`);
    }
    
    const text = response.getContentText();
    
    // Диагностика: выводим первые 500 символов для отладки
    console.log(`📊 Первые 500 символов CSV: ${text.substring(0, 500)}`);
    
    // Разбиваем на строки
    const rows = text.split('\n');
    console.log(`📊 Всего строк в CSV: ${rows.length}`);
    
    // Удаляем BOM символ из первой строки если есть
    if (rows[0].charCodeAt(0) === 0xFEFF) {
      rows[0] = rows[0].substring(1);
    }
    
    // Парсим заголовки
    const headers = parseCsvLine(rows[0]);
    console.log(`📊 Колонок в CSV: ${headers.length}`);
    console.log('📋 Заголовки из CSV:');
    headers.forEach((header, index) => {
      console.log(`${index}: "${header}"`);
    });
    
    let result_value_final = [];
    let processedCount = 0;
    let skippedCount = 0;
    
    // Обрабатываем каждую строку данных (начиная со второй строки)
    for (let i = 1; i < rows.length; i++) {
      const row = rows[i];
      if (!row || row.trim() === '' || row === '\r' || row === '\n') {
        continue; // Пропускаем пустые строки
      }
      
      try {
        // Парсим строку CSV
        const values = parseCsvLine(row);
        
        if (values.length < headers.length) {
          console.warn(`⚠️ Строка ${i} содержит меньше значений (${values.length}), чем заголовков (${headers.length})`);
          skippedCount++;
          continue;
        }
        
        // Проверяем что SKU валиден (не пустой)
        const skuIndex = headers.indexOf('SKU');
        if (skuIndex !== -1) {
          const skuValue = values[skuIndex] || '';
          const cleanSku = skuValue.replace(/['"]/g, '').trim();
          if (!cleanSku || cleanSku === '') {
            console.log(`⏭️ Пропущена строка ${i}: пустой SKU`);
            skippedCount++;
            continue;
          }
        }
        
        // Обрабатываем значения
        const processedRow = [];
        
        for (let j = 0; j < values.length; j++) {
          let value = values[j] || '';
          
          // Очищаем от апострофов и лишних кавычек
          value = value.replace(/^['"]+|['"]+$/g, '').trim();
          
          // Преобразуем числовые значения
          const headerName = headers[j] || '';
          
          // Числовые колонки (с плавающей точкой)
          const floatHeaders = [
            'Контент-рейтинг', 'Рейтинг', 'Объем товара, л', 'Объемный вес, кг',
            'Текущая цена с учетом скидки, ₽', 'Цена до скидки (перечеркнутая цена), ₽', 
            'Цена Premium, ₽', 'Размер НДС, %'
          ];
          
          // Целочисленные колонки
          const intHeaders = [
            'Доступно к продаже по схеме FBO, шт.', 'Зарезервировано, шт',
            'Доступно к продаже по схеме FBS, шт.', 'Доступно к продаже по схеме realFBS, шт.',
            'Зарезервировано на моих складах, шт', 'Отзывы'
          ];
          
          const isFloat = floatHeaders.some(h => headerName.includes(h));
          const isInt = intHeaders.some(h => headerName.includes(h));
          
          if (isFloat) {
            // Убираем апострофы и преобразуем в число
            const cleanValue = value.replace(/[']/g, '').replace(/,/g, '.');
            const numValue = parseFloat(cleanValue);
            processedRow.push(isNaN(numValue) ? 0 : numValue);
          } else if (isInt) {
            const cleanValue = value.replace(/[']/g, '');
            const numValue = parseInt(cleanValue, 10);
            processedRow.push(isNaN(numValue) ? 0 : numValue);
          } else {
            processedRow.push(value);
          }
        }
        
        // Добавляем кабинет в конец
        processedRow.push(cabinetName);
        
        result_value_final.push(processedRow);
        processedCount++;
        
      } catch (error) {
        console.error(`❌ Ошибка при обработке строки ${i}:`, error);
        console.error(`Строка: ${row.substring(0, 100)}...`);
        skippedCount++;
      }
    }
    
    console.log(`✅ Обработано товаров из ${cabinetName}: ${processedCount} (пропущено: ${skippedCount})`);
    
    return result_value_final;
    
  } catch (error) {
    console.error(`❌ Ошибка при обработке CSV для ${cabinetName}:`, error);
    
    // Проверяем ошибки авторизации
    checkAndHandle401ErrorOzonStocks(error, cabinetName);
    
    throw error;
  }
}

// Функция для парсинга строки CSV с учетом кавычек
function parseCsvLine(line) {
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
      result.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  
  // Добавляем последнее значение
  result.push(current);
  
  return result;
}

// ОДНА ПРАВИЛЬНАЯ ФУНКЦИЯ ЗАПИСИ ДАННЫХ
function writeToSpreadsheetOzon(data) {
  console.log('=== НАЧАЛО ЗАПИСИ ДАННЫХ В ТАБЛИЦУ ===');
  
  // Очищаем старые данные
  reportStockSpreadsheetOzon.clearContents();
  
  // Записываем дату и время
  reportStockSpreadsheetOzon.getRange(1, 1).setValue("Дата составления отчёта");
  reportStockSpreadsheetOzon.getRange(1, 2).setValue(formattedDate);
  reportStockSpreadsheetOzon.getRange(2, 1).setValue("Время отчёта");
  reportStockSpreadsheetOzon.getRange(2, 2).setValue(formattedTime);
  
  if (data.length === 0) {
    console.log('❌ Нет данных для записи');
    return;
  }
  
  console.log(`📊 Получено ${data.length} строк данных для записи`);
  
  // Проверим структуру данных
  const sampleRow = data[0];
  console.log(`🔍 Колонок в первой строке: ${sampleRow.length}`);
  console.log('🔍 Пример данных (первые 10 колонок):');
  for (let i = 0; i < Math.min(10, sampleRow.length); i++) {
    console.log(`${i}: "${sampleRow[i]}" (тип: ${typeof sampleRow[i]})`);
  }
  
  // Заголовки согласно вашему CSV (30 колонок: 29 из CSV + 1 кабинет)
  const headers = [
    "Артикул",
    "Ozon Product ID", 
    "SKU", 
    "Barcode", 
    "Название товара", 
    "Контент-рейтинг", 
    "Бренд", 
    "Статус товара", 
    "Метки",  // Колонка 8 - Метки
    "Отзывы", 
    "Рейтинг", 
    "Видимость на Ozon", 
    "Причины скрытия", 
    "Дата создания", 
    "Категория", 
    "Тип", 
    "Объем товара, л", 
    "Объемный вес, кг", 
    "Доступно к продаже по схеме FBO, шт.", 
    "Зарезервировано, шт", 
    "Доступно к продаже по схеме FBS, шт.", 
    "Доступно к продаже по схеме realFBS, шт.", 
    "Зарезервировано на моих складах, шт", 
    "Текущая цена с учетом скидки, ₽", 
    "Цена до скидки (перечеркнутая цена), ₽", 
    "Цена Premium, ₽", 
    "Размер НДС, %", 
    "Ошибки", 
    "Предупреждения",
    "Кабинет"  // Последняя колонка - кабинет
  ];
  
  console.log(`📋 Ожидаемое количество колонок: ${headers.length}`);
  
  // Проверяем, что данные имеют правильную структуру
  if (sampleRow.length < headers.length - 1) {
    console.error(`❌ Ошибка: данные содержат только ${sampleRow.length} колонок, но ожидается ${headers.length - 1} из CSV + 1 кабинет`);
    console.error('Проверьте функцию getCsvFile - возможно, она неправильно парсит CSV');
    return;
  }
  
  // Преобразуем данные в правильный порядок
  const transformedData = [];
  let errorCount = 0;
  
  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    
    // Данные должны содержать 30 колонок: 29 из CSV + 1 кабинет
    if (row.length >= 30) {
      try {
        const newRow = [
          row[0] || '',   // Артикул (0)
          row[1] || '',   // Ozon Product ID (1)
          row[2] || '',   // SKU (2)
          row[3] || '',   // Barcode (3)
          row[4] || '',   // Название товара (4)
          row[5] || 0,    // Контент-рейтинг (5)
          row[6] || '',   // Бренд (6)
          row[7] || '',   // Статус товара (7)
          row[8] || '',   // Метки (8)
          row[9] || 0,    // Отзывы (9)
          row[10] || 0,   // Рейтинг (10)
          row[11] || '',  // Видимость на Ozon (11)
          row[12] || '',  // Причины скрытия (12)
          row[13] || '',  // Дата создания (13)
          row[14] || '',  // Категория (14)
          row[15] || '',  // Тип (15)
          row[16] || 0,   // Объем товара, л (16)
          row[17] || 0,   // Объемный вес, кг (17)
          row[18] || 0,   // FBO, шт. (18)
          row[19] || 0,   // Зарезервировано, шт (19)
          row[20] || 0,   // FBS, шт. (20)
          row[21] || 0,   // realFBS, шт. (21)
          row[22] || 0,   // Зарезервировано на складах (22)
          row[23] || 0,   // Текущая цена (23)
          row[24] || 0,   // Цена до скидки (24)
          row[25] || 0,   // Цена Premium (25)
          row[26] || 0,   // Размер НДС, % (26)
          row[27] || '',  // Ошибки (27)
          row[28] || '',  // Предупреждения (28)
          row[29] || ''   // Кабинет (29)
        ];
        
        transformedData.push(newRow);
      } catch (error) {
        console.error(`❌ Ошибка при трансформации строки ${i}:`, error);
        errorCount++;
      }
    } else {
      console.warn(`⚠️ Строка ${i} содержит только ${row.length} колонок (ожидается 30), пропускаем`);
    }
  }
  
  console.log(`✅ Успешно трансформировано строк: ${transformedData.length} из ${data.length} (ошибок: ${errorCount})`);
  
  if (transformedData.length === 0) {
    console.error('❌ Нет данных для записи после трансформации');
    return;
  }
  
  // Записываем заголовки и данные
  const allData = [headers, ...transformedData];
  const startRow = 3;
  const startCol = 1;
  const numRows = allData.length;
  const numCols = headers.length;
  
  console.log(`📝 Записываем ${numRows} строк с ${numCols} колонками`);
  
  reportStockSpreadsheetOzon.getRange(startRow, startCol, numRows, numCols)
    .setValues(allData);
  
  // Устанавливаем числовые форматы
  const sheet = reportStockSpreadsheetOzon;
  const lastRow = startRow + numRows - 1;
  
  // Колонки с десятичными числами (индексы начиная с 1)
  const decimalColumns = [6, 11, 17, 18, 24, 25, 26, 27]; 
  // 6 - Контент-рейтинг, 11 - Рейтинг, 17 - Объем товара, 18 - Объемный вес, 
  // 24-26 - Цены, 27 - НДС
  
  decimalColumns.forEach(colIndex => {
    if (lastRow > startRow) {
      sheet.getRange(startRow + 1, colIndex, numRows - 1).setNumberFormat("#,##0.00");
    }
  });
  
  // Колонки с целыми числами
  const integerColumns = [10, 19, 20, 21, 22, 23];
  // 10 - Отзывы, 19-23 - остатки
  
  integerColumns.forEach(colIndex => {
    if (lastRow > startRow) {
      sheet.getRange(startRow + 1, colIndex, numRows - 1).setNumberFormat("0");
    }
  });
  
  // Автоподбор ширины колонок
  sheet.autoResizeColumns(1, numCols);
  
  console.log(`💾 Данные успешно записаны: ${transformedData.length} товаров`);
  console.log('=== ЗАВЕРШЕНИЕ ЗАПИСИ ДАННЫХ ===');
}

// Вспомогательные функции
function toastMessageTitle(message, title) {
  SpreadsheetApp.getActiveSpreadsheet().toast(message, title, 5);
}

function alertMessage(message) {
  SpreadsheetApp.getUi().alert(message);
}

// Диагностическая функция
function diagnoseColumns() {
  console.log("=== ДИАГНОСТИКА КОЛОНОК ===");
  const columns = findColumns();
  if (columns) {
    console.log("✅ Колонки найдены:", columns);
  } else {
    console.log("❌ Колонки не найдены");
  }
  return columns;
}

// Функция для холодного запуска
function cold_start() {
  try {
    console.log("🔄 Ozon Stocks: Холодный запуск...");
    toastMessageTitle(formattedDate + " " + formattedTime, "Запуск скрипта Ozon");
    ozon_current_stocks_prices();
    console.log("✅ Ozon Stocks: Холодный запуск завершен!");
    toastMessageTitle("Вы великолепны!", "Завершено");
  } catch (error) {
    console.error("💥 Ozon Stocks: Ошибка в cold_start:", error);
    checkAndHandle401ErrorOzonStocks(error);
    throw error;
  }
}

function testCsvParsing() {
  console.log("🧪 ТЕСТИРОВАНИЕ ПАРСИНГА CSV");
  
  // Пример строки из вашего файла
  const testLine = `"'Angelina/dark_red_M";"773972695";"1333348279";"2000000008776";"Комплект нижнего белья с кружевом";"'100";"Wookiee";"Готов к продаже";"128";"'4.90";"Показывается";;"2023-12-10 09:31:32";"Белье";"Комплект нижнего белья";"'1.14";"'0.2";"0";"0";"0";"0";"0";"2266.00";"6700.00";;"5%";;`;
  
  console.log("Тестовая строка:", testLine);
  const parsed = parseCsvLine(testLine);
  console.log("Результат парсинга:", parsed);
  console.log("Количество значений:", parsed.length);
  
  // Тестируем очистку значений
  parsed.forEach((value, index) => {
    const cleaned = value.replace(/^['"]+|['"]+$/g, '').trim();
    console.log(`${index}: Исходное: "${value}" -> Очищенное: "${cleaned}"`);
  });
}

// Диагностическая функция для проверки структуры данных
function debugDataStructure() {
  console.log("=== ДЕБАГ СТРУКТУРЫ ДАННЫХ ===");
  
  // Тестовый запрос с 1-2 SKU
  const testSkus = ["1333348279", "1333348280"]; // Используйте реальные SKU
  console.log(`Тестируем с SKU: ${testSkus}`);
  
  const testData = getCabinetDataOzon(testSkus, "ИП");
  
  if (testData.length > 0) {
    console.log(`\n=== РЕЗУЛЬТАТ: ${testData.length} строк ===`);
    
    const row = testData[0];
    console.log(`Всего колонок в строке: ${row.length}`);
    
    console.log("\nПОЛНЫЙ АНАЛИЗ КАЖДОЙ КОЛОНКИ:");
    for (let i = 0; i < row.length; i++) {
      console.log(`[${i}] Тип: ${typeof row[i]}, Значение: "${row[i]}"`);
    }
    
    console.log(`\nКабинет (последний элемент): "${row[row.length - 1]}"`);
    
    // Проверим writeToSpreadsheetOzon
    console.log("\n=== ТЕСТИРУЕМ writeToSpreadsheetOzon ===");
    writeToSpreadsheetOzon(testData);
  } else {
    console.log("❌ Не удалось получить тестовые данные");
  }
}

/**
 * Проверяет ошибку на 401/400 с неверным API-ключом и отправляет уведомление
 * @param {Error} error - Объект ошибки
 * @param {string} accountName - Название кабинета (ИП/ООО)
 */
function checkAndHandle401ErrorOzonStocks(error, accountName = '') {
  console.log("🔍 checkAndHandle401ErrorOzonStocks вызвана!");
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
    
    // Текстовые ошибки
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
  
  console.log("🔍 Это ошибка авторизации?", isAuthError);
  
  if (isAuthError) {
    console.log("✅ Обнаружена ошибка авторизации Ozon, вызываю handle401Error...");
    
    // Добавляем информацию о кабинете к ошибке
    const enhancedError = accountName 
      ? new Error(`Ozon API: ${error.message} (Кабинет: ${accountName})`)
      : new Error(`Ozon API: ${error.message}`);
    
    handle401Error(enhancedError, SCRIPT_NAME_OZON_STOCKS);
  } else {
    console.log("⏭️ Это не ошибка авторизации, пропускаем.");
  }
}
