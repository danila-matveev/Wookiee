// ====== Глобальные переменные =====//
let sheetArticulAnalytics = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Аналитика по запросам (поартикульно)");

// ====== КОНФИГУРАЦИЯ ЛИМИТОВ ====== //
const LIMIT_CONFIG_ARTICUL = {
  OOO: 100,
  IP: 30
};

// ====== ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА ====== //
function executeArticulAnalysis() {
  console.log("=== АНАЛИЗ ПО АРТИКУЛАМ ===");
  
  const dates = getDatesFromArticulSheet();
  if (!dates) return;
  
  console.log("Период:", dates.displayStart, "-", dates.displayEnd);
  
  // Очищаем старые данные
  clearOldData();
  
  // Анализируем с разными лимитами
  console.log(`\n=== АНАЛИЗ ДЛЯ ООО (лимит: ${LIMIT_CONFIG_ARTICUL.OOO}) ===`);
  const oooResults = analyzeArticulForCabinet(apiKeyOOO, dates, "ООО", LIMIT_CONFIG_ARTICUL.OOO);
  
  console.log(`\n=== АНАЛИЗ ДЛЯ ИП (лимит: ${LIMIT_CONFIG_ARTICUL.IP}) ===`);
  const ipResults = analyzeArticulForCabinet(apiKeyIP, dates, "ИП", LIMIT_CONFIG_ARTICUL.IP);
  
  // Объединяем и записываем результаты
  const allResults = [...oooResults, ...ipResults];
  writeArticulResults(allResults, dates);
  
  console.log("\n✅ Все данные записаны в таблицу!");
}

// ====== РАБОТА С ДАТАМИ ====== //
function getDatesFromArticulSheet() {
  try {
    const startDateStr = sheetArticulAnalytics.getRange("A2").getDisplayValue();
    const endDateStr = sheetArticulAnalytics.getRange("B2").getDisplayValue();

    if (!startDateStr || !endDateStr) {
      console.log("❌ Даты в ячейках A2 и B2 не заполнены");
      return null;
    }

    console.log("📅 Даты из таблицы:", { startDateStr, endDateStr });
    return formatDatesForArticul(startDateStr, endDateStr);
  } catch (error) {
    console.log("❌ Ошибка получения дат:", error.message);
    return null;
  }
}

function formatDatesForArticul(startDateStr, endDateStr) {
  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    const [day, month, year] = dateStr.split('.');
    const date = new Date(year, month - 1, day);
    if (isNaN(date.getTime())) {
      throw new Error(`Неверный формат даты: ${dateStr}`);
    }
    return Utilities.formatDate(date, Session.getScriptTimeZone(), "yyyy-MM-dd");
  };

  return {
    start: formatDate(startDateStr),
    end: formatDate(endDateStr),
    displayStart: startDateStr,
    displayEnd: endDateStr
  };
}

// ====== ОЧИСТКА ДАННЫХ ====== //
function clearOldData() {
  const lastRow = sheetArticulAnalytics.getLastRow();
  if (lastRow >= 4) {
    sheetArticulAnalytics.getRange(4, 1, lastRow - 3, 10).clearContent();
    console.log(`✅ Очищены данные с строки 4 до ${lastRow}`);
  } else {
    console.log("✅ Нет старых данных для очистки");
  }
}

