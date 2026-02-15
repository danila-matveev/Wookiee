// ====== Глобальные переменные PricesWb =====//
let activeSpreadsheetPricesWb = SpreadsheetApp.getActiveSpreadsheet();
let sheetWbPriceListPricesWb = activeSpreadsheetPricesWb.getSheetByName("WB Цены");

// === НАСТРОЙКИ ЗАЩИТЫ ОТ 401 ОШИБКИ ===
const SCRIPT_NAME_WB = 'Скрипт обновления цен (лист WB Цены)';



// Глобальные переменные времени для PricesWb
const formattedDatePricesWb = Utilities.formatDate(new Date(), "GMT+3", "dd.MM.yyyy");
const formattedTimePricesWb = Utilities.formatDate(new Date(), "GMT+3", "HH:mm");

// Опции запросов для кабинетов
const optionsGetOooPricesWb = {
  "method": "GET",
  "muteHttpExceptions": true,
  "headers": {
    "Authorization": apiKeyOOO,
    "Content-Type": "application/json"
  }
};

const optionsGetIpPricesWb = {
  "method": "GET",
  "muteHttpExceptions": true,
  "headers": {
    "Authorization": apiKeyIP,
    "Content-Type": "application/json"
  }
};

/**
 * Основная функция получения цен для двух кабинетов
 */
function getWbPricesMultiAccount() {
  console.log("🔄 PricesWb: Начало получения цен для двух кабинетов...");
  
  try {
    // Получаем данные из обоих кабинетов
    const dataOoo = getWbPricesDataFromApi(optionsGetOooPricesWb, "ООО");
    const dataIp = getWbPricesDataFromApi(optionsGetIpPricesWb, "ИП");
    
    // Объединяем данные
    const allResults = {
      nmID: [...dataOoo.nmID, ...dataIp.nmID],
      vendorCode: [...dataOoo.vendorCode, ...dataIp.vendorCode],
      price: [...dataOoo.price, ...dataIp.price],
      discount: [...dataOoo.discount, ...dataIp.discount],
      account: [...dataOoo.account, ...dataIp.account]
    };
    
    console.log(`📊 PricesWb: Итого получено - ООО: ${dataOoo.nmID.length}, ИП: ${dataIp.nmID.length}, Всего: ${allResults.nmID.length}`);
    
    // Записываем данные в компактном формате
    writeWbPricesDataToSheet(allResults);
    
    console.log("✅ PricesWb: Цены для двух кабинетов успешно обновлены!");
    toastMessageTitle(`Обновлено: ООО - ${dataOoo.nmID.length}, ИП - ${dataIp.nmID.length} товаров`, "✅ PricesWb Успех");
    
  } catch (error) {
    console.error("💥 PricesWb: Ошибка:", error);
    
    // Обработка любых ошибок авторизации в основном блоке
    if (error.toString().includes('401') || 
        error.toString().toLowerCase().includes('unauthorized')) {
      handle401Error(error, SCRIPT_NAME_WB); // Передаем имя скрипта
    }
    
    toastMessageTitle(`Ошибка: ${error.message}`, "❌ PricesWb Ошибка");
    throw error;
  }
}

/**
 * Получение данных цен из API для конкретного кабинета
 */
