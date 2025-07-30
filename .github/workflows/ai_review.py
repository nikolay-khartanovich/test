#!/usr/bin/env python3
"""
AI Code Reviewer - анализирует изменения в репозитории
"""

import os
import subprocess
import json
import sys
from groq import Groq
from github import Github

# Настройки
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

def run_cmd(cmd):
    """Выполняет git команду"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""

def get_changes(base_branch=None):
    """Получает изменения в Pull Request"""
    if not base_branch:
        print("Ошибка: базовая ветка не указана")
        sys.exit(1)
    
    print(f"Сравниваю с веткой: {base_branch}")
    base_sha = f'origin/{base_branch}'
    
    diff = run_cmd(f'git diff --name-status {base_sha}..HEAD')
    detailed_diff = run_cmd(f'git diff {base_sha}..HEAD')

    return {
        'files': diff,
        'diff': detailed_diff[:10000],  # Увеличиваем лимит для diff
        'commit_msg': run_cmd('git log -1 --pretty=format:"%s"')
    }

def analyze_with_ai(changes):
    """Анализирует изменения с помощью AI"""
    if not GROQ_API_KEY:
        return {"has_issues": True, "review": "GROQ_API_KEY не настроен"}

    client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""
Ты опытный senior разработчик. Проанализируй изменения в коде на основе diff.

**Коммит**: {changes['commit_msg']}

**Измененные файлы**:
{changes['files']}

**Diff изменений**:
```diff
{changes['diff']}
```

Проанализируй код на наличие проблем:

- Уязвимости безопасности (SQL injection, XSS, CSRF)
- Утечки секретов (пароли, токены, ключи в коде) 
- Критические баги (NPE, memory leaks, infinite loops, undefined variables)
- Нарушения принципов SOLID, DRY, KISS
- Плохая архитектура и структура кода
- Неоптимальная производительность
- Отсутствие обработки ошибок
- Магические числа и хардкод значений
- Плохие названия переменных/функций/классов
- Избыточная сложность методов
- Нарушения coding standards
- Отсутствие комментариев в сложных местах
- Дублирование кода
- Неконсистентный стиль

**НЕ анализируй:**
- Версии зависимостей (кроме уязвимых)
- Названия проектов в title/описаниях

Для КАЖДОЙ проблемы укажи КОНКРЕТНЫЙ файл и строку:
Формат: `файл.js:строка` или `файл.js:строки 10-15`

Если проблем НЕТ - ответь точно: "НЕТ ПРОБЛЕМ"

Пример ответа с проблемами:
```
**Найдены проблемы:**

**auth.js:15** - SQL инъекция: прямая подстановка пользовательского ввода
**utils.ts:23-25** - Нарушение DRY: дублирование логики валидации  
**api.js:45** - Отсутствует обработка ошибок в async функции
**component.tsx:12** - Плохое название переменной 'a' вместо описательного
**service.js:8** - Функция слишком сложная (20+ строк), разбить на части
**config.js:3** - Хардкод API ключа в коде
```

Если проблем нет - ответь: "НЕТ ПРОБЛЕМ"

Будь строгим к качеству кода - перечисли ВСЕ найденные проблемы в едином списке!
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.1
        )
        
        review_text = response.choices[0].message.content.strip()
        
        # Проверяем, есть ли проблемы
        has_issues = not (review_text == "НЕТ ПРОБЛЕМ" or 
                         "нет проблем" in review_text.lower() or
                         "проблем не найдено" in review_text.lower())
        
        return {
            "has_issues": has_issues,
            "review": review_text
        }
        
    except Exception as e:
        return {"has_issues": True, "review": f"Ошибка AI: {e}"}

def get_pr_number():
    """Получает номер PR из GitHub event"""
    event_path = os.getenv('GITHUB_EVENT_PATH')
    if not event_path or not os.path.exists(event_path):
        return None
    
    try:
        with open(event_path, 'r') as f:
            event_data = json.load(f)
        return event_data.get('pull_request', {}).get('number')
    except Exception as e:
        print(f"Ошибка чтения event: {e}")
        return None

def post_comment(review):
    """Публикует комментарий в PR"""
    if not GITHUB_TOKEN:
        print("GitHub Token не найден")
        return False

    repo_name = os.getenv('GITHUB_REPOSITORY')
    if not repo_name:
        print("Repository не найден")
        return False

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(repo_name)

        comment = f"""## AI Code Review

{review}

---
*Автоматический анализ от AI Reviewer*"""

        # Получаем номер PR и публикуем комментарий
        pr_number = get_pr_number()
        if pr_number:
            pr = repo.get_pull(pr_number)
            pr.create_issue_comment(comment)
            print(f"Комментарий добавлен в PR #{pr_number}")
            return True
        else:
            print("Не удалось получить номер PR")
            return False
            
    except Exception as e:
        print(f"Ошибка публикации: {e}")
        return False

def main():
    """Основная функция"""
    print("AI Code Reviewer")
    
    # Базовая ветка обязательна для PR
    if len(sys.argv) < 2:
        print("Ошибка: не указана базовая ветка")
        sys.exit(1)
        
    base_branch = sys.argv[1]
    print(f"Базовая ветка: {base_branch}")

    # Получаем изменения
    print("Анализирую изменения...")
    changes = get_changes(base_branch)

    if not changes['files']:
        print("Нет изменений для анализа")
        sys.exit(0)

    # AI анализ
    print("Запускаю AI анализ...")
    result = analyze_with_ai(changes)

    print("Результат анализа:")
    print(result["review"])

    if result["has_issues"]:
        # Есть проблемы - публикуем комментарий и завершаемся с ошибкой
        print("\nНайдены критичные проблемы в коде!")
        
        success = post_comment(result["review"])
        if success:
            print("Комментарий с проблемами успешно опубликован")
        else:
            print("Ошибка публикации комментария, но проблемы найдены")
            
        sys.exit(1)  # Завершаемся с ошибкой
    else:
        # Проблем нет - завершаемся успешно без комментария
        print("\nКод выглядит хорошо! Критичных проблем не найдено.")
        print("Комментарий не требуется - изменения одобрены.")
        sys.exit(0)  # Успешное завершение

if __name__ == "__main__":
    main()