// ====== АНАЛИЗ ДЛЯ КАБИНЕТА ====== //
function analyzeArticulForCabinet(apiKey, dates, cabinetName, limit) {
  console.log(`Запрашиваем данные для кабинета: ${cabinetName} (лимит: ${limit})`);

  try {
    const options = createArticulRequestOptions(apiKey, dates, limit);
    const response = sendArticulRequest(options, cabinetName);

    if (response && response.length > 0) {
      console.log(`✅ Данные получены для ${cabinetName}`);
      console.log(`Найдено записей: ${response.length}`);
      
      // Добавляем информацию о кабинете к каждой записи
      const resultsWithCabinet = response.map(item => ({
        ...item,
        cabinet: cabinetName
      }));
      
      // Детальный вывод первых 3 записей для диагностики
      console.log("🔍 Первые 3 записи:");
      resultsWithCabinet.slice(0, 3).forEach((item, index) => {
        console.log(`   ${index + 1}. "${item.text}" → nmID: ${item.nmId}, Частота: ${item.frequency}, Переходы: ${item.openCard}`);
      });
      
      return resultsWithCabinet;
    } else {
      console.log(`❌ Нет данных для кабинета ${cabinetName}`);
      return [];
    }

  } catch (error) {
    console.log(`❌ Ошибка при запросе для ${cabinetName}:`, error.toString());
    return [];
  }
}

// ====== ЗАПРОС К API ====== //
function createArticulRequestOptions(apiKey, currentPeriod, limit) {
  const formData = {
    "currentPeriod": {
      "start": currentPeriod.start,
      "end": currentPeriod.end
    },
    "nmIds": [],
    "topOrderBy": "openCard",
    "includeSubstitutedSKUs": true,
    "includeSearchTexts": true,
    "orderBy": {
      "field": "visibility",
      "mode": "asc"
    },
    "limit": limit
  };

  return {
    "method": "POST",
    "muteHttpExceptions": true,
    "headers": {
      "Authorization": apiKey,
      "Content-Type": "application/json"
    },
    "payload": JSON.stringify(formData)
  };
}

function sendArticulRequest(options, cabinetName) {
  const wbApiURL = "https://seller-analytics-api.wildberries.ru/api/v2/search-report/product/search-texts";

  try {
    console.log(`Отправляем запрос для ${cabinetName}...`);
    const response = UrlFetchApp.fetch(wbApiURL, options);
    const responseCode = response.getResponseCode();

    if (responseCode !== 200) {
      console.log(`Ошибка API для ${cabinetName}:`, response.getContentText());
      return [];
    }

    const data = JSON.parse(response.getContentText());

    if (!data?.data?.items) {
      console.log(`Нет данных в ответе для ${cabinetName}`);
      return [];
    }

    console.log(`Получено элементов для ${cabinetName}: ${data.data.items.length}`);
    return transformArticulData(data.data.items);

  } catch (error) {
    console.log(`Ошибка при обработке ответа для ${cabinetName}:`, error.toString());
    return [];
  }
}

// ====== ТРАНСФОРМАЦИЯ ДАННЫХ ====== //
function transformArticulData(originalArray) {
  if (!Array.isArray(originalArray)) return [];

  return originalArray.map(function (item) {
    const frequency = typeof item.frequency === 'object' ?
      (item.frequency.current || item.frequency || 0) :
      (item.frequency || 0);

    const openCard = typeof item.openCard === 'object' ?
      (item.openCard.current || item.openCard || 0) :
      (item.openCard || 0);

    const addToCart = typeof item.addToCart === 'object' ?
      (item.addToCart.current || item.addToCart || 0) :
      (item.addToCart || 0);

    const orders = typeof item.orders === 'object' ?
      (item.orders.current || item.orders || 0) :
      (item.orders || 0);

    // Рассчитываем дополнительные метрики с проверкой деления на ноль
    const openToCart = openCard > 0 ? (addToCart / openCard) : 0;
    const cartToOrder = addToCart > 0 ? (orders / addToCart) : 0;

    return {
      text: item.text || "",
      nmId: item.nmId || 0,
      frequency: Number(frequency) || 0,
      openCard: Number(openCard) || 0,
      addToCart: Number(addToCart) || 0,
      orders: Number(orders) || 0,
      openToCart: openToCart,
      cartToOrder: cartToOrder
    };
  }).filter(item => item.text !== "");
}

