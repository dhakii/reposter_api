#!/usr/bin/env bash
# ==============================================================================
# Скрипт быстрой установки Systemd-таймера для авто-дайджеста видео на VPS
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== Установка Auction Video Digest Timer в Systemd ==="
echo "Проект: ${PROJECT_DIR}"

# 1. Проверяем наличие python3, venv и ffmpeg
echo "-> Проверка системных зависимостей..."
if ! command -v ffmpeg &> /dev/null; then
    echo "ВНИМАНИЕ: ffmpeg не установлен! Устанавливаем ffmpeg..."
    apt-get update && apt-get install -y ffmpeg fonts-dejavu fonts-liberation
fi

# 2. Проверяем venv и обновляем зависимости
if [ ! -f "${PROJECT_DIR}/venv/bin/python" ]; then
    echo "-> Создание виртуального окружения python..."
    python3 -m venv "${PROJECT_DIR}/venv"
fi
echo "-> Проверка и установка python-зависимостей..."
"${PROJECT_DIR}/venv/bin/pip" install --upgrade pip
"${PROJECT_DIR}/venv/bin/pip" install -r "${PROJECT_DIR}/requirements.txt"

# 3. Подготавливаем юнит-файлы с реальным путем PROJECT_DIR
SERVICE_SRC="${SCRIPT_DIR}/auction-digest.service"
TIMER_SRC="${SCRIPT_DIR}/auction-digest.timer"

SERVICE_DEST="/etc/systemd/system/auction-digest.service"
TIMER_DEST="/etc/systemd/system/auction-digest.timer"

echo "-> Конфигурация ${SERVICE_DEST}..."
sed "s|/root/reposter_api|${PROJECT_DIR}|g" "${SERVICE_SRC}" > "${SERVICE_DEST}"
cp "${TIMER_SRC}" "${TIMER_DEST}"

# 4. Перезагрузка демонов systemd и запуск таймера
echo "-> Активация таймера в systemd..."
systemctl daemon-reload
systemctl enable auction-digest.timer
systemctl restart auction-digest.timer

echo ""
echo "=== Установка завершена успешно! ==="
echo "Таймер активен. Статус расписания:"
systemctl list-timers --no-pager | grep -E "auction-digest|NEXT" || true

echo ""
echo "Полезные команды на сервере:"
echo "  Проверить статус таймера:   systemctl status auction-digest.timer"
echo "  Запустить разово вручную:   systemctl start auction-digest.service"
echo "  Посмотреть логи генерации:  journalctl -u auction-digest.service -f"
