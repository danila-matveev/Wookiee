// ====== Глобальные переменные =====//
let sheetOtzyvyOOO = activeSpreadsheet.getSheetByName("Отзывы ООО");
let sheetOtzyvyIP = activeSpreadsheet.getSheetByName("Отзывы ИП");

// === НАСТРОЙКИ ЗАЩИТЫ ОТ 401 ОШИБКИ ===
const SCRIPT_NAME_WB_FEEDBACKS = 'WB Отзывы - обновление отзывов';


// Текущая дата и время
const now = new Date();

// Дата ровно неделю назад (с учетом времени)
const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

// Дата ровно неделю назад (с учетом времени)
const startDate = new Date(2020, 0, 1, now.getHours(), now.getMinutes(), now.getSeconds());

// ====== Скрипт для обновления остатков WB =====//
const optionsGetOOO = {
  "method": "GET",
  "muteHttpExceptions": true, // Добавляем для лучшей обработки ошибок
  "headers": {
    "Authorization": apiKeyOOO,
    "Content-Type": "application/json"
  }
};

const optionsGetIP = {
  "method": "GET",
  "muteHttpExceptions": true, // Добавляем для лучшей обработки ошибок
  "headers": {
    "Authorization": apiKeyIP,
    "Content-Type": "application/json"
  }
};

function letsGetOtzyvyOOO() {
  try {
    console.log("🔄 WB Отзывы: Начало получения отзывов для ООО...");
    toastMessageTitle("Дождитесь получения отзывов по API", "Скрипт запущен");
    
    let transformedArr = [];
    let skipForApi = 0;
    
    // Получение отвеченных отзывов
    console.log("   📥 Получение отвеченных отзывов...");
    for (let offsetCounter = 0; offsetCounter < 1000000; offsetCounter++) {
      let wbApiURlfeedbacks = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks?isAnswered=true&take=5000&skip=" + skipForApi + "&order=dateDesc";
      
      const response = UrlFetchApp.fetch(wbApiURlfeedbacks, optionsGetOOO);
      const responseCode = response.getResponseCode();
      
      // Проверяем 401 ошибку
      if (responseCode === 401) {
        const errorMsg = `API Wildberries Feedbacks вернул 401 для кабинета ООО. Токен недействителен.`;
        const detailedError = new Error(errorMsg);
        checkAndHandle401ErrorWbFeedbacks(detailedError, 'ООО');
        throw detailedError;
      }
      
      if (responseCode !== 200) {
        throw new Error(`Ошибка API ООО: ${responseCode}`);
      }
      
      const data = JSON.parse(response.getContentText());
      let curentTransformedArr = transformFeedbackArray(data.data.feedbacks);
      transformedArr = transformedArr.concat(curentTransformedArr);
      
      if (curentTransformedArr.length === 5000) {
        skipForApi = skipForApi + 5000;
      } else {
        break;
      }
      
      Utilities.sleep(100); // Небольшая пауза между запросами
    }
    
    console.log(`   ✅ Отвеченных отзывов: ${transformedArr.length}`);
    
    // Получение неотвеченных отзывов
    console.log("   📥 Получение неотвеченных отзывов...");
    skipForApi = 0;
    for (let offsetCounterNotAnswered = 0; offsetCounterNotAnswered < 1000000; offsetCounterNotAnswered++) {
      let wbApiURlfeedbacks = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks?isAnswered=false&take=5000&skip=" + skipForApi + "&order=dateDesc";
      
      const response = UrlFetchApp.fetch(wbApiURlfeedbacks, optionsGetOOO);
      const responseCode = response.getResponseCode();
      
      // Проверяем 401 ошибку
      if (responseCode === 401) {
        const errorMsg = `API Wildberries Feedbacks вернул 401 для кабинета ООО (неотвеченные отзывы).`;
        const detailedError = new Error(errorMsg);
        checkAndHandle401ErrorWbFeedbacks(detailedError, 'ООО');
        throw detailedError;
      }
      
      if (responseCode !== 200) {
        throw new Error(`Ошибка API ООО (неотвеченные): ${responseCode}`);
      }
      
      const data = JSON.parse(response.getContentText());
      let curentTransformedArr = transformFeedbackArray(data.data.feedbacks);
      
      if (curentTransformedArr.length > 0) {
        transformedArr = transformedArr.concat(curentTransformedArr);
        break;
      }
      
      if (curentTransformedArr.length === 5000) {
        skipForApi = skipForApi + 5000;
      } else {
        break;
      }
      
      Utilities.sleep(100); // Небольшая пауза между запросами
    }
    
    console.log(`   📊 Всего отзывов ООО: ${transformedArr.length}`);
    
    // Обработка данных
    let filtredArr = filterFeedbackArray(transformedArr);
    let resultObj = countRatingsByProduct(filtredArr);
    let resultArr = letsMakeRangeForRatingOOO(resultObj);
    
    // Запись данных
    let currentTimeObj = getCurrentDateTime(now);
    sheetOtzyvyOOO.getRange(1, 2).setValue(currentTimeObj.date);
    sheetOtzyvyOOO.getRange(2, 2).setValue(currentTimeObj.time);
    
    let startDateObj = getCurrentDateTime(startDate);
    sheetOtzyvyOOO.getRange(5, 1).setValue(startDateObj.date);
    sheetOtzyvyOOO.getRange(5, 2).setValue(currentTimeObj.date);
    
    sheetOtzyvyOOO.getRange(13, 3, resultArr.length, resultArr[0].length).setValues(resultArr);
    
    console.log("✅ WB Отзывы: Отзывы для ООО успешно обновлены!");
    toastMessageTitle(`Отзывы ООО получены: ${transformedArr.length} шт.`, "Скрипт завершён");
    
  } catch (error) {
    console.error("💥 WB Отзывы: Ошибка для ООО:", error);
    checkAndHandle401ErrorWbFeedbacks(error, 'ООО');
    toastMessageTitle(`Ошибка: ${error.message}`, "❌ Ошибка выполнения");
    throw error;
  }
}



