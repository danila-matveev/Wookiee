#!/usr/bin/env python3
"""
One-time OAuth2 setup for Bitrix24 local application.

Usage:
    1. Create local app in Bitrix24 (see instructions below)
    2. Add BITRIX_CLIENT_ID and BITRIX_CLIENT_SECRET to .env
    3. Run: python3 scripts/bitrix_oauth_setup.py
    4. Open the URL in browser, authorize, paste the code back
    5. Done — tokens saved to .bitrix_tokens.json

How to create a local app in Bitrix24:
    1. Go to https://wookiee.bitrix24.ru/devops/list/
    2. Click "Добавить локальное приложение" (серверное)
    3. Set:
       - Название: Wookiee Bot
       - Только API (без интерфейса): YES
       - Назначенные права: select ALL
    4. Save → copy client_id and client_secret
    5. Add to .env:
       BITRIX_DOMAIN=wookiee.bitrix24.ru
       BITRIX_CLIENT_ID=local.xxxxx
       BITRIX_CLIENT_SECRET=xxxxx
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / '.env')


def main():
    domain = os.getenv('BITRIX_DOMAIN', 'wookiee.bitrix24.ru')
    client_id = os.getenv('BITRIX_CLIENT_ID', '')
    client_secret = os.getenv('BITRIX_CLIENT_SECRET', '')

    if not client_id or not client_secret:
        print('=' * 60)
        print('BITRIX_CLIENT_ID и BITRIX_CLIENT_SECRET не найдены в .env')
        print()
        print('Инструкция:')
        print(f'1. Открой https://{domain}/devops/list/')
        print('2. Нажми "Добавить локальное приложение"')
        print('3. Настройки:')
        print('   - Тип приложения: Серверное')
        print('   - Только API: Да')
        print('   - Назначенные права: ВСЕ галочки')
        print('4. Сохрани → скопируй client_id и client_secret')
        print('5. Добавь в .env:')
        print(f'   BITRIX_DOMAIN={domain}')
        print('   BITRIX_CLIENT_ID=local.xxxxx')
        print('   BITRIX_CLIENT_SECRET=xxxxx')
        print('6. Запусти этот скрипт снова')
        print('=' * 60)
        return

    from shared.clients.bitrix_client import BitrixClient

    tokens_file = str(PROJECT_ROOT / '.bitrix_tokens.json')
    client = BitrixClient.from_oauth(
        domain=domain,
        client_id=client_id,
        client_secret=client_secret,
        tokens_file=tokens_file,
    )

    # Check if we already have valid tokens
    if Path(tokens_file).exists():
        try:
            user = client.get_current_user()
            print(f'Токены уже есть и работают!')
            print(f'Пользователь: {user.get("NAME")} {user.get("LAST_NAME")}')
            print(f'Scopes: {len(client.check_scope())}')
            return
        except Exception:
            print('Токены устарели, нужна повторная авторизация.')

    # Step 1: Get auth URL
    auth_url = client.get_auth_url()
    print('=' * 60)
    print('Шаг 1: Открой эту ссылку в браузере:')
    print()
    print(f'  {auth_url}')
    print()
    print('Шаг 2: Разреши доступ приложению')
    print('Шаг 3: Тебя перенаправит на страницу с кодом в URL')
    print('        (или на blank page — код будет в адресной строке)')
    print('        URL будет выглядеть так:')
    print('        https://.../?code=XXXXX')
    print()
    code = input('Вставь код (code) из URL: ').strip()
    print('=' * 60)

    if not code:
        print('Код не введён. Отмена.')
        return

    # Step 2: Exchange code for tokens
    try:
        tokens = client.exchange_code(code)
        print(f'Токены получены и сохранены в {tokens_file}')
        print(f'  access_token: {tokens["access_token"][:20]}...')
        print(f'  refresh_token: {tokens["refresh_token"][:20]}...')
        print(f'  expires_in: {tokens.get("expires_in", "?")}s')

        # Verify
        user = client.get_current_user()
        scopes = client.check_scope()
        print()
        print(f'Авторизация успешна!')
        print(f'  Пользователь: {user.get("NAME")} {user.get("LAST_NAME")}')
        print(f'  Доступные scopes: {len(scopes)}')
        print(f'  landing: {"landing" in scopes}')

    except Exception as e:
        print(f'Ошибка: {e}')
        print('Попробуй запустить скрипт заново.')


if __name__ == '__main__':
    main()
