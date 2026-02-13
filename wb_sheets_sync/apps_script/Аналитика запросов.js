// ====== Глобальные переменные =====//
let sheetZaprosy; // Основной рабочий лист

// ====== КОНФИГУРАЦИЯ ЛИМИТОВ ====== //
const LIMIT_CONFIG = {
  OOO: 100,   // Лимит для ООО
  IP: 30      // Лимит для ИП
};

// ====== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ДЛЯ МАППИНГА ====== //
let _poiskovie_zaprosi_podmenMapping = null;

// ====== ТРИ ВАРИАНТА ЗАПУСКА ====== //

function letsGetPodmenArtikul() {
  // Инициализация листа
  if (!initializeSheet()) {
    console.error("❌ Невозможно выполнить функцию: лист не найден");
    return;
  }
  
  const startEndDates = getFormattedDatesForPodmenAPI('sheet');
  console.log("Даты получены из таблицы");
  executeSearchWordsAnalysis(startEndDates);
}

function letsGetPodmenArtikulManual() {
  // Инициализация листа
  if (!initializeSheet()) {
    console.error("❌ Невозможно выполнить функцию: лист не найден");
    return;
  }
  
  // ИЗМЕНИТЕ ЗДЕСЬ ДАТЫ НА НУЖНЫЕ
  const manualStartDate = "01.09.2025"; // Было "29.09.2025"
  const manualEndDate = "07.09.2025";   // Было "05.10.2025"
  const startEndDates = getFormattedDatesForPodmenAPI('manual', manualStartDate, manualEndDate);
  console.log("Даты получены из переменных");
  executeSearchWordsAnalysis(startEndDates);
}

