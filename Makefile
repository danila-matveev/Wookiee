.PHONY: oleg oleg-test oleg-check oleg-deploy test

# ── Oleg ──────────────────────────────────────────────────

oleg: ## Запустить Oleg локально
	python3 -m agents.oleg

oleg-test: ## Прогнать unit-тесты Oleg
	python3 -m pytest tests/oleg -v

oleg-check: ## Проверка здоровья: импорты + scheduler + конфиг
	python3 -m agents.oleg.check_scheduler

oleg-deploy: ## Собрать и запустить Oleg в Docker
	bash deploy/deploy.sh

# ── Общее ────────────────────────────────────────────────

test: ## Все тесты проекта
	python3 -m pytest tests/ -v

help: ## Показать доступные команды
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' Makefile | sort | awk 'BEGIN {FS = ":.*## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
