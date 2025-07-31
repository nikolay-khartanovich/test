#!/usr/bin/env python3
"""
AI Code Reviewer - анализирует изменения в репозитории с помощью нескольких AI моделей
"""

import os
import subprocess
import json
import sys
from groq import Groq
from github import Github

# Константы конфигурации
MAX_TOKENS_ANALYSIS = 1000
MAX_TOKENS_SYNTHESIS = 1200
MAX_DIFF_LENGTH = 10000
TEMPERATURE_ANALYSIS = 0.1
TEMPERATURE_SYNTHESIS = 0.2

# Настройки
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

def run_cmd(cmd):
    """Выполняет git команду и возвращает результат"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""

def get_changes(base_branch=None):
    """Получает изменения в Pull Request"""
    if not base_branch:
        print("Ошибка: базовая ветка не указана")
        sys.exit(1)
    
    print(f"Сравниваем с веткой: {base_branch}")
    base_sha = f'origin/{base_branch}'
    
    diff = run_cmd(f'git diff --name-status {base_sha}..HEAD')
    detailed_diff = run_cmd(f'git diff {base_sha}..HEAD')

    return {
        'files': diff,
        'diff': detailed_diff[:MAX_DIFF_LENGTH],
        'commit_msg': run_cmd('git log -1 --pretty=format:"%s"')
    }

def create_analysis_prompt(changes):
    """Создает prompt для анализа одной моделью"""
    return f"""
You are an experienced senior developer. Analyze code changes based on the diff.

**Commit**: {changes['commit_msg']}

**Changed files**:
{changes['files']}

**Diff changes**:
```diff
{changes['diff']}
```

Conduct thorough code analysis and find ALL issues:

**1. CRITICAL issues:**
- Security vulnerabilities (SQL injection, XSS, CSRF)
- Secret leaks (passwords, tokens, keys in code)
- Critical bugs (NPE, memory leaks, undefined variables, syntax errors)
- Serious architecture violations

**2. CODE QUALITY & BEST PRACTICES:**
- SOLID, DRY, KISS principle violations
- Poor architecture and code structure
- Non-optimal performance
- Missing error handling
- Magic numbers and hardcoded values
- Deep nesting (avoid loops/conditions more than 3 levels deep)
- Long methods/functions (more than 20-30 lines)
- Functions with too many parameters (more than 4-5)
- Complex conditional statements (multiple && || operators)
- Repeated code patterns that should be extracted
- Missing early returns (prefer guard clauses)
- Pyramid of doom (deeply nested callbacks/promises)
- Switch statements that should be polymorphism
- Violation of single responsibility principle
- God objects/classes (too many responsibilities)
- Tight coupling between components
- Missing abstractions for complex logic
- Synchronous operations that should be async
- Missing null/undefined checks
- Improper exception handling (catching generic exceptions)

**3. STYLE AND CLEANLINESS:**
- Poor variable/function/class names
- Excessive method complexity
- Coding standards violations
- Missing comments in complex places
- Code duplication
- Inconsistent formatting
- Dead code (unused variables, functions)
- Console.log statements in production code
- TODO/FIXME comments without context

**IMPORTANT:**
- Be specific and precise in your analysis
- Focus on actual code issues, not theoretical problems
- If no issues found, write only "NO ISSUES"

For each found issue specify: file.ext:line - description + show the problematic code

Response format - list specific issues with code snippets or "NO ISSUES".
"""

def analyze_with_single_model(changes, model_name):
    """Анализирует изменения одной конкретной моделью"""
    if not GROQ_API_KEY:
        return {"model": model_name, "review": "GROQ_API_KEY не настроен", "error": True}

    try:
        client = Groq(api_key=GROQ_API_KEY)
        prompt = create_analysis_prompt(changes)
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=MAX_TOKENS_ANALYSIS,
            temperature=TEMPERATURE_ANALYSIS
        )
        
        review_text = response.choices[0].message.content.strip()
        
        return {
            "model": model_name,
            "review": review_text,
            "error": False
        }
        
    except Exception as e:
        return {
            "model": model_name,
            "review": f"Ошибка анализа: {e}",
            "error": True
        }

def create_synthesis_prompt(model_reviews):
    """Создает prompt для синтеза итогового отчета"""
    reviews_text = ""
    for review_data in model_reviews:
        if not review_data["error"]:
            reviews_text += f"\n**АНАЛИЗ МОДЕЛИ {review_data['model']}:**\n{review_data['review']}\n"
    
    successful_models = [r["model"] for r in model_reviews if not r["error"]]
    models_list = ', '.join(successful_models)
    
    return f"""
Ты опытный ведущий разработчик. У тебя есть анализы кода от нескольких AI моделей. Твоя задача - создать итоговый грамотный отчет.

{reviews_text}

**ТВОЯ ЗАДАЧА:**
1. Проанализируй все мнения моделей
2. Выдели только РЕАЛЬНЫЕ проблемы (не дублируй одинаковые)
3. Проигнорируй ложные срабатывания
4. Создай четкий структурированный отчет
5. ОБЯЗАТЕЛЬНО покажи код для каждой проблемы