function getWbPricesDataFromApi(options, accountName) {
  console.log(`   🔍 PricesWb: Получение данных для кабинета ${accountName}...`);
  
  const results = {
    nmID: [],
    vendorCode: [],
    price: [],
    discount: [],
    account: []
  };
  
  try {
    const wbApiUrl = "https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter?limit=1000";
    const response = UrlFetchApp.fetch(wbApiUrl, options);
    const responseCode = response.getResponseCode();
    
    // Проверяем 401 ошибку
    if (responseCode === 401) {
      const errorMsg = `API Wildberries вернул 401 для кабинета ${accountName}. Токен недействителен или истек срок действия.`;
      const detailedError = new Error(errorMsg);
      handle401Error(detailedError, SCRIPT_NAME_WB); // Передаем имя скрипта
      throw detailedError;
    }
    
    if (responseCode !== 200) {
      throw new Error(`Ошибка API ${accountName}: ${responseCode}`);
    }
    
    const data = JSON.parse(response.getContentText());
    
    if (!data.data || !data.data.listGoods || !Array.isArray(data.data.listGoods)) {
      throw new Error(`Неверный формат ответа от API ${accountName}`);
    }
    
    console.log(`      📦 PricesWb: ${accountName} - ${data.data.listGoods.length} товаров`);
    
    // Обрабатываем данные
    for (let i = 0; i < data.data.listGoods.length; i++) {
      const item = data.data.listGoods[i];
      results.nmID.push([item.nmID]);
      results.vendorCode.push([item.vendorCode]);
      results.price.push([item.sizes && item.sizes.length > 0 ? item.sizes[0].price : 0]);
      results.discount.push([item.discount || 0]);
      results.account.push([accountName]);
    }
    
    return results;
    
  } catch (error) {
    console.error(`      💥 PricesWb: Ошибка для ${accountName}:`, error);
    
    // Дополнительная проверка на текстовые ошибки авторизации
    if (error.toString().includes('401') || 
        error.toString().toLowerCase().includes('unauthorized') ||
        error.toString().toLowerCase().includes('not authorized')) {
      handle401Error(error, SCRIPT_NAME_WB); // Передаем имя скрипта
    }
    
    throw error;
  }
}

/**
 * Запись данных в таблицу в компактном формате (начиная с колонки A)
 */
function writeWbPricesDataToSheet(data) {
  console.log("   📝 PricesWb: Запись данных в таблицу...");
  
  // Подготовка данных для компактной записи
  const compactData = [];
  for (let i = 0; i < data.nmID.length; i++) {
    compactData.push([
      data.nmID[i][0],      // Колонка A - nmID
      data.vendorCode[i][0], // Колонка B - vendorCode  
      data.account[i][0],    // Колонка C - кабинет
      data.price[i][0],      // Колонка D - цена
      data.discount[i][0] / 100 // Колонка E - скидка (деленная на 100)
    ]);
  }
  
  // Очистка старых данных (колонки A-E начиная с строки 5)
  const lastRow = sheetWbPriceListPricesWb.getLastRow();
  if (lastRow > 4) {
    sheetWbPriceListPricesWb.getRange(5, 1, lastRow - 4, 5).clearContent();
  }
  
  // Запись заголовка
  sheetWbPriceListPricesWb.getRange(1, 1).setValue(`📅 ${formattedDatePricesWb} ⏰ ${formattedTimePricesWb} | Два кабинета`);
  
  // Установка заголовков колонок если нужно
  const headers = sheetWbPriceListPricesWb.getRange(4, 1, 1, 5).getValues()[0];
  if (!headers[0] || headers[0] === "") {
    sheetWbPriceListPricesWb.getRange(4, 1, 1, 5).setValues([["nmID", "Артикул", "Кабинет", "Цена", "Скидка %"]]);
  }
  
  // Запись данных
  if (compactData.length > 0) {
    sheetWbPriceListPricesWb.getRange(5, 1, compactData.length, 5).setValues(compactData);
    
    // Форматирование числовых колонок
    sheetWbPriceListPricesWb.getRange(5, 4, compactData.length, 1) // Колонка D - цена
      .setNumberFormat("#,##0.00");
    sheetWbPriceListPricesWb.getRange(5, 5, compactData.length, 1) // Колонка E - скидка
      .setNumberFormat("0%");
  }
  
  console.log(`      ✅ PricesWb: Записано ${compactData.length} строк в колонки A-E`);
}

/**
 * Расширенная версия с пагинацией для большого количества товаров
 */
