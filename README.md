# 🎨 Reposter & Video Digest Engine

Автономный сервис репостов и генерации премиальных вертикальных видео-дайджестов (Reels, Shorts, Клипы) для художественного аукциона **«Твоя Коллекция»**.

---

## 🌟 Возможности системы

1. **Генератор видеороликов высокого класса (Hybrid Editorial):**
   * Разрешение 1080×1920 (9:16), 30 fps, H.264/AAC.
   * Адаптивная вёрстка: картина занимает 68% высоты без обрезки полей на размытом полупрозрачном фоне.
   * Элегантная вёрстка: плашка лота, типографика (Serif Playfair / Montserrat), капсула стартовой цены с квадратными скобками в стиле каталогов Sotheby's.
   * Фирменный переход **Dip-to-White** (затухание в чистый белый цвет) на аутро-экран с логотипом аукциона и ссылкой на канал.
   * Синтезированный эмбиентный саундтрек без авторских прав и перегрузки басами.

2. **Каскадная публикация (1 ролик на 3 дня ровно в 18:00):**
   * **День 1 (18:00):** Сборка ролика и мгновенная публикация в **VK Клипы**.
   * **День 2 (18:00):** Этот же ролик публикуется в **Instagram Reels**.
   * **День 3 (18:00):** Этот же ролик публикуется в **YouTube Shorts**.
   * **День 4 (18:00):** Запуск нового цикла (новый ролик -> VK).
   * *Эффект:* нулевая нагрузка на сервер в дни 2 и 3, постоянная активность на всех площадках, видео не конкурируют друг с другом.

3. **Умный пул картин и архив (Fallback-стратегия):**
   * Парсит свежие лоты из канала Telegram (`@marinakhakimova_auction`).
   * Если новых постов нет или их меньше 5 — система автоматически добирает недостающие картины из архива старых лотов (`data/lot_archive.json` или база `auction_bot.db`) по алгоритму наименее используемых (LRU). Ролики выходят стабильно всегда.

4. **Индивидуальные шаблоны описаний и тегов (без «нейровайба»):**
   * Все тексты и хэштеги редактируются в [`templates/social_templates.json`](./templates/social_templates.json).
   * Под каждой соцсетью подобраны свои теги:
     * **VK:** `#картины #живопись #аукцион #клипы #художникироссии #картинамаслом`
     * **YouTube:** `#Shorts #картины #живопись #аукцион #oilpainting #искусство`
     * **Instagram:** `#аукционискусства #живописьмаслом #русскиехудожники #коллекциякартин #contemporarypainting`
   * Человечный, сдержанный тон каталога аукциона без шаблонных робо-фраз.
   * Подстановка переменных: `{lot_range}`, `{lot_list}`, `{min_price}`, `{channel_handle}`, `{channel_url}`.

---

## 🚀 Быстрый старт на VPS (в 3 шага)

### 1. Клонирование на сервере
```bash
cd /root
git clone https://github.com/dhakii/reposter_api.git
cd /root/reposter_api
```

### 2. Настройка ключей в `.env`
```bash
cp .env.example .env
nano .env
```
Заполните ключи для нужных соцсетей (см. раздел «Получение ключей» ниже).

### 3. Запуск авто-установщика
```bash
chmod +x deploy/setup_systemd.sh
./deploy/setup_systemd.sh
```
Скрипт сам установит ffmpeg, шрифты, python-зависимости и включит ежедневный таймер в **18:00**.

---

## 🔑 Инструкция по получению ключей (API)

### 1. ВКонтакте (VK Клипы и Стена)
1. Получите токен пользователя с правами `wall,video,offline` (например, через VK Admin или vkhost.github.io с правами Kate Mobile / VK Admin).
2. Узнайте числовой ID группы (без знака минус).
3. В `.env` укажите:
   ```env
   VK_USER_TOKEN=vk1.a.ваш_токен
   VK_GROUP_ID=123456789
   ```

