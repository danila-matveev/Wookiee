// =========== УНИВЕРСАЛЬНЫЙ СКРИПТ ДЛЯ МОЙСКЛАД =========== //

// Глобальные переменные
const sheetMoySklad = activeSpreadsheet.getSheetByName("МойСклад_АПИ");
const ACCESS_TOKEN = PropertiesService.getScriptProperties().getProperty("MOYSKLAD_TOKEN");




// === НАСТРОЙКИ ЗАЩИТЫ ОТ 401 ОШИБКИ ===
const SCRIPT_NAME_MS = 'Скрипт обновления МойСклад (лист МойСклад_АПИ)';


// Конфигурация
const CONFIG = {
  stores: {
    main: "4c51ead2-2731-11ef-0a80-07b100450c6a",
    office: "4c51ead2-2731-11ef-0a80-07b100450c6a",
    acceptance: "6281f079-8ae2-11ef-0a80-148c00124916"
  },
  attributesOrder: [
    'Артикул Ozon', 'Баркод', 'Нуменклатура', 'Модель', 'Название для Этикетки', 'Ozon >>',
    'Ozon Product ID', 'FBO OZON SKU ID', 'Размер', 'Цвет',
    'О товаре >>>', 'Продавец', 'Фабрика', 'Состав', 'ТНВЭД', 'SKU', 'Сolor',
    'Color code', 'Price', 'Длина', 'Ширина', 'Высота', 'Объем', 'Кратность короба',
    'Импортер', 'Адрес Импортера', 'Статус WB', 'Статус OZON', 'Склейка на WB',
    'Категория', 'Модель основа', 'Коллекция'
  ],
  maxAttempts: 10,
  delayBetweenRequests: 1000,
  additionalColumns: ['Остатки в офисе', 'Товары с приемкой', 'Товары в пути', 'Себестоимость'],
  maxRowsPerRequest: 500,
  timeout: 300000,
  // Фиксированные позиции для дополнительных колонок
  additionalColumnsStart: 39 // Укажите номер колонки, с которой начинаются дополнительные данные
};

// ===== ОСНОВНЫЕ ФУНКЦИИ ===== //

function moySklad_fetchMetadataCurrentHourStart() {
  const formattedDateMS = getCurrentFormattedDate();
  Logger.log(`Запуск скрипта: ${formattedDateMS}`);
  
  try {
    moySklad_fetchMetadata(formattedDateMS);
  } catch (error) {
    // Дополнительная обработка ошибок на верхнем уровне
    const errorStr = error.toString();
    if (errorStr.includes('401') || 
        errorStr.includes('Unauthorized') ||
        errorStr.includes('Not authorized')) {
      handle401Error(error, SCRIPT_NAME_MS); // Передаем SCRIPT_NAME_MS
    }
    throw error;
  }
}

function moySklad_fetchMetadata(date = null) {
  const formattedDate = date || getDefaultFormattedDate();

  try {
    toastMessageTitle("Начинаем выгрузку данных из МойСклад", "Запуск");

    // Получаем основные данные товаров
    const assortmentData = fetchAllAssortmentData(formattedDate);
    console.log(`Получено товаров: ${assortmentData.length}`);

    if (assortmentData.length === 0) {
      alertMessage("Не получены данные из МойСклад. Проверьте настройки API.");
      return;
    }

    // Обрабатываем и записываем данные
    processAndWriteData(assortmentData, formattedDate);

    toastMessageTitle(`Обработано ${assortmentData.length} товаров`, "Завершено");

  } catch (error) {
    console.error("Ошибка в основной функции:", error);
    
    // Проверяем 401 ошибку с передачей SCRIPT_NAME_MS
    const errorStr = error.toString();
    if (errorStr.includes('401') || 
        errorStr.includes('Unauthorized') ||
        errorStr.includes('Not authorized')) {
      handle401Error(error, SCRIPT_NAME_MS); // Передаем SCRIPT_NAME_MS
    }
    
    alertMessage(`Ошибка выполнения: ${error.message}`);
  }
}

// ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===== //

function getCurrentFormattedDate() {
  const now = new Date();
  now.setUTCHours(now.getUTCHours());
  return Utilities.formatDate(now, "GMT+3", "yyyy-MM-dd HH:mm:ss");
}

function getDefaultFormattedDate() {
  const now = new Date();
  now.setHours(5, 0, 0, 0);
  return Utilities.formatDate(now, "GMT+3", "yyyy-MM-dd HH:mm:ss");
}