function letsGetPodmenArtikulNextWeek() {
  // Инициализация листа
  if (!initializeSheet()) {
    console.error("❌ Невозможно выполнить функцию: лист не найден");
    return;
  }
  
  console.log("=== ЗАПУСК: СЛЕДУЮЩАЯ НЕДЕЛЯ ===");
  
  // 1. Находим самые правые даты в строке 2
  const lastColumn = sheetZaprosy.getLastColumn();
  console.log(`Последняя колонка в таблице: ${lastColumn}`);
  
  if (lastColumn < 4) {
    console.error("❌ В таблице недостаточно колонок");
    return;
  }
  
  // Ищем даты, начиная с последней колонки и двигаясь влево
  let foundDates = [];
  
  for (let col = lastColumn; col >= 1; col--) {
    const cellValue = sheetZaprosy.getRange(2, col).getDisplayValue();
    if (cellValue && cellValue.trim() !== "") {
      // Проверяем формат даты DD.MM.YYYY
      if (cellValue.match(/^\d{2}\.\d{2}\.\d{4}$/)) {
        foundDates.push({
          value: cellValue,
          column: col
        });
        
        if (foundDates.length === 2) {
          // Сортируем по колонкам (слева направо)
          foundDates.sort((a, b) => a.column - b.column);
          break;
        }
      }
    }
  }
  
  if (foundDates.length < 2) {
    // Альтернативный поиск: просто берем колонки lastColumn-3 и lastColumn-2
    console.log("Поиск по паттерну не дал результатов, используем альтернативный метод");
    const col1 = lastColumn - 3;
    const col2 = lastColumn - 2;
    
    if (col1 < 1 || col2 < 1) {
      console.error("❌ Не удалось найти колонки с датами");
      return;
    }
    
    foundDates = [
      { value: sheetZaprosy.getRange(2, col1).getDisplayValue(), column: col1 },
      { value: sheetZaprosy.getRange(2, col2).getDisplayValue(), column: col2 }
    ];
  }
  
  console.log(`Найдены даты: Колонка ${foundDates[0].column}: "${foundDates[0].value}", Колонка ${foundDates[1].column}: "${foundDates[1].value}"`);
  
  // 2. Преобразуем даты в объекты Date
  function parseDate(dateStr) {
    if (!dateStr || dateStr.trim() === "") return null;
    const [day, month, year] = dateStr.split('.');
    return new Date(year, month - 1, day);
  }
  
  const lastStartDate = parseDate(foundDates[0].value);
  const lastEndDate = parseDate(foundDates[1].value);
  
  if (!lastStartDate || !lastEndDate || isNaN(lastStartDate.getTime()) || isNaN(lastEndDate.getTime())) {
    console.error(`❌ Не удалось распознать даты: "${foundDates[0].value}", "${foundDates[1].value}"`);
    
    // Покажем все ячейки в строке 2 для отладки
    console.log("Отладка: все ячейки строки 2:");
    const row2Data = sheetZaprosy.getRange(2, 1, 1, lastColumn).getValues()[0];
    row2Data.forEach((value, index) => {
      if (value) console.log(`Колонка ${index + 1}: "${value}"`);
    });
    
    return;
  }
  
  // 3. Вычисляем следующую неделю
  const nextWeekStart = new Date(lastStartDate);
  nextWeekStart.setDate(nextWeekStart.getDate() + 7);
  
  const nextWeekEnd = new Date(lastEndDate);
  nextWeekEnd.setDate(nextWeekEnd.getDate() + 7);
  
  // 4. Форматируем даты обратно в DD.MM.YYYY
  function formatDate(date) {
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}.${month}.${year}`;
  }
  
  const nextWeekStartStr = formatDate(nextWeekStart);
  const nextWeekEndStr = formatDate(nextWeekEnd);
  
  // 5. Получаем сегодняшнюю дату
  const today = new Date();
  const todayStr = formatDate(today);
  console.log(`📅 Сегодня: ${todayStr}`);
  
  // 6. Проверяем, не выходит ли следующая неделя за пределы сегодня
  if (nextWeekStart > today) {
    console.log(`✅ Новая неделя ${nextWeekStartStr} начинается в будущем (после ${todayStr})`);
    console.log(`✅ Выгрузка завершена - достигнут сегодняшний день`);
    return;
  }
  
  // Если конец недели позже сегодня - обрезаем до сегодня
  let finalEndDate = nextWeekEnd;
  let isTrimmed = false;
  
  if (nextWeekEnd > today) {
    console.log(`⚠️  Конец недели ${nextWeekEndStr} позже сегодняшнего дня, обрезаем до ${todayStr}`);
    finalEndDate = today;
    isTrimmed = true;
  }
  
  const finalEndDateStr = formatDate(finalEndDate);
  
  console.log(`📅 Последняя загруженная неделя: ${foundDates[0].value} - ${foundDates[1].value}`);
  console.log(`📅 Выгружаем следующую неделю: ${nextWeekStartStr} - ${finalEndDateStr}`);
  
  // 7. Выгружаем данные
  const startEndDates = getFormattedDatesForPodmenAPI('manual', nextWeekStartStr, finalEndDateStr);
  executeSearchWordsAnalysis(startEndDates);
  
  console.log(`✅ Выгрузка завершена для недели ${nextWeekStartStr} - ${finalEndDateStr}`);
  
  // 8. Если неделя была обрезана, значит мы достигли сегодня
  if (isTrimmed) {
    console.log(`🎉 Достигнут сегодняшний день! Автоматическая выгрузка завершена.`);
  }
}

function letsGetPodmenArtikulAuto() {
  // Инициализация листа
  if (!initializeSheet()) {
    console.error("❌ Невозможно выполнить функцию: лист не найден");
    return;
  }
  
  const startEndDates = getFormattedDatesForPodmenAPI('auto');
  console.log("Даты получены автоматически (прошлая неделя)");
  executeSearchWordsAnalysis(startEndDates);
}

// ====== ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ ЛИСТА ====== //
function initializeSheet() {
  try {
    const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    sheetZaprosy = spreadsheet.getSheetByName("Аналитика по запросам");
    
    if (!sheetZaprosy) {
      console.error("❌ Лист 'Аналитика по запросам' не найден!");
      SpreadsheetApp.getUi().alert(
        'Ошибка', 
        'Лист "Аналитика по запросам" не найден в таблице', 
        SpreadsheetApp.getUi().ButtonSet.OK
      );
      return false;
    }
    
    console.log("✅ Лист 'Аналитика по запросам' успешно загружен");
    return true;
  } catch (error) {
    console.error("Ошибка при получении листа:", error.message);
    sheetZaprosy = null;
    return false;
  }
}

// ====== НОВАЯ ФУНКЦИЯ: ЗАГРУЗКА МАППИНГА ПОДМЕННЫХ АРТИКУЛОВ ====== //
/**
 * Загружает данные маппинга из колонок A и B текущего листа
 * Формат: A - подменный артикул (запрос), B - основной артикул (нуменклатура)
 */
function _poiskovie_zaprosi_loadPodmenMapping() {
  console.log("Загружаем маппинг подменных артикулов из листа 'Аналитика по запросам'...");
  
  if (!sheetZaprosy) {
    console.error("❌ Лист не инициализирован");
    return new Map();
  }
  
  const lastRow = sheetZaprosy.getLastRow();
  if (lastRow < 3) {
    console.log("❌ На листе нет данных (требуются данные с строки 3)");
    return new Map();
  }
  
  // Читаем данные из колонок A и B, начиная со строки 3 (строка 1-2 - заголовки и даты)
  const dataRange = sheetZaprosy.getRange(3, 1, lastRow - 2, 2); // A3:B[последняя строка]
  const data = dataRange.getValues();
  
  // Создаем Map для хранения соответствий
  const mapping = new Map();
  let loadedCount = 0;
  let duplicateCount = 0;
  
  // Обрабатываем каждую строку
  data.forEach((row, index) => {
    const searchWord = String(row[0]).trim(); // Колонка A - поисковый запрос
    const mainArtikul = row[1]; // Колонка B - основной артикул (может быть пустым)
    
    // Пропускаем пустые поисковые запросы
    if (!searchWord || searchWord === "") {
      return;
    }
    
    // Проверяем, есть ли уже такой запрос в маппинге
    if (mapping.has(searchWord)) {
      duplicateCount++;
      
      // Получаем текущее значение
      const currentValue = mapping.get(searchWord);
      
      // Если текущее значение - НЕ массив, преобразуем в массив
      if (!Array.isArray(currentValue)) {
        mapping.set(searchWord, [currentValue, mainArtikul]);
      } else {
        // Если уже массив - добавляем новый основной артикул
        currentValue.push(mainArtikul);
      }
    } else {
      // Первое вхождение - просто сохраняем значение
      mapping.set(searchWord, mainArtikul);
    }
    
    loadedCount++;
  });
  
  console.log(`✅ Загружено ${loadedCount} соответствий для фильтрации переходов`);
  if (duplicateCount > 0) {
    console.log(`⚠️ Найдено ${duplicateCount} дублирующихся запросов (будут обработаны как массивы)`);
  }
  
  return mapping;
}

// ====== НОВАЯ ФУНКЦИЯ: ПОЛУЧЕНИЕ ОСНОВНОГО АРТИКУЛА ====== //
function _poiskovie_zaprosi_shouldCountTransitions(searchWord, nmId, mapping) {
  // Преобразуем nmId к строке для сравнения
  const nmIdStr = String(nmId);
  
  // Ищем поисковый запрос в маппинге
  if (mapping.has(searchWord)) {
    const mainArtikulValue = mapping.get(searchWord);
    
    // Если значение - массив (несколько основных артикулов)
    if (Array.isArray(mainArtikulValue)) {
      // Проверяем, есть ли nmId в массиве основных артикулов
      return mainArtikulValue.some(main => {
        if (!main && main !== 0) return false; // Пустое значение
        return String(main) === nmIdStr;
      });
    } else {
      // Одиночное значение
      if (!mainArtikulValue && mainArtikulValue !== 0) {
        return true; // Нет основного -> считаем все переходы
      }
      return String(mainArtikulValue) === nmIdStr;
    }
  }
  
  // Если запроса нет в маппинге - считаем как "нет основного артикула"
  return true;
}

// ====== ОБНОВЛЕННАЯ ФУНКЦИЯ ПОЛУЧЕНИЯ ДАТ ====== //
function getFormattedDatesForPodmenAPI(mode = 'sheet', manualStartDate = null, manualEndDate = null) {
  let startDateStr, endDateStr;

  switch (mode) {
    case 'sheet':
      // Читаем даты из ячеек текущего листа (например, A1 и B1 или специальных ячеек)
      // Предполагаем, что даты хранятся в A1 и B1
      startDateStr = sheetZaprosy.getRange("A1").getDisplayValue();
      endDateStr = sheetZaprosy.getRange("B1").getDisplayValue();
      break;
    case 'manual':
      startDateStr = manualStartDate;
      endDateStr = manualEndDate;
      break;
    case 'auto':
      const dates = getLastWeekDates();
      startDateStr = dates.start;
      endDateStr = dates.end;
      break;
    default:
      throw new Error("Неизвестный режим получения дат");
  }

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

function getLastWeekDates() {
  const today = new Date();
  const dayOfWeek = today.getDay();
  const lastMonday = new Date(today);
  lastMonday.setDate(today.getDate() - dayOfWeek - 6);
  const lastSunday = new Date(lastMonday);
  lastSunday.setDate(lastMonday.getDate() + 6);

  const formatToDDMMYYYY = (date) => {
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}.${month}.${year}`;
  };

  return {
    start: formatToDDMMYYYY(lastMonday),
    end: formatToDDMMYYYY(lastSunday)
  };
}

