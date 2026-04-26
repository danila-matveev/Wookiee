import type { StoreResponseConfig } from "@/types/community-settings"

export function createDefaultConfig(connectionId: string): StoreResponseConfig {
  return {
    connectionId,
    reviewModes: {
      1: { mode: "semi_auto", enabled: true },
      2: { mode: "semi_auto", enabled: true },
      3: { mode: "semi_auto", enabled: true },
      4: { mode: "semi_auto", enabled: true },
      5: { mode: "semi_auto", enabled: true },
    },
    recommendProducts: { enabled: false, maxCount: 3, source: "matrix", excludeArticles: [] },
    signatureTemplate: { enabled: false, template: "" },
    questionMode: "disabled",
    salutation: "Привет! Это Wookiee 💛",
    toneOfVoice: { preset: "wookiee", custom: "" },
    responseLength: "medium",
    stopWords: [],
    negativeHandling: {
      enabled: true,
      prompt: "При негативном отзыве: валидируй чувства, признай проблему, предложи конкретное решение, переведи в чат. Никогда не спорь и не обвиняй покупателя.",
      ctaTemplate: "Напиши нам в чат заказа — разберёмся и всё исправим.",
    },
    storeDescription: "",
    brandDescriptions: [],
    productModels: [],
    trainingFiles: [],
    reviewPrompt: "",
    questionPrompt: "",
    chatMode: "disabled",
    chatPrompt: "",
  }
}

// -- WOOKIEE product models (17 real models) --

const PM = {
  vuki: "pm-vuki",
  vukiMagicRed: "pm-vuki-magic-red",
  moon: "pm-moon",
  ruby: "pm-ruby",
  joy: "pm-joy",
  wendy: "pm-wendy",
  eva: "pm-eva",
  audrey: "pm-audrey",
  bella: "pm-bella",
  alice: "pm-alice",
  charlotte: "pm-charlotte",
  trVuki: "pm-tr-vuki",
  trMoon: "pm-tr-moon",
  trRuby: "pm-tr-ruby",
  trBella: "pm-tr-bella",
  lana: "pm-lana",
  valery: "pm-valery",
} as const

const REVIEW_PROMPT = `Ты — голос бренда WOOKIEE. Общаешься как близкая подруга. Всегда на «ты».

Классификация: определи категорию по ТЕКСТУ, а не по звёздам:
- positive — покупатель доволен
- negative — покупатель недоволен (даже при 5★)
- mixed — и плюсы, и минусы
- question — вопрос к продавцу
- size_complaint — жалоба на размер
- quality_complaint — жалоба на брак/дефект
- recommendation_request — просьба порекомендовать

Правила ответа:
- Персонализируй: упомяни модель/цвет/деталь из отзыва
- Кросс-рекомендации только в позитивных отзывах
- В негативных — сочувствие + CTA в чат
- Подпись: «С теплом, Wookiee 💛»
- 3–6 предложений`

const QUESTION_PROMPT = `Ты — эксперт по продукту WOOKIEE. Знаешь всё о составе, размерах, моделях. Всегда на «ты».

Правила:
- Прямой ответ на вопрос
- Добавь полезную информацию (уход: стирка при 30°, мешок для стирки)
- Если вопрос о выборе модели — используй знание товарной матрицы
- Не выдумывай факты
- CTA: приглашение в чат за помощью`

const CHAT_PROMPT = `Ты — консультант поддержки WOOKIEE. Общаешься как близкая подруга. Всегда на «ты».

Задачи в чате:
- Помощь с подбором размера и модели
- Решение проблем (обмен, возврат, брак)
- Ответы на вопросы о составе, уходе, доставке
- Промокоды и рекомендации

Правила:
- Быстрые, конкретные ответы
- Если проблема — предложи решение сразу
- Используй знание товарной матрицы для рекомендаций`

