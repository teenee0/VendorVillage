#!/bin/bash

# Конфигурация
FIXTURES_DIR="z_fixtures"  # Папка для фикстур
APPS=("accounts" "core" "mall" "marketplace" "media" "restaurants")  # Список приложений
INDENT=2  # Форматирование JSON

# Проверка manage.py
if [ ! -f "manage.py" ]; then
    echo "❌ Ошибка: Запустите скрипт из корня Django-проекта (где есть manage.py)!"
    exit 1
fi

# Создание фикстур (экспорт)
export_fixtures() {
    echo "📦 Создание фикстур..."
    mkdir -p "$FIXTURES_DIR"
    source .venv/Scripts/activate
    for app in "${APPS[@]}"; do
        echo " ➡️  Выгружаем $app..."
        OUTPUT_FILE="$FIXTURES_DIR/${app}.json"

        # Сохраняем в файл и подавляем весь stdout (и stderr при пустом дампе)
        python manage.py dumpdata "$app" --indent "$INDENT" --output "$OUTPUT_FILE" >/dev/null 2>&1

        if [ $? -ne 0 ] || [ ! -s "$OUTPUT_FILE" ]; then
            echo "⚠️  Нет данных для $app"
            rm -f "$OUTPUT_FILE"
            continue
        fi

        # Принудительная перекодировка в UTF-8 (если требуется)
        if file -bi "$OUTPUT_FILE" | grep -vi 'utf-8' > /dev/null; then
            echo "    🔄 Перекодировка $app.json в UTF-8..."
            python -c "import sys; f=sys.argv[1]; data=open(f, 'rb').read(); open(f, 'wb').write(data.decode('cp1251', errors='ignore').encode('utf-8'))" "$OUTPUT_FILE"
        fi
    done

    echo "✅ Готово! Фикстуры сохранены в $FIXTURES_DIR/"
}

# Загрузка фикстур (импорт)
import_fixtures() {
    echo "🔄 Загрузка фикстур..."
    source .venv/Scripts/activate
    for app in "${APPS[@]}"; do
        if [ -f "$FIXTURES_DIR/${app}.json" ]; then
            echo " ➡️  Загружаем $app..."
            python manage.py loaddata "$FIXTURES_DIR/${app}.json" || echo "⚠️  Ошибка загрузки $app"
        else
            echo "⚠️  Файл $FIXTURES_DIR/${app}.json не найден!"
        fi
    done

    echo "✅ Готово! Данные загружены."
}

# Меню
case "$1" in
    "export")
        export_fixtures
        ;;
    "import")
        import_fixtures
        ;;
    *)
        echo "Использование: $0 [command]"
        echo "Команды:"
        echo "  export  — создать фикстуры (выгрузить данные)"
        echo "  import  — загрузить фикстуры в БД"
        exit 1
        ;;
esac
