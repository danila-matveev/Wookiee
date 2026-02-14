let sheetSkleykyWB = activeSpreadsheet.getSheetByName("Склейки WB");

// === НАСТРОЙКИ ЗАЩИТЫ ОТ 401 ОШИБКИ ===
const SCRIPT_NAME_WB_GLUE = '- Обновление цен лист Склейки Wb (лист Склейки WB)';

function mainLetsGetAndPastePrices() {
  try {
    console.log("🔄 Склейки WB: Начало обновления цен...");
    
    let optionsIp = letsMakeGetOptions(apiKeyIP);
    let optionsOOO = letsMakeGetOptions(apiKeyOOO);
    
    console.log("   📥 Получение цен для ИП...");
    let arrIp = letsGetPrices(optionsIp);
    
    console.log("   📥 Получение цен для ООО...");
    let arrOOO = letsGetPrices(optionsOOO);
    
    let resultArr = arrIp.concat(arrOOO);
    console.log(`   📊 Итого товаров: ИП - ${arrIp.length}, ООО - ${arrOOO.length}, Всего - ${resultArr.length}`);
    
    pricesArr = letsMakePricesArr(resultArr);
    writeProductDataToSheet(pricesArr);
    
    console.log("✅ Склейки WB: Цены успешно обновлены!");
    SpreadsheetApp.getActive().toast(`Цены обновлены: ${resultArr.length} товаров. Вы великолепны!`, "✅ Скрипт выполнен");
    
  } catch (error) {
    console.error("💥 Склейки WB: Ошибка в основной функции:", error);
    
    // Проверяем ошибки авторизации
    checkAndHandle401ErrorWbGlue(error);
    
    SpreadsheetApp.getActive().toast(`Ошибка: ${error.message}`, "❌ Ошибка выполнения");
    throw error;
  }
}

function letsMakePricesArr(resultArr) {
  let pricesArr = [];
  
  if (!Array.isArray(resultArr)) {
    console.error("Ошибка: resultArr не является массивом");
    return pricesArr;
  }
  
  resultArr.forEach((good) => {
    try {
      let currentGoogdObj = {
        nmID: good.nmID || 0,
        discount: good.discount || 0,
        clubDiscount: good.clubDiscount || 0,
        price: (good.sizes && good.sizes.length > 0) ? good.sizes[0].price : 0,
        discountedPrice: (good.sizes && good.sizes.length > 0) ? good.sizes[0].discountedPrice : 0,
        clubDiscountedPrice: (good.sizes && good.sizes.length > 0) ? good.sizes[0].clubDiscountedPrice : 0
      };
      pricesArr.push(currentGoogdObj);
    } catch (itemError) {
      console.error("Ошибка обработки товара:", itemError, good);
    }
  });
  
  return pricesArr;
}

function writeProductDataToSheet(dataArray) {
  try {
    // Проверяем входные данные
    if (!Array.isArray(dataArray) || dataArray.length === 0) {
      console.warn("Нет данных для записи");
      return;
    }
    
    // Получаем все nmID из колонки D (начиная с D3)
    const nmIdRange = sheetSkleykyWB.getRange("D3:D" + sheetSkleykyWB.getLastRow());
    const nmIds = nmIdRange.getValues().flat();

    // Создаем объект для быстрого поиска данных по nmID
    const dataMap = {};
    dataArray.forEach(item => {
      if (item && item.nmID) {
        dataMap[item.nmID] = {
          price: item.price || "",
          discount: item.discount || "",
          // Округляем discountedPrice по математическим правилам
          discountedPrice: item.discountedPrice ? Math.round(item.discountedPrice) : "",
          clubDiscount: item.clubDiscount || ""
        };
      }
    });

    // Подготавливаем массив для записи в колонки S-V
    const valuesToWrite = nmIds.map(nmId => {
      const productData = dataMap[nmId];
      return productData ? [
        productData.price,
        productData.discount,
        productData.discountedPrice,
        productData.clubDiscount
      ] : ["", "", "", ""];
    });

    // Очищаем и записываем данные в колонки S-V
    if (valuesToWrite.length > 0) {
      sheetSkleykyWB.getRange("S3:V" + (valuesToWrite.length + 2)).clearContent();
      sheetSkleykyWB.getRange(3, 19, valuesToWrite.length, valuesToWrite[0].length).setValues(valuesToWrite);
      sheetSkleykyWB.getRange("S1").setValue("⏰ " + formattedTime + " 📅 " + formattedDate);
      
      console.log(`   📝 Записано данных: ${valuesToWrite.length} строк`);
    }
    
  } catch (error) {
    console.error("Ошибка в writeProductDataToSheet:", error);
    throw error;
  }
}

function letsGetPrices(options) {
  try {
    const wbApiUrl = "https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter?limit=1000";
    const response = UrlFetchApp.fetch(wbApiUrl, options);
    const responseCode = response.getResponseCode();
    
    // Проверяем 401 ошибку
    if (responseCode === 401) {
      const errorMsg = `API Wildberries вернул 401 при получении цен для склеек. Токен недействителен.`;
      const detailedError = new Error(errorMsg);
      checkAndHandle401ErrorWbGlue(detailedError);
      throw detailedError;
    }
    
    if (responseCode !== 200) {
      throw new Error(`Ошибка API Wildberries: ${responseCode}`);
    }
    
    const data = JSON.parse(response.getContentText());
    
    if (!data.data || !data.data.listGoods || !Array.isArray(data.data.listGoods)) {
      throw new Error(`Неверный формат ответа от API Wildberries`);
    }
    
    console.log(`Получено товаров: ${data.data.listGoods.length}`);
    return data.data.listGoods;
    
  } catch (error) {
    console.error("Ошибка в letsGetPrices:", error);
    
    // Проверяем любые ошибки авторизации
    checkAndHandle401ErrorWbGlue(error);
    
    throw error;
  }
}


function letsMakeGetOptions(apiKey) {
  const options = {
    "method": "GET",
    "muteHttpExceptions": true, // Добавляем для лучшей обработки ошибок
    "headers": {
      "Authorization": apiKey,
      "Content-Type": "application/json"
    }
  };
  return options;
}


/**
 * Проверяет ошибку на 401 и отправляет уведомление для скрипта Склейки WB
 * @param {Error} error - Объект ошибки
 */
function checkAndHandle401ErrorWbGlue(error) {
  const errorStr = error.toString();
  if (errorStr.includes('401') || 
      errorStr.includes('Unauthorized') ||
      errorStr.includes('Not authorized')) {
    handle401Error(error, SCRIPT_NAME_WB_GLUE);
  }
}