# Endware Security Bot 🛡️

[English](#english) | [Русский](#русский)

---

## Русский

**Endware Security Bot** — это продвинутый асинхронный Telegram-бот для модерации и защиты групп и каналов от спама, бот-набегов, нежелательного контента и вредоносных ссылок. Бот написан на Python с использованием библиотеки **aiogram 3**, ORM **SQLAlchemy** и базы данных **SQLite**, а также интегрирован с ИИ-моделями **Groq (Llama 4 Scout)** для глубокого текстового и визуального анализа.

### 🌟 Основные возможности

1. **Защита от спама и флуда (Anti-Spam / Flood):**
   * Ограничение отправки сообщений (более 4 сообщений за 5 секунд).
   * Блокировка за повторение одинаковых текстовых сообщений (спам дубликатами).
   * Умный обход альбомов/медиа-групп (до 10 фото отправляются как одно событие, исключая ложные муты).
2. **ИИ Модерация Медиа (NSFW / Vision):**
   * Анализ изображений через Groq Llama Vision.
   * Блокировка порнографии, жестокого контента и рекламы наркошопов.
3. **ИИ Детектор Скрытой Рекламы:**
   * Анализ никнеймов и сообщений на наличие скрытого пиара («ссылка в профиле», «канал в био» и т.д.).
4. **Безопасные Ссылки (Link Guard):**
   * Проверка и удаление фишинговых ссылок, IP-логгеров (Grabify и др.).
5. **Капча при вступлении (Captcha Gate):**
   * Ограничение права новых пользователей и проверка смайликом-животным при входе.
6. **Rogue Admin Protection:**
   * Автоматическое понижение в правах администраторов-нарушителей при фиксации спама.
7. **Кастомные API Ключи:**
   * Возможность для владельцев групп привязать собственные ключи Groq (Text / Vision) отдельно для каждого чата.

---

### 🛠️ Инструкция по установке

#### Требования
* Python 3.10 или выше

#### Шаги
1. **Клонируйте репозиторий:**
   ```bash
   git clone <URL_РЕПОЗИТОРИЯ>
   cd endwareprotect
   ```

2. **Настройте виртуальное окружение:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Установите зависимости:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Создайте файл конфигурации `.env`:**
   Скопируйте пример настроек и укажите свои токены:
   ```bash
   cp .env.example .env
   ```
   Отредактируйте `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=ваш_токен_телеграм_бота
   GROQ_API_KEY_TEXT=ваш_ключ_groq_для_текстов
   GROQ_API_KEY_VISION=ваш_ключ_groq_для_картинок
   OWNER_ID=ваш_telegram_id_владельца
   ```

5. **Запустите бота:**
   ```bash
   python main.py
   ```

---

### 🕹️ Команды модерации (в чате группы)
Команды нужно отправлять ответом (Reply) на сообщение нарушителя:
* `/mute [время] [причина]` — временно запретить писать (например, `/mute 30m флуд`).
* `/unmute` — снять ограничения.
* `/kick` — исключить из группы (пользователь сможет вернуться по ссылке).
* `/ban` — заблокировать навсегда.
* `/unban` — разблокировать.
* `/warn [причина]` — выдать предупреждение (3 предупреждения = автоматический мут на 24 часа).
* `/unwarn` — снять предупреждение.

Для вызова настроек напишите команду `/settings` в **личные сообщения** бота.

---

## English

**Endware Security Bot** is an advanced asynchronous Telegram moderation and defense bot for protecting groups and channels against spam, bot raids, rogue admins, and malicious links. Built on Python with **aiogram 3**, **SQLAlchemy**, and **SQLite**, it integrates with **Groq (Llama 4 Scout)** to leverage high-performance AI text and vision moderation.

### 🌟 Features

1. **Spam & Flood Protection:**
   * Classic flood rate limiter (triggers on the 5th message in 5 seconds).
   * Text repetition/duplicate detector (triggers on 3 identical messages in 15 seconds).
   * Album & media group bypass (up to 10 photos count as a single event to avoid false-positive mutes).
2. **AI Media Moderation (NSFW / Vision):**
   * Scans uploaded images using Groq Vision API.
   * Auto-blocks pornography, explicit nudity, gore, and drug shop advertisements.
3. **AI Stealth Ads Detector:**
   * Identifies advertising behavior in profiles, bios, and messages (e.g. "link in profile", "info in bio").
4. **Link Guard:**
   * Scans and deletes phishing links and IP loggers (Grabify, iplogger, etc.).
5. **Captcha Gate:**
   * Welcomes and restricts new members, requiring them to solve an emoji animal captcha.
6. **Rogue Admin Protection:**
   * Instantly demotes group administrators if they go rogue and start spamming.
7. **Custom Groq API Keys:**
   * Group creators can register their own Groq keys (Text & Vision) via `/settings` on a per-chat basis.

### 🛠️ Installation Guide

1. **Clone the repository:**
   ```bash
   git clone <REPO_URL>
   cd endwareprotect
   ```
2. **Setup virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install requirements:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure environment:**
   ```bash
   cp .env.example .env
   ```
   Add your keys to `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   GROQ_API_KEY_TEXT=your_groq_text_key
   GROQ_API_KEY_VISION=your_groq_vision_key
   OWNER_ID=your_telegram_user_id
   ```
5. **Run the bot:**
   ```bash
   python main.py
   ```
