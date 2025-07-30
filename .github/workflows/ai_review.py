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
    """Получает изменения в последнем коммите или PR"""
    event_name = os.getenv('GITHUB_EVENT_NAME', 'push')

    if event_name == 'pull_request' and base_branch:
        # Для PR используем переданную базовую ветку
        print(f"Сравниваю с веткой: {base_branch}")
        base_sha = f'origin/{base_branch}'
        
        diff = run_cmd(f'git diff --name-status {base_sha}..HEAD')
        detailed_diff = run_cmd(f'git diff {base_sha}..HEAD')
    else:
        # Для push берём последний коммит
        print("Анализирую последний коммит")
        diff = run_cmd('git diff --name-status HEAD~1..HEAD')
        detailed_diff = run_cmd('git diff HEAD~1..HEAD')

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
Ты опытный разработчик. Проанализируй изменения в коде на основе diff.

**Коммит**: {changes['commit_msg']}

**Измененные файлы**:
{changes['files']}

**Diff изменений**:
```diff
{changes['diff']}
```

Проведи тщательный анализ кода:

1. **Критичные проблемы**: Безопасность, баги, нарушения архитектуры
2. **Проблемы качества**: Стиль кода, производительность, читаемость  
3. **Рекомендации**: Предложения по улучшению

ВАЖНО: 
- Если находишь проблемы - укажи КОНКРЕТНЫЙ файл и строку/область кода
- Формат: `файл.js:строка` или `файл.js:строки 10-15`
- Если проблем НЕТ - ответь точно: "НЕТ ПРОБЛЕМ"

Пример ответа с проблемами:
```
**Найдены проблемы:**

**auth.js:15** - Использование устаревшего метода аутентификации
**utils.ts:23-25** - Потенциальная утечка памяти в цикле
**config.json:8** - Хардкод секретного ключа

**Рекомендации:**
- Перейти на современный JWT
- Добавить очистку ресурсов
- Вынести ключ в переменные окружения
```

Если проблем нет - ответь: "НЕТ ПРОБЛЕМ"

Отвечай на русском, будь точным и конкретным.
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
    """Публикует комментарий в PR или коммит"""
    if not GITHUB_TOKEN:
        print("GitHub Token не найден")
        return

    event_name = os.getenv('GITHUB_EVENT_NAME', 'push')
    repo_name = os.getenv('GITHUB_REPOSITORY')

    if not repo_name:
        print("Repository не найден")
        return

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(repo_name)

        comment = f"""## AI Code Review

{review}

---
*Автоматический анализ от AI Reviewer*"""

        if event_name == 'pull_request':
            # Комментарий в PR
            pr_number = get_pr_number()
            if pr_number:
                pr = repo.get_pull(pr_number)
                pr.create_issue_comment(comment)
                print(f"Комментарий добавлен в PR #{pr_number}")
            else:
                print("Не удалось получить номер PR")
        else:
            # Комментарий в коммит
            sha = run_cmd('git rev-parse HEAD')
            if sha:
                commit = repo.get_commit(sha)
                commit.create_comment(comment)
                print(f"Комментарий добавлен к коммиту {sha[:8]}")
    except Exception as e:
        print(f"Ошибка публикации: {e}")

def main():
    """Основная функция"""
    print("AI Code Reviewer")
    
    # Получаем базовую ветку из аргументов
    base_branch = sys.argv[1] if len(sys.argv) > 1 else None
    
    if base_branch:
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
        print("\nНайдены проблемы в коде!")
        post_comment(result["review"])
        print("Комментарий с проблемами опубликован")
        sys.exit(1)  # Завершаемся с ошибкой
    else:
        # Проблем нет - завершаемся успешно без комментария
        print("\nКод выглядит хорошо! Проблем не найдено.")
        print("Комментарий не требуется - изменения одобрены.")
        sys.exit(0)  # Успешное завершение

if __name__ == "__main__":
    main()
