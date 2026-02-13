// Глобальные переменные текущей таблицы//
let sheetWbStocks = activeSpreadsheet.getSheetByName("WB остатки");

const SCRIPT_NAME_WB_STOCKS = 'Обновление остатков WB (лист WB остатки)';

// Опции для запросов к API
function getOptions(apiKey) {
  return {
    "method": "GET",
    "muteHttpExceptions": true, // Добавляем для лучшей обработки ошибок
    "headers": {
      "Authorization": apiKey,
      "Content-Type": "application/json"
    }
  };
}

// Основная функция для получения остатков из двух кабинетов
function letsGetStocksWb() {
  try {
    // Получаем данные из первого кабинета
    console.log("=== ЗАПРОС К ПЕРВОМУ КАБИНЕТУ ===");
    const dataCabinet1 = getCabinetDataWb(apiKeyIP, "ИП");
    
    // Получаем данные из второго кабинета
    console.log("=== ЗАПРОС КО ВТОРОМУ КАБИНЕТУ ===");
    const dataCabinet2 = getCabinetDataWb(apiKeyOOO, "ООО");
    
    // Объединяем данные из двух кабинетов
    console.log("=== ОБЪЕДИНЕНИЕ ДАННЫХ ===");
    const mergedData = mergeCabinetData(dataCabinet1, dataCabinet2);
    
    // Подготавливаем данные для записи
    const dataArrayForPaste = createMergedDataArray(mergedData.combinedData, mergedData.warehouseNames);
    
    // Записываем данные в таблицу
    writeToSpreadsheetWb(dataArrayForPaste, mergedData.warehouseNames);
    
    console.log("✅ WB Stocks: Остатки успешно обновлены!");
    
  } catch (error) {
    console.error("💥 WB Stocks: Ошибка в основной функции:", error);
    
    // Проверяем ошибки авторизации
    checkAndHandle401ErrorWbStocks(error);
    
    throw error;
  }
}

// Функция для получения данных из одного кабинета
function getCabinetDataWb(apiKey, cabinetName) {
  try {
    console.log(`Получение данных из ${cabinetName}`);
    
    const wbApiURl = "https://seller-analytics-api.wildberries.ru/api/v1/warehouse_remains?groupByBarcode=true&groupByBrand=true&groupBySubject=true&groupBySa=true&groupByNm=true&groupBySize=true";
    const options = getOptions(apiKey);
    
    const response = UrlFetchApp.fetch(wbApiURl, options);
    const responseCode = response.getResponseCode();
    
    // Проверяем 401 ошибку
    if (responseCode === 401) {
      const errorMsg = `API Wildberries Stocks вернул 401 для кабинета ${cabinetName}. Токен недействителен.`;
      const detailedError = new Error(errorMsg);
      checkAndHandle401ErrorWbStocks(detailedError);
      throw detailedError;
    }
    
    if (responseCode !== 200) {
      throw new Error(`Ошибка API ${cabinetName}: ${responseCode}`);
    }
    
    const data = JSON.parse(response.getContentText());
    
    console.log(`Отчёт для ${cabinetName} отправлен на формирование`);
    const current_report_id = data.data.taskId;
    
    // Ожидаем готовности отчета и получаем данные
    const reportData = letsCheckCurrentReport(current_report_id, apiKey, cabinetName);
    
    return {
      cabinetName: cabinetName,
      data: reportData.data,
      barcodeWarehouseData: reportData.barcodeWarehouseData
    };
    
  } catch (error) {
    console.error(`Ошибка при получении данных из ${cabinetName}:`, error);
    
    // Проверяем любые ошибки авторизации
    checkAndHandle401ErrorWbStocks(error);
    
    return {
      cabinetName: cabinetName,
      data: [],
      barcodeWarehouseData: { barcodes: [], warehouseNames: [] }
    };
  }
}

