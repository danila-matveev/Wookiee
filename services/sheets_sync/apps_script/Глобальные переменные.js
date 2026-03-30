// ====== Глобальные переменные =====//
let activeSpreadsheet = SpreadsheetApp.getActiveSpreadsheet();


// Глобальные переменные кабинетов WB //
// Ключи хранятся в Script Properties (File → Project properties → Script properties)
// Необходимые ключи: WB_API_KEY_OOO, WB_API_KEY_IP, OZON_CLIENT_ID_IP, OZON_API_KEY_IP, OZON_CLIENT_ID_OOO, OZON_API_KEY_OOO
const scriptProps = PropertiesService.getScriptProperties();
const apiKeyOOO = scriptProps.getProperty("WB_API_KEY_OOO");
const apiKeyIP = scriptProps.getProperty("WB_API_KEY_IP");

// Глобальные переменные для кабинетов Ozon //
const cabinetCredentials = {
  "ИП": {
    clientId: scriptProps.getProperty("OZON_CLIENT_ID_IP"),
    apiKey: scriptProps.getProperty("OZON_API_KEY_IP")
  },
  "ООО": {
    clientId: scriptProps.getProperty("OZON_CLIENT_ID_OOO"),
    apiKey: scriptProps.getProperty("OZON_API_KEY_OOO")
  }
};

// Глобальные переменные времени//
const formattedDate = Utilities.formatDate(new Date(), "GMT+3", "dd.MM.yyyy");
const formattedTime = Utilities.formatDate(new Date(), "GMT+3", "HH:mm");

// Функции уведомлений
function toastMessageTitle(message, title) {
  if (!message) message = "Текст сообщения";
  if (!title) title = "Заголовок";
  SpreadsheetApp.getActive().toast(message, title);
}

function alertMessage(message) {
  if (!message) message = "Текст сообщения";
  SpreadsheetApp.getUi().alert(message);
}