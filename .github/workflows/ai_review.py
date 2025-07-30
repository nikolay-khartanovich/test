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

def validate_api_keys():
    """Проверяет наличие необходимых API ключей с обработкой ошибок"""
    try:
        groq_key = os.getenv('GROQ_API_KEY')
        if not groq_key or groq_key.strip() == '':
            print("Ошибка: GROQ_API_KEY не найден или пуст в переменных окружения")
            return False
        
        github_token = os.getenv('GITHUB_TOKEN')
        if not github_token or github_token.strip() == '':
            print("Ошибка: GITHUB_TOKEN не найден или пуст в переменных окружения")  
            return False
            
        print("API ключи успешно загружены из переменных окружения")
        return True
        
    except Exception as e:
        print(f"Ошибка при проверке API ключей: {e}")
        return False

def run_cmd(cmd):
    """Выполняет только безопасные git команды с улучшенной обработкой ошибок"""
    # Проверяем, что команда начинается с git для безопасности
    if not isinstance(cmd, str) or not cmd.strip().startswith('git '):
        print(f"Ошибка: разрешены только git команды. Получено: {cmd}")
        return ""
    
    # Список разрешенных git команд для дополнительной безопасности
    allowed_git_commands = ['git diff', 'git log', 'git rev-parse', 'git merge-base']
    
    if not any(cmd.strip().startswith(allowed_cmd) for allowed_cmd in allowed_git_commands):
        print(f"Ошибка: неразрешенная git команда: {cmd}")
        return ""
    
    try:
        # Безопасно разбиваем команду на аргументы
        cmd_parts = cmd.strip().split()
        
        result = subprocess.run(
            cmd_parts,  # Используем список вместо строки для безопасности
            capture_output=True, 
            text=True,
            timeout=30,  # Таймаут 30 секунд
            check=False  # Не поднимаем исключение при ненулевом коде возврата
        )
        
        if result.returncode != 0:
            print(f"Предупреждение: команда '{' '.join(cmd_parts)}' завершилась с кодом {result.returncode}")
            if result.stderr:
                print(f"Stderr: {result.stderr}")
            
        return result.stdout.strip()
        
    except subprocess.TimeoutExpired:
        print(f"Ошибка: команда '{cmd}' превысила таймаут")
        return ""
    except Exception as e:
        print(f"Ошибка выполнения команды '{cmd}': {e}")
        return ""

def get_changes(base_branch=None):
    """Получает изменения в Pull Request с полной валидацией"""
    if not base_branch:
        print("Ошибка: базовая ветка не указана")
        sys.exit(1)
    
    # Дополнительная валидация базовой ветки
    if not isinstance(base_branch, str) or base_branch.strip() == '':
        print(f"Ошибка: некорректная базовая ветка: {base_branch}")
        sys.exit(1)
        
    # Проверка на потенциально опасные символы
    dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>']
    if any(char in base_branch for char in dangerous_chars):
        print(f"Ошибка: базовая ветка содержит опасные символы: {base_branch}")
        sys.exit(1)
    
    base_branch = base_branch.strip()
    print(f"Сравниваю с веткой: {base_branch}")
    
    try:
        base_sha = f'origin/{base_branch}'
        
        diff = run_cmd(f'git diff --name-status {base_sha}..HEAD')
        detailed_diff = run_cmd(f'git diff {base_sha}..HEAD')
        commit_msg = run_cmd('git log -1 --pretty=format:"%s"')

        return {
            'files': diff,
            'diff': detailed_diff[:10000],  # Увеличиваем лимит для diff
            'commit_msg': commit_msg
        }
        
    except Exception as e:
        print(f"Ошибка получения изменений: {e}")
        sys.exit(1)