// ====== ЗАПИСЬ РЕЗУЛЬТАТОВ (С ДОПОЛНИТЕЛЬНОЙ ПРОВЕРКОЙ) ====== //
function writeArticulResults(results, dates) {
  if (results.length === 0) {
    console.log("❌ Нет результатов для записи");
    return;
  }

  console.log(`\n💾 Записываем ${results.length} записей...`);

  // Подготавливаем данные для записи с проверкой числовых значений
  const dataToWrite = results.map(item => {
    // Проверяем и корректируем числовые значения
    const safeOpenToCart = isNaN(item.openToCart) || !isFinite(item.openToCart) ? 0 : item.openToCart;
    const safeCartToOrder = isNaN(item.cartToOrder) || !isFinite(item.cartToOrder) ? 0 : item.cartToOrder;
    
    return [
      item.text,                    // Колонка 1: Поисковый запрос
      item.nmId,                    // Колонка 2: nmId
      item.openCard,                // Колонка 3: openCard (переходы)
      item.addToCart,               // Колонка 4: addToCart (добавления)
      safeOpenToCart,               // Колонка 5: openToCart (конверсия переход→корзина)
      item.orders,                  // Колонка 6: orders (заказы)
      safeCartToOrder,              // Колонка 7: cartToOrder (конверсия корзина→заказ)
      dates.displayStart,           // Колонка 8: дата от
      dates.displayEnd,             // Колонка 9: дата до
      item.cabinet                  // Колонка 10: кабинет (ООО/ИП)
    ];
  });

  // Записываем данные начиная с строки 4
  if (dataToWrite.length > 0) {
    sheetArticulAnalytics.getRange(4, 1, dataToWrite.length, 10).setValues(dataToWrite);
    console.log(`✅ Записано ${dataToWrite.length} строк данных`);
    
    // Форматируем числовые колонки
    formatNumericColumns(dataToWrite.length);
  }
}

// ====== ФОРМАТИРОВАНИЕ КОЛОНОК ====== //
function formatNumericColumns(rowCount) {
  if (rowCount === 0) return;
  
  try {
    // Форматируем колонки с числами (колонки 3-7)
    const numberRange = sheetArticulAnalytics.getRange(4, 3, rowCount, 5);
    numberRange.setNumberFormat("0");
    
    // Форматируем колонки с конверсиями (колонки 5 и 7) как проценты
    const conversionRange1 = sheetArticulAnalytics.getRange(4, 5, rowCount, 1);
    const conversionRange2 = sheetArticulAnalytics.getRange(4, 7, rowCount, 1);
    conversionRange1.setNumberFormat("0.00%");
    conversionRange2.setNumberFormat("0.00%");
    
    console.log("✅ Числовые колонки отформатированы");
  } catch (error) {
    console.log("⚠️ Не удалось отформатировать числовые колонки:", error.message);
  }
}

// ====== ДОПОЛНИТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ РУЧНОГО ЗАПУСКА ====== //
function executeArticulAnalysisManual() {
  console.log("=== РУЧНОЙ ЗАПУСК АНАЛИЗА ПО АРТИКУЛАМ ===");
  
  const manualStartDate = "29.09.2025";
  const manualEndDate = "05.10.2025";
  
  const dates = formatDatesForArticul(manualStartDate, manualEndDate);
  
  // Очищаем старые данные
  clearOldData();
  
  // Анализируем с разными лимитами
  console.log(`\n=== АНАЛИЗ ДЛЯ ООО (лимит: ${LIMIT_CONFIG_ARTICUL.OOO}) ===`);
  const oooResults = analyzeArticulForCabinet(apiKeyOOO, dates, "ООО", LIMIT_CONFIG_ARTICUL.OOO);
  
  console.log(`\n=== АНАЛИЗ ДЛЯ ИП (лимит: ${LIMIT_CONFIG_ARTICUL.IP}) ===`);
  const ipResults = analyzeArticulForCabinet(apiKeyIP, dates, "ИП", LIMIT_CONFIG_ARTICUL.IP);
  
  // Объединяем и записываем результаты
  const allResults = [...oooResults, ...ipResults];
  writeArticulResults(allResults, dates);
  
  console.log("\n✅ Все данные записаны в таблицу!");
}