function getWbPricesMultiAccountEnhanced() {
  console.log("🔄 PricesWb Enhanced: Начало получения ВСЕХ цен для двух кабинетов...");
  
  try {
    // Получаем все данные из обоих кабинетов (с пагинацией)
    const dataOoo = getWbPricesAllDataFromApi(optionsGetOooPricesWb, "ООО");
    const dataIp = getWbPricesAllDataFromApi(optionsGetIpPricesWb, "ИП");
    
    // Объединяем данные
    const allResults = {
      nmID: [...dataOoo.nmID, ...dataIp.nmID],
      vendorCode: [...dataOoo.vendorCode, ...dataIp.vendorCode],
      price: [...dataOoo.price, ...dataIp.price],
      discount: [...dataOoo.discount, ...dataIp.discount],
      account: [...dataOoo.account, ...dataIp.account]
    };
    
    console.log(`📊 PricesWb Enhanced: Итого - ООО: ${dataOoo.nmID.length}, ИП: ${dataIp.nmID.length}, Всего: ${allResults.nmID.length}`);
    
    // Записываем данные
    writeWbPricesDataToSheet(allResults);
    
    console.log("✅ PricesWb Enhanced: Все цены успешно обновлены!");
    toastMessageTitle(`Обновлено ВСЕ: ООО - ${dataOoo.nmID.length}, ИП - ${dataIp.nmID.length} товаров`, "✅ PricesWb Enhanced");
    
  } catch (error) {
    console.error("💥 PricesWb Enhanced: Ошибка:", error);
    
    // Обработка ошибок авторизации
    if (error.toString().includes('401') || 
        error.toString().toLowerCase().includes('unauthorized')) {
      handle401Error(error, SCRIPT_NAME_WB); // Передаем имя скрипта
    }
    
    toastMessageTitle(`Ошибка Enhanced: ${error.message}`, "❌ PricesWb Enhanced Ошибка");
    throw error;
  }
}

/**
 * Получение ВСЕХ данных с пагинацией
 */
function getWbPricesAllDataFromApi(options, accountName) {
  console.log(`   🔍 PricesWb: Получение ВСЕХ данных для ${accountName}...`);
  
  const allResults = {
    nmID: [],
    vendorCode: [],
    price: [],
    discount: [],
    account: []
  };
  
  let offset = 0;
  const limit = 1000;
  let hasMoreData = true;
  let totalItems = 0;
  
  while (hasMoreData) {
    try {
      console.log(`      📥 PricesWb: ${accountName} - батч со смещением ${offset}`);
      
      const wbApiUrl = `https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter?limit=${limit}&offset=${offset}`;
      const response = UrlFetchApp.fetch(wbApiUrl, options);
      const responseCode = response.getResponseCode();
      
      // Проверяем 401 ошибку
      if (responseCode === 401) {
        const errorMsg = `API Wildberries вернул 401 для кабинета ${accountName} при пагинации.`;
        const detailedError = new Error(errorMsg);
        handle401Error(detailedError, SCRIPT_NAME_WB); // Передаем имя скрипта
        throw detailedError;
      }
      
      if (responseCode !== 200) {
        throw new Error(`Ошибка API ${accountName}: ${responseCode}`);
      }
      
      const data = JSON.parse(response.getContentText());
      
      if (!data.data || !data.data.listGoods) {
        break;
      }
      
      const currentBatch = data.data.listGoods;
      console.log(`         📦 Получено: ${currentBatch.length} товаров`);
      
      // Обрабатываем текущий батч
      for (let i = 0; i < currentBatch.length; i++) {
        const item = currentBatch[i];
        allResults.nmID.push([item.nmID]);
        allResults.vendorCode.push([item.vendorCode]);
        allResults.price.push([item.sizes && item.sizes.length > 0 ? item.sizes[0].price : 0]);
        allResults.discount.push([item.discount || 0]);
        allResults.account.push([accountName]);
      }
      
      totalItems += currentBatch.length;
      
      // Проверяем, есть ли еще данные
      if (currentBatch.length < limit) {
        hasMoreData = false;
        console.log(`      ✅ PricesWb: ${accountName} - все данные получены (${totalItems} товаров)`);
      } else {
        offset += limit;
        Utilities.sleep(500); // Пауза между запросами
      }
      
    } catch (error) {
      console.error(`      💥 PricesWb: Ошибка в батче ${accountName}:`, error);
      
      // Проверяем ошибки авторизации
      if (error.toString().includes('401') || 
          error.toString().toLowerCase().includes('unauthorized')) {
        handle401Error(error, SCRIPT_NAME_WB); // Передаем имя скрипта
      }
      
      throw error;
    }
  }
  
  return allResults;
}

