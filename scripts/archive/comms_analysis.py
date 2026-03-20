"""LLM-powered analysis of WB communications data.

Reads enriched CSV from comms_export, groups by model, sends samples to LLM
for deep analysis. Produces:
  - analysis_report.md — full model-by-model analysis
  - auto_response_prompts.md — ready-to-use prompts for Wookiee Hub
  - tone_of_voice.md — brand communication guidelines

Usage:
    python3 scripts/comms_analysis.py [--csv PATH] [--max-samples 100]
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared.config import MODEL_MAIN, OPENROUTER_API_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OUT_DIR = ROOT / "data" / "comms_export"


def load_csv(path: Path) -> list[dict]:
    """Load enriched CSV into list of dicts."""
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def call_llm(prompt: str, system: str = "", model: str = MODEL_MAIN) -> str:
    """Call OpenRouter LLM API."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(3):
        try:
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"model": model, "messages": messages, "max_tokens": 8000, "temperature": 0.3},
                timeout=120.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            elif resp.status_code == 429:
                logger.warning("Rate limited, waiting 30s...")
                time.sleep(30)
                continue
            else:
                logger.error("LLM HTTP %d: %s", resp.status_code, resp.text[:300])
                return f"[ERROR: HTTP {resp.status_code}]"
        except Exception as e:
            logger.error("LLM error: %s", e)
            if attempt < 2:
                time.sleep(5)
    return "[ERROR: failed after 3 attempts]"


def compute_stats(items: list[dict]) -> dict:
    """Compute basic statistics for a group of items."""
    total = len(items)
    feedbacks = [i for i in items if i.get("type") == "feedback"]
    questions = [i for i in items if i.get("type") == "question"]

    ratings = [int(i["rating"]) for i in feedbacks if i.get("rating") and i["rating"] != ""]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0

    answered = sum(1 for i in items if i.get("is_answered") == "True")
    with_text = [i for i in feedbacks if i.get("comment", "").strip()]
    with_pros = [i for i in feedbacks if i.get("pros", "").strip()]
    with_cons = [i for i in feedbacks if i.get("cons", "").strip()]

    rating_dist = defaultdict(int)
    for r in ratings:
        rating_dist[r] += 1

    return {
        "total": total,
        "feedbacks": len(feedbacks),
        "questions": len(questions),
        "avg_rating": round(avg_rating, 2),
        "rating_dist": dict(sorted(rating_dist.items())),
        "answered_pct": round(answered / total * 100, 1) if total else 0,
        "with_text_pct": round(len(with_text) / len(feedbacks) * 100, 1) if feedbacks else 0,
        "with_pros_pct": round(len(with_pros) / len(feedbacks) * 100, 1) if feedbacks else 0,
        "with_cons_pct": round(len(with_cons) / len(feedbacks) * 100, 1) if feedbacks else 0,
    }


def sample_items(items: list[dict], max_samples: int = 100) -> list[dict]:
    """Get a representative sample: mix of ratings, answered/unanswered, with text."""
    # Filter items with meaningful text content
    with_text = [i for i in items if (i.get("comment", "").strip() or i.get("pros", "").strip() or i.get("cons", "").strip())]

    if not with_text:
        return []

    # Stratified sampling by rating
    by_rating = defaultdict(list)
    for item in with_text:
        r = item.get("rating", "")
        if r and r != "":
            by_rating[int(r)].append(item)
        else:
            by_rating[0].append(item)  # questions

    sampled = []
    # Over-sample low ratings (1-2) for more insight into problems
    allocation = {1: 0.25, 2: 0.20, 3: 0.15, 4: 0.15, 5: 0.15, 0: 0.10}

    for rating, frac in allocation.items():
        pool = by_rating.get(rating, [])
        n = min(len(pool), max(1, int(max_samples * frac)))
        sampled.extend(random.sample(pool, n))

    # Fill remaining with random
    remaining = max_samples - len(sampled)
    if remaining > 0:
        unused = [i for i in with_text if i not in sampled]
        if unused:
            sampled.extend(random.sample(unused, min(remaining, len(unused))))

    return sampled[:max_samples]


