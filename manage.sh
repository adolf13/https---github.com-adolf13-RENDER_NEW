#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$PROJECT_DIR"
PID_FILE="$PROJECT_DIR/server.pid"

get_port() {
    # Сначала пытаемся получить порт из переменной окружения
    if [ -n "$RENDER_PORT" ]; then
        echo "$RENDER_PORT"
        return
    fi
    # Если не получилось, ищем в StartRender.py
    PORT=$(grep -oP 'RENDER_PORT", "\K[0-9]+' StartRender.py 2>/dev/null | head -1)
    if [ -z "$PORT" ]; then
        PORT=5001 # Значение по умолчанию, если ничего не найдено
    fi
    echo "$PORT"
}

get_ip() {
    IP=$(hostname -I | awk '{print $1}')
    if [ -z "$IP" ]; then
        IP="localhost"
    fi
    echo "$IP"
}

status() {
    PORT=$(get_port)
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null; then
            IP=$(get_ip)
            echo -e "${GREEN}✅ Сервер запущен${NC}"
            echo -e "${GREEN}   PID: $PID${NC}"
            echo -e "${GREEN}🌐 Локальный адрес: http://localhost:${PORT}${NC}"
            echo -e "${GREEN}🌐 Сетевой адрес: http://${IP}:${PORT}${NC}"
            return 0
        fi
    fi
    echo -e "${RED}❌ Сервер не запущен${NC}"
    # Очищаем старый PID-файл, если процесс не найден
    rm -f "$PID_FILE"
    return 1
}

stop() {
    PORT=$(get_port)
    echo -e "${YELLOW}🛑 Остановка сервера на порту $PORT...${NC}"
    
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${GREEN}✅ Сервер и так не был запущен (PID-файл не найден).${NC}"
        # Дополнительная проверка и очистка порта на всякий случай
        fuser -k ${PORT}/tcp 2>/dev/null
        return
    fi
    
    PID=$(cat "$PID_FILE")
    if [ -z "$PID" ]; then
        echo -e "${GREEN}✅ Сервер и так не был запущен (PID-файл пуст).${NC}"
        rm -f "$PID_FILE"
        return
    fi
    
    # Убиваем процесс
    kill -9 $PID 2>/dev/null
    rm -f "$PID_FILE"
    
    sleep 1
    
    # Проверяем, что порт действительно освободился
    if lsof -i :$PORT > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️ Порт $PORT всё ещё занят. Принудительная очистка...${NC}"
        fuser -k ${PORT}/tcp 2>/dev/null
        sleep 1
    fi
    
    echo -e "${GREEN}✅ Сервер остановлен${NC}"
}

start() {
    PORT=$(get_port)
    # Проверяем статус через PID-файл
    if status > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️ Сервер уже запущен. Для перезапуска используйте 'restart'.${NC}"
        status # Показываем текущий статус
        return
    fi
    
    echo -e "${GREEN}🚀 Запуск сервера...${NC}"
    
    # Проверка и активация виртуального окружения
    if [ -f "venv/bin/activate" ]; then
        echo -e "   Активация venv..."
        source venv/bin/activate
    else
        echo -e "${RED}❌ Виртуальное окружение 'venv' не найдено. Запуск невозможен.${NC}"
        return 1
    fi
    
    # Создаем необходимые директории
    mkdir -p ORDERS logs
    
    # Запуск в фоновом режиме с перенаправлением вывода в лог
    nohup python3 -u run.py --host 0.0.0.0 --port $PORT > logs/server.log 2>&1 &
    
    # Сохраняем PID в файл
    echo $! > "$PID_FILE"
    
    sleep 2
    
    if status > /dev/null 2>&1; then
        IP=$(get_ip)
        IP=$(get_ip)
        echo -e "${GREEN}✅ Сервер запущен${NC}"
        echo -e "${GREEN}   PID: $PID${NC}"
        echo -e "${GREEN}🌐 Локальный адрес: http://localhost:${PORT}${NC}"
        echo -e "${GREEN}🌐 Сетевой адрес: http://${IP}:${PORT}${NC}"
        return 0
    else
        echo -e "${RED}❌ Сервер не запущен${NC}"
        return 1
    fi
}

restart() {
    echo -e "${YELLOW}🔄 Перезапуск сервера...${NC}"
    stop
    sleep 2
    start
}

logs() {
    if [ -f "logs/server.log" ]; then
        echo -e "${BLUE}📋 Логи сервера (Ctrl+C для выхода)${NC}"
        echo -e "${YELLOW}================================${NC}"
        tail -f logs/server.log
    else
        echo -e "${RED}❌ Файл логов не найден: logs/server.log${NC}"
    fi
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart) restart ;;
    status) status ;;
    logs) logs ;;
    *)
        echo "Использование: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Команды:"
        echo "  start   - запустить сервер в фоновом режиме"
        echo "  stop    - остановить сервер"
        echo "  restart - перезапустить сервер"
        echo "  status  - проверить статус сервера"
        echo "  logs    - просмотреть основной лог сервера"
        exit 1
        ;;
esac