function getApiHeaders() {
  return {
    "Authorization": `Bearer ${ACCESS_TOKEN}`,
    "Accept-Encoding": "gzip"
  };
}

function makeApiRequest(url) {
  const options = {
    method: "get",
    headers: getApiHeaders(),
    muteHttpExceptions: true,
    timeout: CONFIG.timeout
  };

  try {
    const response = UrlFetchApp.fetch(url, options);

    if (response.getResponseCode() === 200) {
      try {
        return JSON.parse(response.getContentText());
      } catch (jsonError) {
        console.error(`JSON Parse Error: ${jsonError}`);
        console.error(`Response length: ${response.getContentText().length}`);

        const fixedJson = tryFixJson(response.getContentText());
        if (fixedJson) {
          return JSON.parse(fixedJson);
        }

        throw new Error(`Невалидный JSON в ответе: ${jsonError.message}`);
      }
    } else {
      console.error(`API Error ${response.getResponseCode()}: ${response.getContentText()}`);

      // Обрабатываем ошибку 401 с передачей SCRIPT_NAME_MS
      if (response.getResponseCode() === 401) {
        const errorMsg = `API МойСклад вернул 401. Токен недействителен или истек срок действия.`;
        const detailedError = new Error(`${errorMsg} Ответ API: ${response.getContentText()}`);
        handle401Error(detailedError, SCRIPT_NAME_MS); // Передаем SCRIPT_NAME_MS
      }
      return null;
    }
  } catch (error) {
    console.error(`Request failed: ${error}`);
    
    // Проверяем ошибки сети, которые могут указывать на проблемы с авторизацией
    if (error.toString().includes('401') || 
        error.toString().toLowerCase().includes('unauthorized')) {
      handle401Error(error, SCRIPT_NAME_MS); // Передаем SCRIPT_NAME_MS
    }
    return null;
  }
}

function tryFixJson(jsonString) {
  try {
    let fixed = jsonString;
    let openQuotes = 0;

    for (let i = 0; i < fixed.length; i++) {
      if (fixed[i] === '"' && fixed[i - 1] !== '\\') {
        openQuotes++;
      }
    }

    if (openQuotes % 2 !== 0) {
      fixed += '"';
    }

    JSON.parse(fixed);
    console.log("JSON успешно исправлен");
    return fixed;

  } catch (fixError) {
    console.error("Не удалось исправить JSON:", fixError);
    return null;
  }
}


function fetchAllAssortmentData(formattedDate, storeId = "") {
  let allRows = [];
  let offset = 0;
  let hasMore = true;
  let attempt = 0;

  while (hasMore && attempt < CONFIG.maxAttempts) {
    let url = "";

    if (storeId) {
      if (storeId.includes(';')) {
        const storeIds = storeId.split(';');
        const storeFilters = storeIds.map(id =>
          `stockStore=https://api.moysklad.ru/api/remap/1.2/entity/store/${id}`
        ).join(';');
        url = `https://api.moysklad.ru/api/remap/1.2/entity/assortment?filter=${storeFilters};stockMoment=${formattedDate}&offset=${offset}&limit=${CONFIG.maxRowsPerRequest}`;
      } else {
        url = `https://api.moysklad.ru/api/remap/1.2/entity/assortment?filter=stockStore=https://api.moysklad.ru/api/remap/1.2/entity/store/${storeId};stockMoment=${formattedDate}&offset=${offset}&limit=${CONFIG.maxRowsPerRequest}`;
      }
    } else {
      url = `https://api.moysklad.ru/api/remap/1.2/entity/assortment?filter=stockMoment=${formattedDate}&offset=${offset}&limit=${CONFIG.maxRowsPerRequest}`;
    }

    console.log(`Fetching URL: ${url}`);

    const data = makeApiRequest(url);
    if (!data || !data.rows) {
      console.log("Не удалось получить данные, пропускаем этот запрос");
      break;
    }

    allRows = allRows.concat(data.rows);
    console.log(`Получено ${data.rows.length} записей, всего: ${allRows.length}`);

    if (data.rows.length < CONFIG.maxRowsPerRequest) {
      hasMore = false;
    } else {
      offset += CONFIG.maxRowsPerRequest;
      attempt++;
      Utilities.sleep(CONFIG.delayBetweenRequests);
    }
  }

  return allRows;
}

