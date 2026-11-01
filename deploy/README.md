# 🚀 Развертывание Video Digest Engine на VPS (Systemd)

Руководство по развертыванию модульного генератора видео-дайджестов на вашем сервере (рядом с Telegram-ботом или отдельно).

---

## ⚡ Быстрый запуск в 3 шага

### Шаг 1: Клонирование или обновление репозитория на сервере

```bash
cd /root
git clone https://github.com/dhakii/reposter_api.git
# или если уже склонирован:
cd /root/reposter_api && git pull
```

### Шаг 2: Настройка переменных окружения

```bash
cd /root/reposter_api
cp .env.example .env
nano .env
```
Заполните в `.env`:
* `VK_USER_TOKEN` — ваш токен VK с правами `wall,video,offline`
* `VK_GROUP_ID` — ID группы ВКонтакте (только цифры)
* `AUCTION_DB_PATH` — путь к базе бота `/root/auction-bot/auction_bot.db` (для архива)

### Шаг 3: Автоматическая установка таймера Systemd

```bash
chmod +x deploy/setup_systemd.sh
./deploy/setup_systemd.sh
```

Скрипт автоматически:
1. Проверит и установит `ffmpeg` и базовые шрифты (`fonts-dejavu`)
2. Создаст виртуальное окружение `venv` и установит зависимости
3. Настроит системные службы `/etc/systemd/system/auction-digest.service` и `.timer`
4. Активирует запуск **3 раза в неделю (Понедельник, Среда, Пятница в 12:00)** — идеальный интервал в 2-3 дня, чтобы ролики успевали набирать охваты.

---

## 🛠️ Управление через Systemd

* **Проверить расписание:**
  ```bash
  systemctl list-timers | grep auction-digest
  ```

* **Запустить генерацию и публикацию ролика прямо сейчас вручную:**
  ```bash
  systemctl start auction-digest.service
  ```

* **Посмотреть живые логи генерации:**
  ```bash
  journalctl -u auction-digest.service -f
  ```

* **Изменить расписание (например, на каждые 2 или 3 дня):**
  Отредактируйте `/etc/systemd/system/auction-digest.timer`:
  * По умолчанию (Пн, Ср, Пт): `OnCalendar=Mon,Wed,Fri 12:00:00`
  * Каждые 2 дня: `OnCalendar=*-*-01/2 12:00:00`
  * Каждые 3 дня: `OnCalendar=*-*-01/3 12:00:00`

  Затем примените изменения:
  ```bash
  systemctl daemon-reload
  systemctl restart auction-digest.timer
  ```

---

## 🧩 Модульность: подключение новых площадок

В проекте реализована модульная архитектура публикации (`app/publishers/`):
* **VK Клипы / ВКонтакте** — полностью настроен и готов
* **YouTube Shorts** (`YouTubeShortsPublisher`) — подключается добавлением Google API токена в `.env`
* **Instagram Reels** (`InstagramReelsPublisher`) — подключается добавлением Meta Graph токена в `.env`
* **TikTok** (`TikTokPublisher`) — подключается добавлением TikTok токена в `.env`

Все издатели наследуют `BasePublisher`. Основной скрипт публикует во все настроенные сети автоматически без изменения кода.

---

## 🎨 Архив старых лотов и Fallback-стратегия

Генератор хранит локальную историю в `data/lot_archive.json`. 
* Если в Telegram-канале есть свежие картины — они берутся в первую очередь.
* Если свежих постов меньше 5 (или канал несколько дней молчит) — система автоматически добирает недостающие картины из архива старых лотов по алгоритму ротации (LRU).
* Ролики будут стабильно выходить каждый день, даже когда нет новых аукционов!