// Функция для объединения данных из двух кабинетов
function mergeCabinetData(dataCabinet1, dataCabinet2) {
  // Объединяем все уникальные баркоды из обоих кабинетов
  const allBarcodes = [...new Set([
    ...dataCabinet1.barcodeWarehouseData.barcodes,
    ...dataCabinet2.barcodeWarehouseData.barcodes
  ])];
  
  // Объединяем склады из обоих кабинетов БЕЗ идентификации кабинета
  let allWarehouseNames = [...new Set([
    ...dataCabinet1.barcodeWarehouseData.warehouseNames,
    ...dataCabinet2.barcodeWarehouseData.warehouseNames
  ])];
  
  // Выделяем специальные склады и сортируем остальные
  const specialWarehouses = [
    "В пути до получателей",
    "В пути возвраты на склад WB", 
    "Всего находится на складах"
  ];
  
  // Удаляем специальные склады из общего списка
  const regularWarehouses = allWarehouseNames.filter(name => 
    !specialWarehouses.includes(name)
  ).sort(); // Сортируем обычные склады по алфавиту
  
  // Собираем финальный список: сначала специальные, потом обычные
  allWarehouseNames = [...specialWarehouses, ...regularWarehouses];
  
  // Объединяем все данные
  const allData = [
    ...dataCabinet1.data.map(item => ({ ...item, source: dataCabinet1.cabinetName })),
    ...dataCabinet2.data.map(item => ({ ...item, source: dataCabinet2.cabinetName }))
  ];
  
  console.log(`Объединено баркодов: ${allBarcodes.length}`);
  console.log(`Объединено складов: ${allWarehouseNames.length}`);
  console.log(`Объединено товаров: ${allData.length}`);
  
  return {
    combinedData: allData,
    warehouseNames: allWarehouseNames,
    barcodes: allBarcodes
  };
}

// Создание общего массива данных для записи
function createMergedDataArray(combinedData, warehouseNames) {
  const dataArray = [];
  
  // Проходим по каждому уникальному баркоду
  const uniqueBarcodes = [...new Set(combinedData.map(item => item.barcode))];
  
  uniqueBarcodes.forEach(barcode => {
    // Находим все записи с этим баркодом (могут быть из разных кабинетов)
    const items = combinedData.filter(data => data.barcode === barcode);
    
    // Берем данные из первой найденной записи (основные данные товара)
    const mainItem = items[0];
    
    if (mainItem) {
      // Создаем строку с основными данными товара в НОВОМ ПОРЯДКЕ
      const row_sku = [
        mainItem.barcode || "",           // Баркод
        mainItem.vendorCode || "",        // Артикул
        mainItem.techSize || "",          // Размер
        mainItem.nmId || "",              // NMID
        mainItem.subjectName || "",       // Категория
        mainItem.brand || "",             // Бренд
        mainItem.volume || "",            // Объем
        mainItem.source || ""             // Кабинет
      ];
      
      // Добавляем остатки по всем складам
      const stockQuantities = getMergedWarehouseQuantities(items, warehouseNames);
      const row = row_sku.concat(stockQuantities);
      
      dataArray.push(row);
    }
  });
  
  return dataArray;
}

// Функция для получения остатков по всем складам из обоих кабинетов
function getMergedWarehouseQuantities(items, warehouseNames) {
  const result = [];
  
  // Проходим по каждому названию склада
  for (let i = 0; i < warehouseNames.length; i++) {
    const warehouseName = warehouseNames[i];
    let quantity = 0;
    
    // Для каждого товара проверяем остатки на этом складе
    items.forEach(item => {
      // Ищем склад в массиве warehouses товара
      for (let j = 0; j < item.warehouses.length; j++) {
        if (item.warehouses[j].warehouseName === warehouseName) {
          quantity += item.warehouses[j].quantity;
          break;
        }
      }
    });
    
    result.push(quantity);
  }
  
  return result;
}

// Функция записи данных в таблицу
function writeToSpreadsheetWb(dataArrayForPaste, warehouseNames) {
  // Очищаем старые данные
  sheetWbStocks.getRange(3, 1, sheetWbStocks.getLastRow(), sheetWbStocks.getLastColumn()).clearContent();
  
  // Записываем заголовки в НОВОМ ПОРЯДКЕ
  const warehouseHeaders = [[
    "Баркод", "Артикул", "Размер", "NMID", "Категория", "Бренд", "Объем", "Кабинет", ...warehouseNames
  ]];
  
  sheetWbStocks.getRange(3, 1, 1, warehouseHeaders[0].length).setValues(warehouseHeaders);
  
  // Записываем основные данные
  if (dataArrayForPaste.length > 0) {
    sheetWbStocks.getRange(4, 1, dataArrayForPaste.length, dataArrayForPaste[0].length).setValues(dataArrayForPaste);
  }
  
  // Обновляем дату и время выгрузки
  sheetWbStocks.getRange(1, 2).setValue(formattedDate);
  sheetWbStocks.getRange(2, 2).setValue(formattedTime);
  
  console.log(`Данные успешно записаны: ${dataArrayForPaste.length} товаров`);
}