function fetchStockDataWithRetry(formattedDate, storeId, maxRetries = 3) {
  for (let retry = 0; retry < maxRetries; retry++) {
    try {
      console.log(`Попытка ${retry + 1} получить данные склада ${storeId}`);
      const data = fetchAllAssortmentData(formattedDate, storeId);

      if (data && data.length > 0) {
        return data;
      }

      if (retry < maxRetries - 1) {
        console.log(`Повторная попытка через ${(retry + 1) * 5} секунд...`);
        Utilities.sleep((retry + 1) * 5000);
      }
    } catch (error) {
      console.error(`Ошибка при попытке ${retry + 1}:`, error);
      if (retry < maxRetries - 1) {
        Utilities.sleep((retry + 1) * 5000);
      }
    }
  }

  console.log(`Не удалось получить данные склада ${storeId} после ${maxRetries} попыток`);
  return [];
}

function processAndWriteData(assortmentRows, formattedDate) {
  // Обрабатываем основные данные
  const processedData = processAssortmentRows(assortmentRows);

  // Очищаем лист (включая дополнительные колонки)
  clearSheetData();

  // Записываем основные данные
  writeMainData(processedData, formattedDate);

  // Получаем и записываем дополнительные данные в фиксированные колонки
  if (processedData.length > 0) {
    const productIds = processedData.map(row => row[1]); // ИЗМЕНЕНО: берем ID из колонки B (индекс 1)
    writeAdditionalData(productIds, formattedDate);
  }
}

function processAssortmentRows(rows) {
  const result = [];

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];

    // Обрабатываем все товары без фильтрации по продавцу
    if (row.attributes && row.barcodes && row.barcodes.length > 1) {
      const processedRow = processSingleRow(row);
      if (processedRow) {
        result.push(processedRow);
      }
    }
  }

  return result;
}

function processSingleRow(row) {
  try {
    const attributeValues = extractAttributeValues(row.attributes);
    const barcodeData = extractBarcodeData(row.barcodes);
    const additionalData = getAdditionalRowData(row);

    const processedRow = [
      attributeValues[0],  // Артикул Ozon (колонка A)
      row.id,              // ID товара (колонка B) - ВАЖНО: теперь это колонка B!
      attributeValues[1],  // Баркод (атрибут) (колонка C)
      barcodeData[0],      // Баркод 1 (API) (колонка D)
      barcodeData[1],      // Баркод 2 (API) (колонка E)
      attributeValues[2],  // Нуменклатура (колонка F)
      row.article,         // Артикул (колонка G)
      attributeValues[3],  // Модель (колонка H)
      attributeValues[4],  // Название для Этикетки (колонка I)
      attributeValues[5],  // Ozon >> (колонка J)     
      attributeValues[0],  // Артикул Ozon (дублируется - колонка K)
      attributeValues[6],  // Ozon Product ID (колонка L)
      attributeValues[7],  // FBO OZON SKU ID (колонка M)
      attributeValues[8],  // Размер (колонка N)
      attributeValues[9],  // Цвет (колонка O)
      attributeValues[10], // О товаре >>> (колонка P)
      attributeValues[11], // Продавец (колонка Q)
      attributeValues[12], // Фабрика (колонка R)
      attributeValues[13], // Состав (колонка S)
      attributeValues[14], // ТНВЭД (колонка T)
      attributeValues[15], // SKU (колонка U)
      attributeValues[16], // Сolor (колонка V)
      attributeValues[17], // Color code (колонка W)
      normalizePrice(attributeValues[18]), // Price (колонка X)
      additionalData[0],   // Вес (колонка Y)
      attributeValues[19], // Длина (колонка Z)
      attributeValues[20], // Ширина (колонка AA) 
      attributeValues[21], // Высота (колонка AB)
      attributeValues[22], // Объем (колонка AC)
      attributeValues[23], // Кратность короба (колонка AD)
      attributeValues[24], // Импортер (колонка AE)
      attributeValues[25], // Адрес Импортера (колонка AF)
      attributeValues[26], // Статус WB (колонка AG)
      attributeValues[27], // Статус OZON (колонка AH)
      attributeValues[28], // Склейка на WB (колонка AI)
      attributeValues[29], // Категория (колонка AJ)
      attributeValues[30], // Модель основа (колонка AK)
      attributeValues[31]  // Коллекция (колонка AL)
    ];

    return processedRow;

  } catch (error) {
    console.error("Ошибка обработки строки:", error, row);
    return null;
  }
}