// ====== ОСНОВНАЯ ЛОГИКА ДЛЯ ПОИСКОВЫХ СЛОВ ====== //
function executeSearchWordsAnalysis(startEndDates) {
  console.log("=== АНАЛИЗ ПОИСКОВЫХ СЛОВ ===");
  console.log("Период:", startEndDates.displayStart, "-", startEndDates.displayEnd);
  
  // Загружаем маппинг для фильтрации переходов
  _poiskovie_zaprosi_podmenMapping = _poiskovie_zaprosi_loadPodmenMapping();
  console.log(`Загружено ${_poiskovie_zaprosi_podmenMapping.size} запросов для фильтрации переходов`);
  
  const searchWordsData = getSearchWordsFromSheetZaprosy();
  console.log("Найдено поисковых слов:", searchWordsData.words.length);

  if (searchWordsData.words.length === 0) {
    console.log("❌ Нет поисковых слов для анализа");
    return;
  }

  const startColumn = findFirstEmptyColumn();
  console.log(`Запись начнется с колонки: ${startColumn}`);

  createHeadersAndDates(startColumn, startEndDates);

  // Анализируем с РАЗНЫМИ лимитами
  console.log(`\n=== АНАЛИЗ ДЛЯ ООО (лимит: ${LIMIT_CONFIG.OOO}) ===`);
  const oooResults = analyzeSearchWordsForCabinet(apiKeyOOO, startEndDates, searchWordsData, "ООО", LIMIT_CONFIG.OOO);

  console.log(`\n=== АНАЛИЗ ДЛЯ ИП (лимит: ${LIMIT_CONFIG.IP}) ===`);
  const ipResults = analyzeSearchWordsForCabinet(apiKeyIP, startEndDates, searchWordsData, "ИП", LIMIT_CONFIG.IP);

  Utilities.sleep(20000);

  const combinedResults = combineResults(oooResults, ipResults, searchWordsData.words);
  writeResultsToSheet(combinedResults, searchWordsData, startColumn);

  console.log("\n✅ Все данные записаны в таблицу!");
}