// Остальные функции остаются с небольшими изменениями
function letsCheckCurrentReport(current_report_id, apiKey, cabinetName) {
  Utilities.sleep(10000);
  
  for (let i = 0; i < 100; i++) {
    Utilities.sleep(15000);
    console.log(`Ожидание отчета ${current_report_id} из ${cabinetName}...`);
    
    try {
      let url_check_current_report = `https://seller-analytics-api.wildberries.ru/api/v1/warehouse_remains/tasks/${current_report_id}/status`;
      const options = getOptions(apiKey);
      const response_check_current_report = UrlFetchApp.fetch(url_check_current_report, options);
      const responseCode = response_check_current_report.getResponseCode();
      
      // Проверяем 401 ошибку при проверке статуса
      if (responseCode === 401) {
        const errorMsg = `API Wildberries Stocks вернул 401 при проверке статуса отчета ${cabinetName}.`;
        const detailedError = new Error(errorMsg);
        checkAndHandle401ErrorWbStocks(detailedError);
        throw detailedError;
      }
      
      const data_check_current_report = JSON.parse(response_check_current_report.getContentText());
      
      if (data_check_current_report.data.status === "done") {
        console.log(`Отчёт ${current_report_id} из ${cabinetName} готов`);
        Utilities.sleep(60000);
        
        return letsGetCurrentReport(current_report_id, apiKey, cabinetName);
      }
    } catch (error) {
      console.error(`Ошибка при проверке статуса отчета из ${cabinetName}:`, error);
      
      // Проверяем ошибки авторизации
      if (error.toString().includes('401') || 
          error.toString().toLowerCase().includes('unauthorized')) {
        checkAndHandle401ErrorWbStocks(error);
      }
      
      // Продолжаем попытки или бросаем ошибку
      if (i === 99) {
        throw new Error(`Таймаут ожидания отчета из ${cabinetName}: ${error.message}`);
      }
    }
  }
  
  throw new Error(`Таймаут ожидания отчета из ${cabinetName}`);
}

function letsGetCurrentReport(current_report_id, apiKey, cabinetName) {
  console.log(`Скачиваю отчёт из ${cabinetName}`);
  
  let url_get_current_report = `https://seller-analytics-api.wildberries.ru/api/v1/warehouse_remains/tasks/${current_report_id}/download`;
  const options = getOptions(apiKey);
  const response_get_current_report = UrlFetchApp.fetch(url_get_current_report, options);
  const data_get_current_report = JSON.parse(response_get_current_report.getContentText());
  
  console.log(`Отчёт ${current_report_id} из ${cabinetName} получен`);
  
  let barcodeWarehouseData = extractUniqueValues(data_get_current_report);
  
  return {
    data: data_get_current_report,
    barcodeWarehouseData: barcodeWarehouseData
  };
}

// Функции extractUniqueValues остается без изменений
function extractUniqueValues(data) {
  console.log("Извлекаю уникальные баркоды");
  const uniqueBarcodes = [...new Set(data.map(item => item.barcode))];
  const uniqueWarehouseNames = [
    ...new Set(data.flatMap(item => item.warehouses.map(warehouse => warehouse.warehouseName)))
  ];

  return {
    barcodes: uniqueBarcodes,
    warehouseNames: uniqueWarehouseNames
  };
}

/**
 * Проверяет ошибку на 401 и отправляет уведомление для скрипта WB Stocks
 * @param {Error} error - Объект ошибки
 */
function checkAndHandle401ErrorWbStocks(error) {
  const errorStr = error.toString();
  if (errorStr.includes('401') || 
      errorStr.includes('Unauthorized') ||
      errorStr.includes('Not authorized')) {
    handle401Error(error, SCRIPT_NAME_WB_STOCKS);
  }
}