def create_analysis_prompt(changes):
    """Создает промпт для AI анализа"""
    return f"""
Ты опытный senior разработчик. Проанализируй изменения в коде на основе diff.

**Коммит**: {changes['commit_msg']}

**Измененные файлы**:
{changes['files']}

**Diff изменений**:
```diff
{changes['diff']}
```

Найди проблемы в коде, которые нужно исправить:

**ОБЯЗАТЕЛЬНО АНАЛИЗИРУЙ:**
- Синтаксические ошибки (опечатки в переменных, лишние символы)
- Неопределенные переменные и функции  
- Ошибки компиляции/выполнения
- Уязвимости безопасности (SQL injection, XSS)
- Утечки конфиденциальных данных (пароли, токены в коде)
- Критические проблемы производительности
- Явные нарушения архитектуры
- Сломанный функционал

**НЕ АНАЛИЗИРУЙ:**
- Версии зависимостей и пакетов (если не уязвимы)
- Проверки импортов библиотек в CI/CD
- Мелкие улучшения обработки ошибок
- Конфигурационные настройки (Python версии и т.д.)
- Стиль именования (если переменная определена)

Для каждой проблемы укажи файл и строку: `файл.js:строка`

Если проблем НЕТ - ответь точно: "НЕТ ПРОБЛЕМ"

Пример ответа:
```
**auth.js:15** - SQL инъекция: прямая подстановка user_id без экранирования
**main.ts:13** - Переменная err2 не определена, должно быть err
**config.js:8** - Пароль базы данных захардкожен в коде  
**api.ts:23** - Синтаксическая ошибка: лишняя запятая в объекте
```

ВАЖНО: Обязательно найди опечатки и синтаксические ошибки!
"""

def call_ai_api(prompt):
    """Вызывает AI API для анализа с полной обработкой ошибок"""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY не настроен")
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.1
        )
        
        if not response or not response.choices:
            raise ValueError("Пустой ответ от AI API")
            
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Пустое содержимое в ответе AI")
            
        return content.strip()
        
    except Exception as api_error:
        print(f"Ошибка вызова AI API: {api_error}")
        raise

def parse_ai_response(review_text):
    """Парсит ответ AI и определяет наличие проблем"""
    has_issues = not (review_text == "НЕТ ПРОБЛЕМ" or 
                     "нет проблем" in review_text.lower() or
                     "проблем не найдено" in review_text.lower())
    
    return {
        "has_issues": has_issues,
        "review": review_text
    }

def analyze_with_ai(changes):
    """Анализирует изменения с помощью AI"""
    if not GROQ_API_KEY:
        return {"has_issues": True, "review": "GROQ_API_KEY не настроен"}

    try:
        prompt = create_analysis_prompt(changes)
        review_text = call_ai_api(prompt)
        return parse_ai_response(review_text)
        
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
    """Публикует комментарий в PR с проверками существования"""
    if not GITHUB_TOKEN:
        print("GitHub Token не найден")
        return False

    repo_name = os.getenv('GITHUB_REPOSITORY')
    if not repo_name:
        print("Repository не найден в переменных окружения")
        return False

    try:
        g = Github(GITHUB_TOKEN)
        
        # Проверяем существование репозитория
        try:
            repo = g.get_repo(repo_name)
        except Exception as repo_error:
            print(f"Ошибка доступа к репозиторию {repo_name}: {repo_error}")
            return False

        comment = f"""## AI Code Review

{review}

---
*Автоматический анализ от AI Reviewer*"""

        # Получаем номер PR и проверяем его существование
        pr_number = get_pr_number()
        if not pr_number:
            print("Не удалось получить номер PR из GitHub event")
            return False
            
        try:
            pr = repo.get_pull(pr_number)
            # Проверяем, что PR открыт
            if pr.state != 'open':
                print(f"PR #{pr_number} не открыт (состояние: {pr.state})")
                return False
                
        except Exception as pr_error:
            print(f"Ошибка доступа к PR #{pr_number}: {pr_error}")
            return False
            
        # Публикуем комментарий
        try:
            pr.create_issue_comment(comment)
            print(f"Комментарий добавлен в PR #{pr_number}")
            return True
        except Exception as comment_error:
            print(f"Ошибка создания комментария в PR #{pr_number}: {comment_error}")
            return False
            
    except Exception as e:
        print(f"Общая ошибка публикации: {e}")
        return False

def main():
    """Основная функция с полной обработкой ошибок"""
    try:
        print("AI Code Reviewer")
        
        # Проверяем API ключи в начале
        if not validate_api_keys():
            print("Не удалось загрузить API ключи")
            sys.exit(1)
        
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
            
    except KeyboardInterrupt:
        print("\nПрерывание выполнения пользователем")
        sys.exit(1)
    except SystemExit:
        # Позволяем sys.exit() работать нормально
        raise
    except Exception as e:
        print(f"Критическая ошибка в main(): {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
