"""
Модуль интеграции с Bitrix24 REST API

Использование:
    from Bitrix.client import BitrixClient

    client = BitrixClient()
    print(client.get_auth_url())  # URL для авторизации
    client.authorize('код')       # Обмен кода на токены
    result = client.call('user.current')  # API запрос
"""

from Bitrix.client import BitrixClient

__all__ = ['BitrixClient']