/**
 * Функция для получения цен только по одному кабинету (для обратной совместимости)
 */
function getWbPricesSingleAccount(accountType = "ИП") {
  console.log(`🔄 PricesWb Single: Получение цен для кабинета ${accountType}...`);
  
  try {
    const options = accountType === "ООО" ? optionsGetOooPricesWb : optionsGetIpPricesWb;
    const data = getWbPricesDataFromApi(options, accountType);
    
    writeWbPricesDataToSheet(data);
    
    console.log(`✅ PricesWb Single: Цены для ${accountType} успешно обновлены!`);
    toastMessageTitle(`Обновлено: ${accountType} - ${data.nmID.length} товаров`, "✅ PricesWb Single");
    
  } catch (error) {
    console.error(`💥 PricesWb Single: Ошибка для ${accountType}:`, error);
    
    // Проверка ошибок авторизации
    if (error.toString().includes('401') || 
        error.toString().toLowerCase().includes('unauthorized')) {
      handle401Error(error, SCRIPT_NAME_WB); // Передаем имя скрипта
    }
    
    toastMessageTitle(`Ошибка Single: ${error.message}`, "❌ PricesWb Single Ошибка");
    throw error;
  }
}

/**
 * Тестирование подключения к кабинетам
 */
function testWbPricesConnections() {
  console.log("🔍 PricesWb: Тестирование подключений к кабинетам...");
  
  try {
    // Тестируем ООО
    console.log("   🔐 Тестируем кабинет ООО...");
    const testUrl = "https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter?limit=1";
    const responseOoo = UrlFetchApp.fetch(testUrl, optionsGetOooPricesWb);
    const responseCodeOoo = responseOoo.getResponseCode();
    
    // Проверяем 401
    if (responseCodeOoo === 401) {
      const error = new Error(`ООО: API Wildberries вернул 401. Токен недействителен.`);
      handle401Error(error, SCRIPT_NAME_WB); // Передаем имя скрипта
      throw error;
    }
    
    if (responseCodeOoo === 200) {
      console.log("      ✅ ООО: подключение успешно");
    } else {
      throw new Error(`ООО: ошибка ${responseCodeOoo}`);
    }
    
    // Тестируем ИП
    console.log("   🔐 Тестируем кабинет ИП...");
    const responseIp = UrlFetchApp.fetch(testUrl, optionsGetIpPricesWb);
    const responseCodeIp = responseIp.getResponseCode();
    
    // Проверяем 401
    if (responseCodeIp === 401) {
      const error = new Error(`ИП: API Wildberries вернул 401. Токен недействителен.`);
      handle401Error(error, SCRIPT_NAME_WB); // Передаем имя скрипта
      throw error;
    }
    
    if (responseCodeIp === 200) {
      console.log("      ✅ ИП: подключение успешно");
    } else {
      throw new Error(`ИП: ошибка ${responseCodeIp}`);
    }
    
    console.log("✅ PricesWb: Оба кабинета работают корректно!");
    toastMessageTitle("Оба кабинета работают корректно!", "✅ PricesWb Тест");
    
  } catch (error) {
    console.error("💥 PricesWb: Ошибка тестирования:", error);
    
    // Дополнительная проверка для любых ошибок авторизации
    if (error.toString().includes('401') || 
        error.toString().toLowerCase().includes('unauthorized')) {
      handle401Error(error, SCRIPT_NAME_WB); // Передаем имя скрипта
    }
    
    toastMessageTitle(`Ошибка теста: ${error.message}`, "❌ PricesWb Тест");
    throw error;
  }
}

/**
 * Проверяет ошибку на 401 и отправляет уведомление для скрипта PricesWb
 * @param {Error} error - Объект ошибки
 */
function checkAndHandle401ErrorPricesWb(error) {
  const errorStr = error.toString();
  if (errorStr.includes('401') || 
      errorStr.includes('Unauthorized') ||
      errorStr.includes('Not authorized')) {
    handle401Error(error, SCRIPT_NAME_WB);
  }
}