// Новая функция для нормализации цены
function normalizePrice(priceValue) {
  if (priceValue === null || priceValue === undefined) {
    return "0,00";
  }
  
  const priceStr = String(priceValue);
  
  // Удаляем символы валют и пробелы
  let cleanedPrice = priceStr.replace(/[¥€$₽\s]/g, '');
  
  // Заменяем запятые на точки для корректного парсинга
  cleanedPrice = cleanedPrice.replace(',', '.');
  
  // Парсим в число
  const priceNumber = parseFloat(cleanedPrice);
  
  // Возвращаем в формате с запятой
  return !isNaN(priceNumber) ? priceNumber.toFixed(2).replace('.', ',') : "0,00";
}

function extractAttributeValues(attributes) {
  return CONFIG.attributesOrder.map(attrName => {
    const attribute = attributes.find(attr => attr.name === attrName);
    return attribute ? attribute.value : null;
  });
}

function extractBarcodeData(barcodes) {
  const barcodeData = [barcodes[1] ? barcodes[1].ean13 : ""];
  barcodeData.push(barcodes[2] ? barcodes[2].gtin : "");
  return barcodeData;
}

function getAdditionalRowData(row) {
  return [row.weight || 0];
}

function clearSheetData() {
  const lastRow = sheetMoySklad.getLastRow();
  if (lastRow >= 3) {
    // Очищаем ВСЕ данные, включая дополнительные колонки
    const totalColumns = Math.max(sheetMoySklad.getLastColumn(), CONFIG.additionalColumnsStart + CONFIG.additionalColumns.length - 1);
    sheetMoySklad.getRange(3, 1, lastRow - 2, totalColumns).clearContent();
  }
  
  // Также очищаем заголовки дополнительных колонок
  const headerRange = sheetMoySklad.getRange(2, CONFIG.additionalColumnsStart, 1, CONFIG.additionalColumns.length);
  headerRange.clearContent();
}

function getMainDataColumnsCount() {
  // Количество колонок в основных данных
  return 34; // 34 основные колонки (A-AL)
}

function writeMainData(data, formattedDate) {
  if (data.length > 0) {
    sheetMoySklad.getRange(3, 1, data.length, data[0].length).setValues(data);
    sheetMoySklad.getRange('A1').setValue(formattedDate);
    console.log(`Записано основных данных: ${data.length} строк, ${data[0].length} колонок`);
  }
}

function writeAdditionalData(productIds, formattedDate) {
  const startColumn = CONFIG.additionalColumnsStart;
  
  console.log(`Запись дополнительных данных в колонки: ${startColumn}-${startColumn + 3}`);
  console.log(`Количество productIds для поиска: ${productIds.length}`);

  // Записываем заголовки дополнительных колонок
  writeAdditionalHeaders(startColumn);

  console.log("Получение остатков в офисе...");
  const officeStock = fetchStockDataWithRetry(formattedDate, CONFIG.stores.office);
  console.log(`Найдено товаров в офисе: ${officeStock.length}`);
  const officeData = mapProductsToIds(productIds, officeStock, 'quantity');
  writeColumnData(officeData, startColumn);

  console.log("Получение товаров с приемкой...");
  try {
    const acceptanceStock = fetchStockDataWithRetry(formattedDate, `${CONFIG.stores.acceptance};${CONFIG.stores.main}`);
    console.log(`Найдено товаров с приемкой: ${acceptanceStock.length}`);
    const acceptanceData = mapProductsToIds(productIds, acceptanceStock, 'stock');
    writeColumnData(acceptanceData, startColumn + 1);
  } catch (error) {
    console.error("Ошибка при получении товаров с приемкой:", error);
    const emptyData = productIds.map(() => [0]);
    writeColumnData(emptyData, startColumn + 1);
  }

  console.log("Получение товаров в пути...");
  const ordersInTransit = fetchOrdersInTransit();
  console.log(`Найдено заказов в пути: ${ordersInTransit.length}`);
  const transitData = mapOrdersToIds(productIds, ordersInTransit);
  writeColumnData(transitData, startColumn + 2);

  console.log("Получение себестоимости...");
  const costData = fetchCostData();
  console.log(`Найдено данных себестоимости: ${costData.length}`);
  writeColumnData(costData, startColumn + 3);
}

function writeAdditionalHeaders(startColumn) {
  const headers = CONFIG.additionalColumns;
  const headerRange = sheetMoySklad.getRange(2, startColumn, 1, headers.length);
  headerRange.setValues([headers]);
  headerRange.setBackground("#e6e6e6").setFontWeight("bold");
  console.log(`Записаны заголовки дополнительных колонок: ${headers.join(', ')}`);
}

function fetchStockData(formattedDate, storeId) {
  return fetchAllAssortmentData(formattedDate, storeId);
}