function letsGetOtzyvyIP() {
  try {
    console.log("🔄 WB Отзывы: Начало получения отзывов для ИП...");
    toastMessageTitle("Дождитесь получения отзывов по API", "Скрипт запущен");
    
    let transformedArr = [];
    let skipForApi = 0;
    
    // Получение отвеченных отзывов
    console.log("   📥 Получение отвеченных отзывов...");
    for (let offsetCounter = 0; offsetCounter < 1000000; offsetCounter++) {
      let wbApiURlfeedbacks = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks?isAnswered=true&take=5000&skip=" + skipForApi + "&order=dateDesc";
      
      const response = UrlFetchApp.fetch(wbApiURlfeedbacks, optionsGetIP);
      const responseCode = response.getResponseCode();
      
      // Проверяем 401 ошибку
      if (responseCode === 401) {
        const errorMsg = `API Wildberries Feedbacks вернул 401 для кабинета ИП. Токен недействителен.`;
        const detailedError = new Error(errorMsg);
        checkAndHandle401ErrorWbFeedbacks(detailedError, 'ИП');
        throw detailedError;
      }
      
      if (responseCode !== 200) {
        throw new Error(`Ошибка API ИП: ${responseCode}`);
      }
      
      const data = JSON.parse(response.getContentText());
      let curentTransformedArr = transformFeedbackArray(data.data.feedbacks);
      transformedArr = transformedArr.concat(curentTransformedArr);
      
      if (curentTransformedArr.length === 5000) {
        skipForApi = skipForApi + 5000;
      } else {
        break;
      }
      
      Utilities.sleep(100); // Небольшая пауза между запросами
    }
    
    console.log(`   ✅ Отвеченных отзывов: ${transformedArr.length}`);
    
    // Получение неотвеченных отзывов
    console.log("   📥 Получение неотвеченных отзывов...");
    skipForApi = 0;
    for (let offsetCounterNotAnswered = 0; offsetCounterNotAnswered < 1000000; offsetCounterNotAnswered++) {
      let wbApiURlfeedbacks = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks?isAnswered=false&take=5000&skip=" + skipForApi + "&order=dateDesc";
      
      const response = UrlFetchApp.fetch(wbApiURlfeedbacks, optionsGetIP);
      const responseCode = response.getResponseCode();
      
      // Проверяем 401 ошибку
      if (responseCode === 401) {
        const errorMsg = `API Wildberries Feedbacks вернул 401 для кабинета ИП (неотвеченные отзывы).`;
        const detailedError = new Error(errorMsg);
        checkAndHandle401ErrorWbFeedbacks(detailedError, 'ИП');
        throw detailedError;
      }
      
      if (responseCode !== 200) {
        throw new Error(`Ошибка API ИП (неотвеченные): ${responseCode}`);
      }
      
      const data = JSON.parse(response.getContentText());
      let curentTransformedArr = transformFeedbackArray(data.data.feedbacks);
      
      if (curentTransformedArr.length > 0) {
        transformedArr = transformedArr.concat(curentTransformedArr);
        break;
      }
      
      if (curentTransformedArr.length === 5000) {
        skipForApi = skipForApi + 5000;
      } else {
        break;
      }
      
      Utilities.sleep(100); // Небольшая пауза между запросами
    }
    
    console.log(`   📊 Всего отзывов ИП: ${transformedArr.length}`);
    
    // Обработка данных
    let filtredArr = filterFeedbackArray(transformedArr);
    let resultObj = countRatingsByProduct(filtredArr);
    let resultArr = letsMakeRangeForRatingIP(resultObj);
    
    // Запись данных
    let currentTimeObj = getCurrentDateTime(now);
    sheetOtzyvyIP.getRange(1, 2).setValue(currentTimeObj.date);
    sheetOtzyvyIP.getRange(2, 2).setValue(currentTimeObj.time);
    
    let startDateObj = getCurrentDateTime(startDate);
    sheetOtzyvyIP.getRange(5, 1).setValue(startDateObj.date);
    sheetOtzyvyIP.getRange(5, 2).setValue(currentTimeObj.date);
    
    sheetOtzyvyIP.getRange(13, 3, resultArr.length, resultArr[0].length).setValues(resultArr);
    
    console.log("✅ WB Отзывы: Отзывы для ИП успешно обновлены!");
    toastMessageTitle(`Отзывы ИП получены: ${transformedArr.length} шт.`, "Скрипт завершён");
    
  } catch (error) {
    console.error("💥 WB Отзывы: Ошибка для ИП:", error);
    checkAndHandle401ErrorWbFeedbacks(error, 'ИП');
    toastMessageTitle(`Ошибка: ${error.message}`, "❌ Ошибка выполнения");
    throw error;
  }
}