**ФОРМАТ ОТВЕТА:**

Если есть проблемы, показывай КАЖДУЮ проблему с кодом:

- file.ext:line - описание проблемы
```code
проблемный код из файла
```

- file.ext:line - описание проблемы
```code
проблемный код из файла
```

- file.ext:line - описание проблемы
```code
проблемный код из файла
```

---
*Reviewed by AI Ensemble: {models_list}*

Если проблем НЕТ:
```
NO ISSUES
```

ВАЖНО: Для каждой проблемы ОБЯЗАТЕЛЬНО приводи конкретный код! Будь конкретен, не добавляй общие фразы.
"""

def create_final_report(model_reviews):
    """Создает итоговый отчет на основе анализов нескольких моделей"""
    if not GROQ_API_KEY:
        return {"has_issues": True, "review": "GROQ_API_KEY не настроен"}

    try:
        client = Groq(api_key=GROQ_API_KEY)
        synthesis_prompt = create_synthesis_prompt(model_reviews)
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": synthesis_prompt}],
            max_tokens=MAX_TOKENS_SYNTHESIS,
            temperature=TEMPERATURE_SYNTHESIS
        )
        
        final_review = response.choices[0].message.content.strip()
        
        # Определяем есть ли проблемы
        has_issues = not (final_review == "NO ISSUES" or (
            "NO ISSUES" in final_review and 
            len(final_review.replace("NO ISSUES", "").strip()) < 10
        ))
        
        return {
            "has_issues": has_issues,
            "review": final_review
        }
        
    except Exception as e:
        return {"has_issues": True, "review": f"Ошибка создания итогового отчета: {e}"}

def analyze_with_ai(changes):
    """Анализирует изменения с помощью нескольких AI моделей и создает итоговый отчет"""
    
    # Список моделей для анализа
    models_to_use = [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile", 
        "mixtral-8x7b-32768",
        "gemma2-9b-it"
    ]
    
    print("Запускаем анализ несколькими моделями...")
    
    # Получаем анализы от разных моделей
    model_reviews = []
    for model in models_to_use:
        print(f"Анализ модели {model}...")
        review = analyze_with_single_model(changes, model)
        model_reviews.append(review)
        
        if review["error"]:
            print(f"Ошибка в модели {model}: {review['review']}")
        else:
            print(f"Модель {model} завершил анализ")
    
    # Проверяем что хотя бы одна модель сработала
    successful_reviews = [r for r in model_reviews if not r["error"]]
    if not successful_reviews:
        return {"has_issues": True, "review": "Все модели вернули ошибки"}
    
    print("Создаем итоговый отчет...")
    final_result = create_final_report(model_reviews)
    
    print("Анализ завершен!")
    return final_result

def get_pr_number_from_event():
    """Получает номер PR из GitHub event"""
    event_path = os.environ.get('GITHUB_EVENT_PATH')
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
    """Публикует комментарий в PR с обработкой ошибок"""
    if not GITHUB_TOKEN:
        print("GitHub Token не найден")
        return False

    repo_name = os.environ.get('GITHUB_REPOSITORY')
    if not repo_name:
        print("Репозиторий не найден")
        return False

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(repo_name)

        comment = f"""## AI Code Review

{review}"""
        
        pr_number = get_pr_number_from_event()
        if not pr_number:
            print("Не удалось получить номер PR")
            return False
            
        pr = repo.get_pull(pr_number)
        pr.create_issue_comment(comment)
        print(f"Комментарий добавлен в PR #{pr_number}")
        return True
        
    except Exception as e:
        print(f"Ошибка публикации: {e}")
        return False

def main():
    """Основная функция - точка входа в программу"""
    # Базовая ветка обязательна для PR
    if len(sys.argv) < 2:
        print("Ошибка: базовая ветка не указана")
        sys.exit(1)
        
    base_branch = sys.argv[1]
    print(f"Базовая ветка: {base_branch}")

    # Получаем изменения
    changes = get_changes(base_branch)

    if not changes['files']:
        print("Нет изменений для анализа")
        sys.exit(0)

    # AI анализ
    result = analyze_with_ai(changes)

    if result["has_issues"]:
        # Найдены проблемы - публикуем комментарий и завершаем с ошибкой
        print("\nКритические проблемы найдены в коде!")
        
        success = post_comment(result["review"])
        if success:
            print("Комментарий с проблемами успешно опубликован")
        else:
            print("Ошибка публикации комментария, но проблемы найдены")
            
        sys.exit(1)  # Завершение с ошибкой
    else:
        # Проблем нет - завершаем успешно без комментария
        print("\nКод выглядит хорошо! Критических проблем не найдено.")
        print("Комментарий не требуется - изменения одобрены.")
        sys.exit(0)  # Успешное завершение

if __name__ == "__main__":
    main()