def format_sample_for_llm(item: dict) -> str:
    """Format a single item for LLM input."""
    parts = []
    r = item.get("rating", "")
    if r and r != "":
        parts.append(f"[{item['type'].upper()} ★{r}]")
    else:
        parts.append(f"[{item['type'].upper()}]")

    if item.get("product_name"):
        parts.append(f"Товар: {item['product_name'][:60]}")
    if item.get("pros"):
        parts.append(f"Плюсы: {item['pros'][:200]}")
    if item.get("cons"):
        parts.append(f"Минусы: {item['cons'][:200]}")
    if item.get("comment"):
        parts.append(f"Комментарий: {item['comment'][:300]}")
    if item.get("answer_text"):
        parts.append(f"Ответ продавца: {item['answer_text'][:300]}")
    parts.append(f"Дата: {item.get('created_at', '')[:10]}")

    return "\n".join(parts)


SYSTEM_PROMPT = """Ты — эксперт по анализу коммуникаций бренда нижнего белья WOOKIEE на маркетплейсах (Wildberries, Ozon).
Бренд позиционируется как качественное бесшовное белье для повседневного использования.
Основные модели: Vuki (бестселлер), Moon, Ruby, Joy, Audrey, Wendy, Bella, Alice, Olivia, Valery.
Отвечай на русском языке. Будь конкретным и аналитичным."""


def analyze_model(model_name: str, items: list[dict], stats: dict, max_samples: int) -> str:
    """Analyze communications for one model via LLM."""
    samples = sample_items(items, max_samples)
    if not samples:
        return f"## {model_name}\n\nНедостаточно данных для анализа.\n"

    samples_text = "\n---\n".join(format_sample_for_llm(s) for s in samples)

    prompt = f"""Проанализируй отзывы и вопросы покупателей о модели **{model_name}** бренда WOOKIEE.

**Статистика модели:**
- Всего записей: {stats['total']} (отзывов: {stats['feedbacks']}, вопросов: {stats['questions']})
- Средний рейтинг: {stats['avg_rating']}
- Распределение оценок: {stats['rating_dist']}
- Отвечено: {stats['answered_pct']}%
- С текстом: {stats['with_text_pct']}%, с плюсами: {stats['with_pros_pct']}%, с минусами: {stats['with_cons_pct']}%

**Выборка из {len(samples)} отзывов/вопросов:**

{samples_text}

---

Проведи глубокий анализ по следующим пунктам:

1. **Ключевые достоинства** — что покупатели чаще всего хвалят (топ-5 тем)
2. **Ключевые проблемы** — на что жалуются (топ-5 тем), степень критичности
3. **Расхождение рейтинга и текста** — примеры где высокий рейтинг но негативный текст, и наоборот
4. **Частые вопросы** — о чем спрашивают покупатели
5. **Качество ответов продавца** — оценка текущих ответов:
   - Шаблонность (шаблон vs персонализация)
   - Решает ли ответ проблему покупателя
   - Тональность (вежливость, участие, равнодушие)
   - Есть ли приглашение к повторной покупке / в чат
6. **Рекомендации** — конкретные улучшения для этой модели

Формат: markdown с заголовками ##.
"""

    logger.info("Analyzing model %s (%d samples)...", model_name, len(samples))
    result = call_llm(prompt, system=SYSTEM_PROMPT)
    return f"## {model_name}\n\n{result}\n"


def generate_cross_model_analysis(model_stats: dict[str, dict]) -> str:
    """Generate cross-model comparison via LLM."""
    stats_text = "\n".join(
        f"- **{name}**: {s['total']} записей, ★{s['avg_rating']}, отвечено {s['answered_pct']}%, "
        f"оценки: {s['rating_dist']}"
        for name, s in sorted(model_stats.items(), key=lambda x: -x[1]["total"])
        if s["total"] >= 10
    )

    prompt = f"""Проведи сравнительный анализ моделей бренда WOOKIEE по коммуникациям с покупателями.

**Статистика по моделям:**
{stats_text}

Сделай:
1. **Рейтинг моделей** по удовлетворённости (не только по avg rating, а с учётом распределения)
2. **Проблемные модели** — где больше всего негатива, почему
3. **Лучшие модели** — бенчмарк для остальных
4. **Модели с низким % ответов** — требуют внимания
5. **Общие тренды** — паттерны, общие для всего бренда
6. **Приоритеты** — на чём фокусироваться в первую очередь

Формат: markdown.
"""

    logger.info("Generating cross-model analysis...")
    return call_llm(prompt, system=SYSTEM_PROMPT)