// Получаем поисковые слова из листа "Запросы"
function getSearchWordsFromSheetZaprosy() {
  if (!sheetZaprosy) {
    console.log("❌ Лист не инициализирован");
    return { words: [], rowMap: {}, lastRow: 0 };
  }

  const lastRow = sheetZaprosy.getLastRow();
  if (lastRow < 3) {
    console.log("❌ На листе нет данных (нужны данные с строки 3)");
    return { words: [], rowMap: {}, lastRow: 0 };
  }

  const columnData = sheetZaprosy.getRange("A3:A" + lastRow).getValues();
  const words = [];
  const rowMap = {};

  for (let i = 0; i < columnData.length; i++) {
    const cellValue = columnData[i][0];
    if (cellValue && cellValue.toString().trim() !== "") {
      const word = cellValue.toString().trim();
      words.push(word);
      rowMap[word] = i + 3;
    }
  }

  console.log(`✅ Получено ${words.length} запросов с листа`);
  return { words, rowMap, lastRow };
}

// Находим первую пустую колонку
function findFirstEmptyColumn() {
  const lastColumn = sheetZaprosy.getLastColumn();
  const startColumn = lastColumn + 1;
  return startColumn;
}

// Создаем заголовки и записываем даты с чередованием цветов
function createHeadersAndDates(startColumn, startEndDates) {
  const headers = ["Частота", "Переходы", "Добавления", "Заказы"];
  sheetZaprosy.getRange(1, startColumn, 1, 4).setValues([headers]);
  
  const datesRow = [startEndDates.displayStart, startEndDates.displayEnd, "", ""];
  sheetZaprosy.getRange(2, startColumn, 1, 4).setValues([datesRow]);
  
  const newColor = getNextBlockColor(startColumn);
  sheetZaprosy.getRange(1, startColumn, 2, 4).setBackground(newColor);
  
  console.log(`✅ Заголовки созданы в колонках ${startColumn}-${startColumn + 3}`);
}

