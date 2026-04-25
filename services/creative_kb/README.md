# Creative KB

## Назначение
Структурированная база рекламных креативов бренда Wookiee (видео, статьи ЯПС, тексты АДС/АДБ) с автоматической распаковкой содержимого через LLM и привязкой к performance-метрикам. Отвечает на вопрос «какие хуки/сценарии работают» на уровне отдельных элементов контента, а не кампаний.

Текущее состояние — MVP/PoC: модуль содержит только промпт-библиотеку (`prompts/video_unpack.md`) и тестовые фикстуры (`tests/fixtures/`). Полная реализация (ETL, embeddings, Notion-публикация) описана в `docs/superpowers/specs/2026-04-17-creative-kb-design.md`.

## Точка входа / как запускать
Прямой entry-point ещё не реализован. Для PoC-распаковки видео используется `prompts/video_unpack.md` как системный промпт LLM. LLM-вызовы — строго через OpenRouter (по правилу `.claude/rules/economics.md`): MAIN-tier модель (`google/gemini-3-flash-preview`) для распаковки текста, fallback на HEAVY-tier при confidence ниже порога.

## Зависимости
- Data: YaDisk (видео-файлы), Google Sheets (usage в АДС/АДБ/ЯПС), Supabase (планируемая таблица `creative_kb` с pgvector)
- External: OpenRouter (Gemini для распаковки), ffmpeg + whisper (транскрипты)

## Связанные скиллы
- `/content-search` — родственный модуль `services/content_kb/` индексирует фото; creative_kb — sibling для рекламных креативов
- `/marketing-report` — потребитель данных о performance креативов

## Owner
danila-matveev
