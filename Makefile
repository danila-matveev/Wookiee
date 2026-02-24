.PHONY: oleg2 oleg2-test oleg2-check oleg2-deploy oleg1 test

# ── Oleg v2 ──────────────────────────────────────────────────

oleg2: ## Запустить Oleg v2 локально
	python3 -m agents.oleg_v2

oleg2-test: ## Прогнать unit-тесты Oleg v2
	python3 -m pytest tests/oleg_v2 -v

oleg2-check: ## Проверка здоровья: импорты + scheduler + конфиг
	python3 -m agents.oleg_v2.check_scheduler

oleg2-deploy: ## Собрать и запустить Oleg v2 в Docker
	bash deploy/deploy_v2.sh

# ── Oleg v1 (совместимость) ──────────────────────────────────

oleg1: ## Запустить Oleg v1 (bot)
	python3 -m agents.oleg bot

oleg1-deploy: ## Задеплоить Oleg v1 (agent + bot)
	bash deploy/deploy.sh

# ── Общее ────────────────────────────────────────────────────

test: ## Все тесты проекта
	python3 -m pytest tests/ -v

help: ## Показать доступные команды
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' Makefile | sort | awk 'BEGIN {FS = ":.*## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