function fetchCostData() {
  const url = "https://api.moysklad.ru/api/remap/1.2/report/stock/all";
  const data = makeApiRequest(url);

  if (data && data.rows) {
    const productIds = getProductIdsFromSheet();
    console.log(`Поиск себестоимости для ${productIds.length} товаров`);
    return mapProductsToIds(productIds, data.rows, 'price', true);
  }
  return [];
}

function fetchOrdersInTransit() {
  const url = "https://api.moysklad.ru/api/remap/1.2/entity/purchaseorder";
  const data = makeApiRequest(url);

  if (!data || !data.rows) return [];

  const activeOrders = data.rows.filter(order =>
    order.state && order.state.meta.href !== "https://api.moysklad.ru/api/remap/1.2/entity/purchaseorder/metadata/states/75199f67-2f9f-11ef-0a80-02fb00081527"
  );

  console.log(`Найдено активных заказов: ${activeOrders.length}`);

  const allPositions = [];
  for (const order of activeOrders) {
    const positions = fetchOrderPositions(order.id);
    if (positions) allPositions.push(positions);
    Utilities.sleep(500);
  }

  return allPositions;
}

function fetchOrderPositions(orderId) {
  const url = `https://api.moysklad.ru/api/remap/1.2/entity/purchaseorder/${orderId}/positions`;
  return makeApiRequest(url);
}

function mapProductsToIds(productIds, data, field, isCost = false) {
  console.log(`Сопоставление ${productIds.length} ID с ${data.length} записями, поле: ${field}`);
  
  const result = productIds.map(id => {
    const product = data.find(item => {
      const itemHref = item.meta?.href;
      if (!itemHref) return false;

      const itemId = itemHref.split('/').pop().split('?')[0];
      return itemId === id;
    });

    if (!product) {
      console.log(`Не найден товар с ID: ${id}`);
      return [0];
    }

    if (product[field] === undefined || product[field] === null) {
      console.log(`Товар ${id} не имеет значения для поля ${field}`);
      return [0];
    }

    if (isCost) {
      const cost = (Math.floor(product[field]) / 100).toFixed(2).replace('.', ',');
      console.log(`Себестоимость для ${id}: ${cost}`);
      return [cost];
    }

    console.log(`Значение для ${id} (${field}): ${product[field]}`);
    return [product[field]];
  });

  // Подсчет ненулевых значений для отладки
  const nonZeroCount = result.filter(val => val[0] !== 0).length;
  console.log(`Ненулевых значений: ${nonZeroCount} из ${result.length}`);
  
  return result;
}

function mapOrdersToIds(productIds, ordersData) {
  const quantities = {};
  productIds.forEach(id => quantities[id] = 0);

  ordersData.forEach(order => {
    if (order && order.rows) {
      order.rows.forEach(row => {
        if (row.assortment && row.assortment.meta && row.assortment.meta.href) {
          const id = row.assortment.meta.href.split('/').pop();
          if (quantities.hasOwnProperty(id)) {
            quantities[id] += row.quantity || 0;
          }
        }
      });
    }
  });

  // Логирование для отладки
  const nonZeroOrders = Object.entries(quantities).filter(([id, qty]) => qty > 0);
  console.log(`Товаров в заказах: ${nonZeroOrders.length} из ${productIds.length}`);

  return productIds.map(id => [quantities[id]]);
}

function getProductIdsFromSheet() {
  const lastRow = sheetMoySklad.getLastRow();
  if (lastRow < 3) return [];
  
  // ИЗМЕНЕНО: берем ID из колонки B (индекс 1 в массиве, но колонка 2 в таблице)
  const ids = sheetMoySklad.getRange(3, 2, lastRow - 2, 1).getValues().flat();
  const validIds = ids.filter(id => id && id !== '');
  console.log(`Получено ID из листа: ${validIds.length} из ${ids.length}`);
  return validIds;
}

function writeColumnData(data, column) {
  if (data.length > 0) {
    sheetMoySklad.getRange(3, column, data.length, 1).setValues(data);
    
    // Подсчет ненулевых значений для отладки
    const nonZeroCount = data.filter(val => val[0] !== 0).length;
    console.log(`Записано данных в колонку ${column}: ${data.length} строк, ненулевых: ${nonZeroCount}`);
  }
}


// ===== ТЕСТИРОВАНИЕ ===== //

function testScript() {
  console.log("Запуск тестовой версии скрипта...");
  moySklad_fetchMetadataCurrentHourStart();
}