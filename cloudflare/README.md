# Настройка Cloudflare Worker Proxy для VK

Этот воркер маршрутизирует все запросы к VK API (`api.vk.ru`) и серверам загрузки фото (`pu.vk.ru`) через глобальную сеть Cloudflare:
- **Полная анонимизация:** VK видит только IP-адреса Cloudflare, ваш реальный IP сервера нигде не фигурирует.
- **Обход блокировок:** Устраняет проблему с зависанием TCP-соединений при загрузке фотографий на `pu.vk.ru` с зарубежных VPS.
- **Бесплатно:** Тариф Cloudflare Workers Free предоставляет 100 000 запросов в день.

---

## Быстрая установка за 1 минуту

1. Войдите в свой аккаунт [dash.cloudflare.com](https://dash.cloudflare.com/).
2. В левом боковом меню перейдите в **Compute (Workers) > Workers & Pages** (или **Workers**).
3. Нажмите кнопку **Create application** -> **Create Worker**.
4. Задайте имя (например, `vk-proxy`) и нажмите **Deploy**.
5. Нажмите **Edit code**.
6. Удалите весь существующий код в редакторе и вставьте содержимое файла `worker.js`.
7. Нажмите **Deploy** (или **Save and Deploy**).
8. Скопируйте URL вашего воркера (например: `https://vk-proxy.your-subdomain.workers.dev`).

---

## Подключение к Reposter API

1. На вашем сервере в файле `/root/reposter_api/.env` добавьте строку с полученным URL:
   ```env
   VK_PROXY_URL=https://vk-proxy.your-subdomain.workers.dev
   ```

2. Перезапустите сервис репостера:
   ```bash
   systemctl restart reposter-api.service
   ```

3. Проверьте логи:
   ```bash
   journalctl -u reposter-api -n 20 --no-pager
   ```
   В логах при отправке запросов появится отметка: `VK HTTP [via CF Proxy ...]`.