def generate_auto_prompts(all_items: list[dict], max_examples: int = 50) -> str:
    """Generate auto-response prompts for Wookiee Hub."""
    # Collect best seller responses (answered, diverse ratings)
    answered = [i for i in all_items if i.get("answer_text", "").strip() and i.get("type") == "feedback"]
    examples = sample_items(answered, max_examples)
    examples_text = "\n---\n".join(format_sample_for_llm(e) for e in examples)

    prompt = f"""На основе анализа {len(all_items)} отзывов и вопросов бренда WOOKIEE (бесшовное нижнее белье),
создай **готовые промпты для AI-системы автоматических ответов** в Wookiee Hub.

**Важные правила:**
1. Классификация НЕ по рейтингу, а по **реальной тональности текста**:
   - 5★ но негативный текст → обрабатывать как негативный
   - 1★ но позитивный текст → обрабатывать как позитивный
2. Паттерны вовлечения: «напишите нам в чат для промокода на повторную покупку»
3. Паттерны решения проблем: перевод в личный чат для возвратов/обменов
4. Ответы должны быть: вежливые, участливые, продающие, НЕ шаблонные

**Примеры существующих ответов продавца (для анализа стиля):**

{examples_text}

---

Создай следующие промпты (каждый — полноценный system prompt для LLM):

### 1. PROMPT_POSITIVE_REVIEW
Для позитивных отзывов (любой рейтинг, позитивная тональность текста).
Включи:
- Благодарность за покупку
- Персонализация по тексту отзыва (упомянуть что именно понравилось)
- Приглашение написать в чат за промокодом на повторную покупку
- Приглашение посмотреть другие модели

### 2. PROMPT_NEGATIVE_REVIEW
Для негативных отзывов (любой рейтинг, негативная тональность).
Включи:
- Извинение и сочувствие
- Конкретное решение по типу проблемы (размер, качество, доставка)
- Перевод в чат для решения вопроса
- НЕ спорить с покупателем

### 3. PROMPT_MIXED_REVIEW
Отзыв с плюсами и минусами одновременно.
- Поблагодарить за плюсы
- Отработать минусы
- Показать что мнение ценно

### 4. PROMPT_QUESTION
Для вопросов от покупателей.
- Чёткий ответ на вопрос
- Дополнительная полезная информация
- Приглашение к покупке

### 5. PROMPT_SIZE_COMPLAINT
Специальный промпт для жалоб на размер (самая частая проблема).
- Помощь с подбором размера
- Приглашение в чат для консультации
- Предложение обмена

### 6. PROMPT_QUALITY_COMPLAINT
Жалоба на качество/дефект.
- Серьёзное отношение
- Запрос фото в чат
- Предложение замены

### 7. PROMPT_CLASSIFIER
Промпт для классификации входящего отзыва/вопроса по категориям:
- positive / negative / mixed / question / size_complaint / quality_complaint
- Учитывать расхождение рейтинга и текста

Формат: markdown с кодовыми блоками для каждого промпта.
Каждый промпт должен быть production-ready system prompt для LLM.
"""

    logger.info("Generating auto-response prompts...")
    return call_llm(prompt, system=SYSTEM_PROMPT)


def generate_tone_of_voice(all_items: list[dict]) -> str:
    """Generate brand tone-of-voice guidelines."""
    # Get stats overview
    total = len(all_items)
    feedbacks = [i for i in all_items if i["type"] == "feedback"]
    ratings = [int(i["rating"]) for i in feedbacks if i.get("rating")]
    avg = sum(ratings) / len(ratings) if ratings else 0

    # Sample best answers
    best_answers = [i for i in feedbacks if i.get("answer_text", "").strip() and int(i.get("rating", 0)) >= 4]
    worst_answers = [i for i in feedbacks if i.get("answer_text", "").strip() and int(i.get("rating", 0)) <= 2]

    best_sample = random.sample(best_answers, min(20, len(best_answers)))
    worst_sample = random.sample(worst_answers, min(20, len(worst_answers)))

    best_text = "\n---\n".join(format_sample_for_llm(s) for s in best_sample)
    worst_text = "\n---\n".join(format_sample_for_llm(s) for s in worst_sample)

    prompt = f"""На основе анализа {total} коммуникаций бренда WOOKIEE (средний рейтинг: {avg:.2f}),
создай подробный документ **Tone of Voice** для бренда.

**Примеры ответов на позитивные отзывы (★4-5):**
{best_text}

**Примеры ответов на негативные отзывы (★1-2):**
{worst_text}

---

Создай документ со следующими разделами:

1. **Миссия коммуникации** — зачем мы отвечаем на отзывы (не для галочки)
2. **Голос бренда** — характер, тональность (дружелюбный vs формальный, и т.д.)
3. **Обращение** — как обращаемся к покупателям (ты/Вы, имя, и т.д.)
4. **Структура ответа** — обязательные элементы для каждого типа
5. **Правила по рейтингам**:
   - ★1-2: приоритет — решение проблемы
   - ★3: отработка минусов + благодарность за плюсы
   - ★4-5: благодарность + вовлечение
6. **Запрещённые фразы** — что нельзя писать (шаблоны, отписки)
7. **Обязательные элементы** — что всегда должно быть в ответе
8. **Стоп-слова** — слова которых избегаем
9. **Примеры идеальных ответов** — по 2-3 для каждого типа
10. **Метрики качества** — как оценивать ответы (чеклист)

Формат: markdown, готовый к использованию как руководство для команды и AI.
"""

    logger.info("Generating tone-of-voice document...")
    return call_llm(prompt, system=SYSTEM_PROMPT)