function getNextBlockColor(startColumn) {
  if (startColumn === 1) return "#FED6BC";
  
  try {
    const lastCellColor = sheetZaprosy.getRange(1, startColumn - 1).getBackground();
    return (lastCellColor === "#fed6bc" || lastCellColor === "#FED6BC") ? "#DEF7FE" : "#FED6BC";
  } catch (error) {
    return "#FED6BC";
  }
}

// Анализ поисковых слов для конкретного кабинета
function analyzeSearchWordsForCabinet(apiKey, dates, searchWordsData, cabinetName, limit) {
  console.log(`Запрашиваем данные для кабинета: ${cabinetName} (лимит: ${limit})`);

  try {
    const options = createSearchWordsRequestOptions(apiKey, dates, limit);
    const response = sendSearchWordsRequest(options, cabinetName);

    if (response && response.length > 0) {
      console.log(`✅ Данные получены для ${cabinetName}`);
      console.log(`Найдено записей: ${response.length}`);

      // Передаем маппинг в функцию анализа
      const analysisResults = analyzeResultsWithDetails(
        response, 
        searchWordsData, 
        cabinetName, 
        _poiskovie_zaprosi_podmenMapping
      );
      
      return analysisResults;
    } else {
      console.log(`❌ Нет данных для кабинета ${cabinetName}`);
      return {};
    }

  } catch (error) {
    console.log(`❌ Ошибка при запросе для ${cabinetName}:`, error.toString());
    return {};
  }
}

// Создаем опции запроса для поисковых слов
function createSearchWordsRequestOptions(apiKey, currentPeriod, limit) {
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

// Отправляем запрос и обрабатываем ответ
function sendSearchWordsRequest(options, cabinetName) {
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
    return transformSearchData(data.data.items);

  } catch (error) {
    console.log(`Ошибка при обработке ответа для ${cabinetName}:`, error.toString());
    return [];
  }
}

// Преобразуем данные поиска
function transformSearchData(originalArray) {
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

    return {
      text: item.text || "",
      nmId: item.nmId || 0,
      frequency: Number(frequency) || 0,
      openCard: Number(openCard) || 0,
      addToCart: Number(addToCart) || 0,
      orders: Number(orders) || 0
    };
  }).filter(item => item.text !== "");
}

