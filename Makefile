.PHONY: test lint deploy help

test: ## Прогнать все тесты
	python3 -m pytest tests/ -q

lint: ## Линт + security scan
	ruff check agents services shared scripts

deploy: ## Деплой в Docker (app server)
	bash deploy/deploy.sh

help: ## Показать доступные команды
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' Makefile | sort | awk 'BEGIN {FS = ":.*## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