function getCurrentDateTime(now) {

  // Форматирование даты: число, месяц, год
  const day = now.getDate();
  const month = now.getMonth() + 1; // Месяцы начинаются с 0
  const year = now.getFullYear();
  const formattedDate = `${day}.${month}.${year}`;

  // Форматирование времени по GMT+3 (Москва)
  const hours = now.getUTCHours() + 3;
  const minutes = now.getUTCMinutes();
  const seconds = now.getUTCSeconds();
  const formattedTime = `${hours}:${minutes}:${seconds}`;

  return {
    date: formattedDate,
    time: formattedTime
  };
}


function transformFeedbackArray(originalArray) {
  return originalArray.map(function (feedback) {
    return {
      nmId: feedback.productDetails.nmId,
      productValuation: feedback.productValuation,
      createdDate: feedback.createdDate
    };
  });
}

function filterFeedbackArray(reviewsArray) {
  return reviewsArray.filter(function (review) {
    const reviewDate = new Date(review.createdDate);
    return reviewDate >= startDate && reviewDate <= now;
  });
}

function countRatingsByProduct(reviewsArray) {
  const result = {};
  reviewsArray.forEach(review => {
    const nmId = review.nmId;
    const rating = review.productValuation;
    // Инициализация структуры для нового товара
    if (!result[nmId]) {
      result[nmId] = {
        counts: { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 }, // Количество каждой оценки
        sum: 0,  // Сумма всех оценок
        total: 0 // Общее количество отзывов
      };
    }
    // Заполняем данные (если оценка валидна)
    if (rating >= 1 && rating <= 5) {
      result[nmId].counts[rating]++;
      result[nmId].sum += rating;
      result[nmId].total++;
    }
  });
  return result;
}

function letsMakeRangeForRatingOOO(ratingsData) {
  const nmIds = sheetOtzyvyOOO.getRange(`B13:B${sheetOtzyvyOOO.getLastRow()}`).getValues().flat();
  return nmIds.map(nmId => {
    if (!nmId || nmId === "") return ["", "", "", "", "", ""]; // 6 пустых строк
    const id = String(nmId).trim();
    const productData = ratingsData[id]; // Весь объект с counts, sum, total
    if (!productData) return ["", "", "", "", "", ""]; // 6 пустых строк
    // Рассчитываем средний рейтинг (sum / total)
    const averageRating = productData.total > 0
      ? (productData.sum / productData.total).toFixed(1).replace('.', ',')
      : '0';
    // Возвращаем массив: [средний, 5★, 4★, 3★, 2★, 1★]
    return [
      averageRating,
      productData.counts['5'] || 0,
      productData.counts['4'] || 0,
      productData.counts['3'] || 0,
      productData.counts['2'] || 0,
      productData.counts['1'] || 0
    ];
  });
}

function letsMakeRangeForRatingIP(ratingsData) {
  const nmIds = sheetOtzyvyIP.getRange(`B13:B${sheetOtzyvyIP.getLastRow()}`).getValues().flat();
  return nmIds.map(nmId => {
    if (!nmId || nmId === "") return ["", "", "", "", "", ""]; // 6 пустых строк
    const id = String(nmId).trim();
    const productData = ratingsData[id]; // Весь объект с counts, sum, total
    if (!productData) return ["", "", "", "", "", ""]; // 6 пустых строк
    // Рассчитываем средний рейтинг (sum / total)
    const averageRating = productData.total > 0
      ? (productData.sum / productData.total).toFixed(1).replace('.', ',')
      : '0';
    // Возвращаем массив: [средний, 5★, 4★, 3★, 2★, 1★]
    return [
      averageRating,
      productData.counts['5'] || 0,
      productData.counts['4'] || 0,
      productData.counts['3'] || 0,
      productData.counts['2'] || 0,
      productData.counts['1'] || 0
    ];
  });
}

/**
 * Проверяет ошибку на 401 и отправляет уведомление для скрипта WB Отзывы
 * @param {Error} error - Объект ошибки
 * @param {string} accountName - Название кабинета (ИП/ООО)
 */
function checkAndHandle401ErrorWbFeedbacks(error, accountName = '') {
  const errorStr = error.toString();
  if (errorStr.includes('401') || 
      errorStr.includes('Unauthorized') ||
      errorStr.includes('Not authorized')) {
    
    // Добавляем информацию о кабинете к ошибке
    const enhancedError = accountName 
      ? new Error(`${error.message} (Кабинет: ${accountName})`)
      : error;
    
    handle401Error(enhancedError, SCRIPT_NAME_WB_FEEDBACKS);
  }
}