// ====== ОБНОВЛЕННАЯ ФУНКЦИЯ: АНАЛИЗ РЕЗУЛЬТАТОВ С ФИЛЬТРАЦИЕЙ ПЕРЕХОДОВ ====== //
function analyzeResultsWithDetails(data, searchWordsData, cabinetName, podmenMapping) {
  if (data.length === 0) {
    console.log("Нет данных для анализа");
    return {};
  }

  const wordsAnalysis = {};
  const { words } = searchWordsData;
  
  console.log(`Начинаем анализ ${data.length} записей для ${words.length} слов...`);
  console.log(`⚠️ ВНИМАНИЕ: переходы фильтруются по основному артикулу`);
  
  words.forEach(word => {
    const wordLower = word.toLowerCase();
    const matches = [];

    // Ищем все записи, содержащие это слово
    data.forEach(item => {
      if (item.text && item.text.toLowerCase().includes(wordLower)) {
        matches.push({
          text: item.text,
          frequency: item.frequency,
          openCard: item.openCard,
          addToCart: item.addToCart,
          orders: item.orders,
          nmId: item.nmId
        });
      }
    });

    if (matches.length > 0) {
      // Суммируем статистику с УЧЕТОМ ФИЛЬТРАЦИИ ПЕРЕХОДОВ
      const totals = matches.reduce((acc, match) => {
        // Частота, добавления, заказы - всегда суммируем
        acc.frequency += match.frequency;
        acc.addToCart += match.addToCart;
        acc.orders += match.orders;
        
        // Фильтруем переходы по основному артикулу
        const shouldCountTransitions = _poiskovie_zaprosi_shouldCountTransitions(
          word, // поисковый запрос
          match.nmId, // артикул из API
          podmenMapping // маппинг подменных артикулов
        );
        
        if (shouldCountTransitions) {
          acc.openCard += match.openCard;
          acc.includedTransitionsCount++;
        } else {
          acc.excludedTransitionsCount++;
        }
        
        return acc;
      }, { 
        frequency: 0, 
        openCard: 0, 
        addToCart: 0, 
        orders: 0,
        includedTransitionsCount: 0,
        excludedTransitionsCount: 0
      });

      wordsAnalysis[word] = {
        totalFrequency: totals.frequency,
        totalOrders: totals.orders,
        totalOpenCard: totals.openCard, // УЖЕ ОТФИЛЬТРОВАННЫЕ переходы
        totalAddToCart: totals.addToCart,
        matchCount: matches.length,
        includedTransitionsCount: totals.includedTransitionsCount,
        excludedTransitionsCount: totals.excludedTransitionsCount,
        matches: matches
      };

      // ДЕТАЛЬНЫЙ ВЫВОД
      console.log(`\n🎯 Слово: "${word}"`);
      console.log(`📊 Найдено совпадений: ${matches.length}`);
      console.log(`📈 Итоговые суммы: Частота=${totals.frequency}, Переходы=${totals.openCard} (учтено: ${totals.includedTransitionsCount}, исключено: ${totals.excludedTransitionsCount}), Добавления=${totals.addToCart}, Заказы=${totals.orders}`);
      
      if (totals.excludedTransitionsCount > 0) {
        console.log(`⚠️  Переходы отфильтрованы: исключено ${totals.excludedTransitionsCount} записей (не основной артикул)`);
      }
    }
  });

  console.log(`✅ Проанализировано слов для ${cabinetName}: ${Object.keys(wordsAnalysis).length}`);
  return wordsAnalysis;
}

// Суммируем результаты обоих кабинетов
function combineResults(oooResults, ipResults, words) {
  const combinedResults = {};
  
  words.forEach(word => {
    const oooData = oooResults[word] || {
      totalFrequency: 0,
      totalOrders: 0,
      totalOpenCard: 0,
      totalAddToCart: 0
    };
    
    const ipData = ipResults[word] || {
      totalFrequency: 0,
      totalOrders: 0,
      totalOpenCard: 0,
      totalAddToCart: 0
    };
    
    combinedResults[word] = {
      totalFrequency: oooData.totalFrequency + ipData.totalFrequency,
      totalOrders: oooData.totalOrders + ipData.totalOrders,
      totalOpenCard: oooData.totalOpenCard + ipData.totalOpenCard, // Уже отфильтрованные переходы
      totalAddToCart: oooData.totalAddToCart + ipData.totalAddToCart
    };
  });
  
  console.log(`✅ Результаты ООО и ИП объединены`);
  return combinedResults;
}

// Записываем результаты в таблицу
function writeResultsToSheet(results, searchWordsData, startColumn) {
  if (Object.keys(results).length === 0) {
    console.log(`❌ Нет результатов для записи`);
    return;
  }

  const { words, rowMap, lastRow } = searchWordsData;
  const dataToWrite = [];

  for (let row = 3; row <= lastRow; row++) {
    dataToWrite.push(["", "", "", ""]);
  }

  words.forEach(word => {
    const rowIndex = rowMap[word] - 3;
    const wordResults = results[word] || {
      totalFrequency: 0,
      totalOrders: 0,
      totalOpenCard: 0,
      totalAddToCart: 0
    };

    // Записываем данные (переходы уже отфильтрованы)
    dataToWrite[rowIndex] = [
      wordResults.totalFrequency,
      wordResults.totalOpenCard, // Фильтрованные переходы
      wordResults.totalAddToCart,
      wordResults.totalOrders
    ];
  });

  if (dataToWrite.length > 0) {
    sheetZaprosy.getRange(3, startColumn, dataToWrite.length, 4).setValues(dataToWrite);
    console.log(`✅ Записаны суммарные данные в колонки ${startColumn}-${startColumn + 3}`);
    console.log(`ℹ️  Переходы уже отфильтрованы по основному артикулу`);
  }
}