export const mockCommsSettingsConfigs: Record<string, StoreResponseConfig> = {
  "conn-wb-01": {
    ...createDefaultConfig("conn-wb-01"),
    reviewModes: {
      1: { mode: "semi_auto", enabled: true },
      2: { mode: "semi_auto", enabled: true },
      3: { mode: "semi_auto", enabled: true },
      4: { mode: "semi_auto", enabled: true },
      5: { mode: "auto", enabled: true },
    },
    signatureTemplate: { enabled: true, template: "С теплом, {{brandName}} 💛" },
    toneOfVoice: { preset: "wookiee", custom: "" },
    recommendProducts: { enabled: true, maxCount: 2, source: "matrix", excludeArticles: [] },
    storeDescription: "WOOKIEE — бренд бесшовного белья про здоровый комфорт и реальную фигуру. Бельё, в котором чувствуешь себя свободно — без давления, утяжки и дискомфорта. Не переделывать тело, а поддержать его.",
    brandDescriptions: [
      { name: "WOOKIEE", description: "Бренд бесшовного белья для повседневной жизни. Голос: близкая подруга, которая разбирается в белье. Архетип Искатель — свобода, подлинность, «быть собой»." },
    ],
    productModels: [
      // Бюстгальтеры / Топы
      { id: PM.vuki, name: "Vuki", nomenclatures: [], description: "Бесшовный бюстгальтер, мягкая чашка, без косточек, трикотаж. Универсальная база на каждый день.", recommendWith: [PM.trVuki, PM.moon], positioning: "Универсальная база 24/7", notFor: ["нужен пуш-ап → Wendy"] },
      { id: PM.vukiMagicRed, name: "Vuki Magic Red", nomenclatures: [], description: "Праздничная капсула Vuki в красном для особых случаев.", recommendWith: [PM.trVuki], positioning: "Праздничная капсула Vuki" },
      { id: PM.moon, name: "Moon", nomenclatures: [], description: "Комфорт для большой груди. Широкие бретели, усиленная поддержка, до G.", recommendWith: [PM.trMoon, PM.ruby], positioning: "Комфорт для большой груди", notFor: ["маленькая грудь → Vuki"] },
      { id: PM.ruby, name: "Ruby", nomenclatures: [], description: "Спорт и активный день. Компрессия, фиксация при движении.", recommendWith: [PM.trRuby, PM.joy], positioning: "Спорт и активный день", notFor: ["нужен повседневный → Vuki"] },
      { id: PM.joy, name: "Joy", nomenclatures: [], description: "Лёгкий бралетт для дома. Минимум конструкций, кроп-топ силуэт.", recommendWith: [PM.trVuki], positioning: "Лёгкий бралетт для дома", notFor: ["нужна поддержка → Moon"] },
      { id: PM.wendy, name: "Wendy", nomenclatures: [], description: "Пуш-ап без косточек. Мягкий пуш-ап эффект, бесшовный.", recommendWith: [PM.eva], positioning: "Пуш-ап без косточек", notFor: ["не нужен пуш-ап → Vuki"] },
      { id: PM.eva, name: "Eva", nomenclatures: [], description: "Бесшовный с формой. Гладкий силуэт под одежду, формованная чашка.", recommendWith: [PM.wendy], positioning: "Бесшовный с формой", notFor: ["нужен трикотаж → Vuki"] },
      { id: PM.audrey, name: "Audrey", nomenclatures: [], description: "Бандо / без бретелей. Для открытых плеч, съёмные бретели.", recommendWith: [PM.bella], positioning: "Бандо / без бретелей", notFor: ["нужна поддержка → Moon"] },
      { id: PM.bella, name: "Bella", nomenclatures: [], description: "Кружевной бралетт. Декоративное кружево, мягкая поддержка.", recommendWith: [PM.trBella], positioning: "Кружевной бралетт", notFor: ["нужна фиксация → Ruby"] },
      { id: PM.alice, name: "Alice", nomenclatures: [], description: "Базовый хлопок. Хлопок с эластаном, классический крой.", recommendWith: [PM.valery], positioning: "Базовый хлопок", notFor: ["нужна бесшовность → Vuki"] },
      { id: PM.charlotte, name: "Charlotte", nomenclatures: [], description: "Корсетный топ. Моделирующий эффект, утяжка.", recommendWith: [], positioning: "Корсетный топ", notFor: ["нужен комфорт без утяжки → Vuki"] },
      // Трусы
      { id: PM.trVuki, name: "Трусы Vuki", nomenclatures: [], description: "Бесшовные слипы-база. Невидимы под одеждой, трикотаж.", recommendWith: [PM.vuki, PM.moon], positioning: "Бесшовные слипы-база", notFor: ["нужен бразилиана → Трусы Ruby"] },
      { id: PM.trMoon, name: "Трусы Moon", nomenclatures: [], description: "Высокая посадка для комфорта. Мягкая поддержка живота.", recommendWith: [PM.moon], positioning: "Высокая посадка для комфорта", notFor: ["нужна низкая посадка → Трусы Vuki"] },
      { id: PM.trRuby, name: "Трусы Ruby", nomenclatures: [], description: "Спорт-бразилиана. Активный крой.", recommendWith: [PM.ruby], positioning: "Спорт-бразилиана", notFor: ["нужна классика → Трусы Vuki"] },
      { id: PM.trBella, name: "Трусы Bella", nomenclatures: [], description: "Кружевной комплект. Декоративное кружево, пара к Bella.", recommendWith: [PM.bella], positioning: "Кружевной комплект", notFor: ["нужна бесшовность → Трусы Vuki"] },
      { id: PM.lana, name: "Lana", nomenclatures: [], description: "Бесшовные стринги. Невидимы под облегающей одеждой.", recommendWith: [PM.vuki, PM.eva], positioning: "Бесшовные стринги", notFor: ["не носишь стринги → Трусы Vuki"] },
      { id: PM.valery, name: "Valery", nomenclatures: [], description: "Хлопковая классика. Повседневные трусы из хлопка.", recommendWith: [PM.alice], positioning: "Хлопковая классика", notFor: ["нужна бесшовность → Трусы Vuki"] },
    ],
    trainingFiles: [
      { id: "tf-001", name: "tone-of-voice-wookiee.pdf", size: 3_200_000, uploadedAt: "2026-03-01T10:00:00Z", status: "ready" },
      { id: "tf-002", name: "auto-response-prompts.md", size: 45_000, uploadedAt: "2026-03-15T09:00:00Z", status: "ready" },
      { id: "tf-003", name: "size-chart-all-models.csv", size: 18_500, uploadedAt: "2026-03-10T14:00:00Z", status: "ready" },
    ],
    reviewPrompt: REVIEW_PROMPT,
    questionPrompt: QUESTION_PROMPT,
    chatPrompt: CHAT_PROMPT,
  },
  "conn-ozon-01": createDefaultConfig("conn-ozon-01"),
}