### 2. YouTube Shorts (Google YouTube Data API v3)
1. В [Google Cloud Console](https://console.cloud.google.com/apis/credentials) создайте проект и включите **YouTube Data API v3**.
2. Создайте учетные данные: **OAuth 2.0 Client ID** (Тип: *Desktop App* / *Приложение для ПК*).
3. Нажмите кнопку **Download JSON** и сохраните файл как `client_secret.json` в папке проекта.
4. На своём компьютере запустите интерактивный мастер:
   ```bash
   python scripts/setup_youtube_auth.py
   ```
5. В браузере подтвердите доступ. Скрипт выдаст три готовые строки для `.env`:
   ```env
   YOUTUBE_CLIENT_ID=...
   YOUTUBE_CLIENT_SECRET=...
   YOUTUBE_REFRESH_TOKEN=...
   ```

### 3. Instagram Reels (Meta Graph API)
1. Переведите профиль Instagram в **Профессиональный** (Бизнес или Автор).
2. Привяжите его к публичной странице Facebook в **Meta Business Suite**.
3. В [Meta for Developers](https://developers.facebook.com) создайте приложение (Тип: *Бизнес*) и добавьте продукт **Instagram Graph API**.
4. В Graph API Explorer сгенерируйте **Long-Lived Page Access Token** с правами: `instagram_basic`, `instagram_content_publish`.
5. В `.env` укажите:
   ```env
   INSTAGRAM_ACCESS_TOKEN=EAAB...
   INSTAGRAM_ACCOUNT_ID=178414...   # Числовой Instagram Business Account ID
   PUBLIC_APP_URL=http://ip_вашего_сервера:8000
   ```

---

## 🛠️ Полезные команды на сервере

* **Проверить статус подключения всех платформ и шаблонов:**
  ```bash
  ./venv/bin/python scripts/test_publishers.py
  ```
* **Посмотреть состояние 3-дневного каскада и архив лотов:**
  ```bash
  ./venv/bin/python -m app.orchestrator --status
  ```
* **Запустить шаг сегодняшнего дня вручную прямо сейчас:**
  ```bash
  systemctl start auction-digest.service
  ```
* **Смотреть живой лог генерации и публикации:**
  ```bash
  journalctl -u auction-digest.service -f
  ```
* **Проверить расписание Systemd таймера:**
  ```bash
  systemctl list-timers | grep auction-digest
  ```

---

## 📁 Структура проекта

```
reposter_api/
├── app/
│   ├── publishers/              # Модули публикации в соцсети
│   │   ├── base.py              # Интерфейс BasePublisher
│   │   ├── vk_publisher.py      # Модуль VK Клипы
│   │   ├── youtube_publisher.py # Модуль YouTube Shorts (OAuth2/Resumable)
│   │   ├── instagram_publisher.py # Модуль Instagram Reels (Meta Graph API)
│   │   ├── tiktok_publisher.py  # Модуль TikTok Content Posting API
│   │   └── manager.py           # Диспетчер PublisherManager
│   ├── sources/                 # Источники данных
│   │   ├── telegram_source.py   # Парсер канала @marinakhakimova_auction
│   │   ├── bot_db_source.py     # Источник SQLite базы аукционного бота
│   │   └── pool.py              # Пул картин и архив с умной ротацией (LRU)
│   ├── video_engine/            # Графический и видео-движок (Hybrid Editorial)
│   │   ├── builder.py           # Сборка роликов, Dip-to-White, аудио-микс
│   │   ├── overlays.py          # Вёрстка плашек, шрифтов, теней и капсул
│   │   └── audio_synth.py       # Генератор фоновой эмбиентной музыки
│   ├── cascade.py               # Менеджер 3-дневной каскадной кампании
│   ├── template_engine.py       # Шаблонизатор текстов и тегов
│   └── orchestrator.py          # Главный оркестратор конвейера
├── deploy/                      # Файлы развертывания на VPS
│   ├── auction-digest.service   # Systemd-сервис
│   ├── auction-digest.timer     # Systemd-таймер (каждый день в 18:00)
│   ├── setup_systemd.sh         # Скрипт авто-установки
│   └── README.md                # Руководство по деплою
├── templates/
│   └── social_templates.json    # Настраиваемые тексты и теги для VK, YT, IG
├── scripts/
│   ├── setup_youtube_auth.py    # 1-кликовый мастер авторизации YouTube
│   └── test_publishers.py       # Тест шаблонов и проверка готовности ключей
├── requirements.txt             # Все зависимости
└── .env.example                 # Шаблон файла настроек
```
