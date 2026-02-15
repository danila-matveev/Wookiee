// ====== Глобальные переменные =====//
let activeSpreadsheet = SpreadsheetApp.getActiveSpreadsheet();


// Глобальные переменные кабинетов WB //
const apiKeyOOO = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjUwOTA0djEiLCJ0eXAiOiJKV1QifQ.eyJhY2MiOjEsImVudCI6MSwiZXhwIjoxNzgyMjQ2MjU0LCJpZCI6IjAxOWI0YTRmLTEwYTctN2RlMS04YjA5LTFiNjYyMGIwNjE0YiIsImlpZCI6MTMyNTYzMTAsIm9pZCI6OTQ3Mzg4LCJzIjoxNjEyNiwic2lkIjoiNzM0YzEyMzAtYTUwYy00YzFjLThlZGUtYmMxMjRmMGY4YzcyIiwidCI6ZmFsc2UsInVpZCI6MTMyNTYzMTB9.AzefUj-4vs683KEcMOYPIZghmC19dsAvEIUEuNDnttqSi-QonNt5SU-_jYjgaWMFIHxfndJUJyW903dJAJVZdg";

const apiKeyIP = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjUwOTA0djEiLCJ0eXAiOiJKV1QifQ.eyJhY2MiOjEsImVudCI6MSwiZXhwIjoxNzgyMjQ2MjAwLCJpZCI6IjAxOWI0YTRlLTQwMGYtNzFjYS04YzBlLTQzMTZiOTM3YzBhYSIsImlpZCI6MTMyNTYzMTAsIm9pZCI6MTA1NzU3LCJzIjoxNjEyNiwic2lkIjoiNjZhNzgyMWQtMDhkMS01MGE2LWE2ODUtNmJlMDg4ODA4MGI0IiwidCI6ZmFsc2UsInVpZCI6MTMyNTYzMTB9.r45yyFsKamZJP_nD55Eqmhsd_R1-z2HoR6Bl0_u-w7Sm_rTdk8asl83ExFv04TnNIzmSs-44KR_jhlm9qU1ZRA";

// Глобальные переменные для кабинетов Ozon //
const cabinetCredentials = {
  "ИП": {
    clientId: "1410333",
    apiKey: "2ac7b0ea-1be8-4fef-ab91-f3dd3a30ea17"
  },
  "ООО": {
    clientId: "1540263", 
    apiKey: "5eff950a-6ed0-42c4-bdcc-4a3091aa9226"
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