def main():
    parser = argparse.ArgumentParser(description="LLM analysis of WB/Ozon communications")
    parser.add_argument("--csv", type=str, help="Path to enriched CSV (default: latest in data/comms_export/)")
    parser.add_argument("--max-samples", type=int, default=80, help="Max samples per model for LLM")
    parser.add_argument("--top-models", type=int, default=10, help="Analyze top N models by volume")
    args = parser.parse_args()

    # Find CSV
    if args.csv:
        csv_path = Path(args.csv)
    else:
        csvs = sorted(OUT_DIR.glob("all_comms_*.csv"))
        if not csvs:
            logger.error("No CSV found in %s. Run comms_export.py first.", OUT_DIR)
            sys.exit(1)
        csv_path = csvs[-1]

    logger.info("Loading data from %s", csv_path)
    all_items = load_csv(csv_path)
    logger.info("Loaded %d items", len(all_items))

    # Group by model
    by_model = defaultdict(list)
    for item in all_items:
        model = item.get("model_osnova") or "Unknown"
        by_model[model].append(item)

    # Sort by count, take top N
    sorted_models = sorted(by_model.items(), key=lambda x: -len(x[1]))
    active_models = sorted_models[:args.top_models]

    logger.info("Models: %s", ", ".join(f"{m}({len(items)})" for m, items in active_models))

    # Compute stats per model
    model_stats = {}
    for model_name, items in active_models:
        model_stats[model_name] = compute_stats(items)

    # ---- 1. Model-by-model analysis ----
    report_parts = ["# Анализ коммуникаций WOOKIEE\n"]
    report_parts.append(f"**Дата анализа:** {csv_path.stem.split('_')[-1]}\n")
    report_parts.append(f"**Всего записей:** {len(all_items)}\n\n")

    for model_name, items in active_models:
        stats = model_stats[model_name]
        analysis = analyze_model(model_name, items, stats, args.max_samples)
        report_parts.append(analysis)
        report_parts.append("\n---\n\n")
        time.sleep(1)  # Rate limit courtesy

    # ---- 2. Cross-model comparison ----
    report_parts.append("# Сравнительный анализ моделей\n\n")
    cross_analysis = generate_cross_model_analysis(model_stats)
    report_parts.append(cross_analysis)

    # Save analysis report
    report_path = OUT_DIR / "analysis_report.md"
    report_path.write_text("\n".join(report_parts), encoding="utf-8")
    logger.info("Saved analysis report → %s", report_path)

    # ---- 3. Auto-response prompts ----
    prompts = generate_auto_prompts(all_items)
    prompts_path = OUT_DIR / "auto_response_prompts.md"
    prompts_path.write_text(f"# Промпты для автоматических ответов WOOKIEE\n\n{prompts}", encoding="utf-8")
    logger.info("Saved auto-response prompts → %s", prompts_path)

    # ---- 4. Tone of voice ----
    tov = generate_tone_of_voice(all_items)
    tov_path = OUT_DIR / "tone_of_voice.md"
    tov_path.write_text(f"# Tone of Voice — WOOKIEE\n\n{tov}", encoding="utf-8")
    logger.info("Saved tone-of-voice → %s", tov_path)

    logger.info("=" * 60)
    logger.info("ANALYSIS COMPLETE. Output files:")
    logger.info("  %s", report_path)
    logger.info("  %s", prompts_path)
    logger.info("  %s", tov_path)


if __name__ == "__main__":
    main()
