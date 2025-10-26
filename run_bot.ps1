# Запуск Telegram бота
# Скрипт для Windows PowerShell

Write-Host "🚀 Запуск Video Generator Bot..." -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green

# Проверяем наличие виртуального окружения
if (-Not (Test-Path "venv")) {
    Write-Host "❌ Виртуальное окружение не найдено!" -ForegroundColor Red
    Write-Host "Создаю виртуальное окружение..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "✅ Виртуальное окружение создано" -ForegroundColor Green
}

# Активируем виртуальное окружение
Write-Host "Активирую виртуальное окружение..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"

# Устанавливаем зависимости
Write-Host "Проверяю зависимости..." -ForegroundColor Yellow
pip install -q -r requirements.txt 2>$null

# Проверяем .env файл
if (-Not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Host "❌ .env файл не найден!" -ForegroundColor Red
        Write-Host "⚠️ Скопируй .env.example в .env и добавь токены:" -ForegroundColor Yellow
        Write-Host "   - BOT_TOKEN: Telegram Bot API токен" -ForegroundColor Cyan
        Write-Host "   - OPENAI_API_KEY: OpenAI API ключ" -ForegroundColor Cyan
        Write-Host "   - REPLICATE_API_TOKEN: Replicate API токен" -ForegroundColor Cyan
        exit
    }
}
else {
    Write-Host "✅ .env файл найден" -ForegroundColor Green
}

# Проверяем Python версию
$pythonVersion = python --version 2>&1
Write-Host "✅ $pythonVersion" -ForegroundColor Green

# Запускаем бота
Write-Host "`n🎬 Запускаю Video Generator Bot..." -ForegroundColor Green
Write-Host "💬 Бот готов к работе!" -ForegroundColor Green
Write-Host "================================================`n" -ForegroundColor Green

python main.py

Write-Host "`n👋 Бот остановлен" -ForegroundColor Yellow
deactivate