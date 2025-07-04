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
        python manage.py dumpdata "$app" --indent "$INDENT" --output "$FIXTURES_DIR/${app}.json" 2>/dev/null || echo "⚠️  Нет данных для $app"
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