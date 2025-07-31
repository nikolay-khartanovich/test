#!/usr/bin/env python3
"""
AI Code Reviewer - analyzes repository changes using multiple AI models
"""

import os
import subprocess
import json
import sys
from groq import Groq
from github import Github

# Configuration constants
MAX_TOKENS_ANALYSIS = 3000  # Increased for real code examples with context
MAX_TOKENS_SYNTHESIS = 4000  # Increased for detailed final report with real code
MAX_DIFF_LENGTH = 10000
TEMPERATURE_ANALYSIS = 0.1
TEMPERATURE_SYNTHESIS = 0.2

# Settings
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

def run_cmd(cmd):
    """Executes git command and returns result"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""

def get_changes(base_branch=None):
    """Gets changes in Pull Request"""
    if not base_branch:
        print("Error: base branch not specified")
        sys.exit(1)
    
    print(f"Comparing with branch: {base_branch}")
    base_sha = f'origin/{base_branch}'
    
    diff = run_cmd(f'git diff --name-status {base_sha}..HEAD')
    detailed_diff = run_cmd(f'git diff {base_sha}..HEAD')

    return {
        'files': diff,
        'diff': detailed_diff[:MAX_DIFF_LENGTH],
        'commit_msg': run_cmd('git log -1 --pretty=format:"%s"')
    }

def create_analysis_prompt(changes):
    """Creates prompt for analysis by a single model"""
    return f"""
You are an experienced senior developer. Analyze code changes based on the diff.

**CRITICAL INSTRUCTION: You MUST only analyze files shown in "Changed files" below. NEVER analyze files not in this list.**

**Commit**: {changes['commit_msg']}

**Changed files (ONLY analyze these files):**
{changes['files']}

**Diff changes:**
```diff
{changes['diff']}
```

**STRICT LIMITATIONS:**
- ONLY analyze files listed in "Changed files" above
- NEVER analyze files not mentioned in the changed files list
- NEVER invent code that doesn't exist in the diff
- If a file has no actual changes in the diff, don't analyze it

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

**CRITICAL REQUIREMENTS FOR CODE EXAMPLES:**
- For EVERY issue you find, you MUST show the EXACT REAL CODE from the provided diff
- Include AT LEAST 5-10 lines of context BEFORE and AFTER the problematic line
- Show the FULL function/method if it's short (under 20 lines)
- ABSOLUTELY FORBIDDEN: making up code, synthetic examples, placeholder comments
- ONLY show code that ACTUALLY EXISTS in the provided diff above
- Copy-paste the EXACT lines from the diff - don't paraphrase or rewrite

**STRICT VERIFICATION RULES:**
- Before writing any code example, verify it exists EXACTLY in the provided diff
- If you cannot find the exact code in the diff, DO NOT create synthetic examples
- Every line of code you show must be traceable to the actual diff content
- Match indentation, spacing, and syntax EXACTLY as shown in diff

**IMPORTANT:**
- Be specific and precise in your analysis
- Focus on actual code issues, not theoretical problems
- If no issues found, write only "NO ISSUES"
- NEVER invent code examples - only use what's actually in the diff

**RESPONSE FORMAT - MANDATORY:**
For each issue use this EXACT format:

file.ext:line - detailed description of the problem

```language
# ТЕКУЩИЙ КОД (из diff):
Copy-paste EXACT current code from the diff above (5-10 lines context)  # ❌ Описание проблемы

# ИСПРАВЛЕННЫЙ КОД:
Show how the code should be fixed with improvements marked  # ✅ Объяснение исправления
```

**EXAMPLE OF CORRECT FORMAT:**

**ai_review.py:25 - Missing error handling in subprocess call**

```python
# ТЕКУЩИЙ КОД (проблема):
def run_cmd(cmd):
    """Executes git command and returns result"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)  # ❌ Нет обработки ошибок
    return result.stdout.strip() if result.returncode == 0 else ""

# ИСПРАВЛЕННЫЙ КОД:
def run_cmd(cmd):
    """Executes git command and returns result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)  # ✅ Добавлен timeout
        if result.returncode != 0:
            print(f"Git command failed: {result.stderr}")  # ✅ Показываем ошибку
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception as e:  # ✅ Обрабатываем исключения
        print(f"Error executing command: {e}")
        return ""
```

**CRITICAL RULES:**
- ONLY analyze files that appear in the diff above
- CURRENT CODE section must be EXACT copy from diff
- If you cannot find exact code in diff, skip this issue
- Never analyze files not mentioned in the "Changed files" section
- Always provide both CURRENT CODE and SUGGESTED FIX sections

If no issues: "NO ISSUES"
"""

def analyze_with_single_model(changes, model_name):
    """Analyzes changes with a single specific model"""
    if not GROQ_API_KEY:
        return {"model": model_name, "review": "GROQ_API_KEY not configured", "error": True}

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
            "review": f"Analysis error: {e}",
            "error": True
        }

def create_synthesis_prompt(model_reviews, changed_files=""):
    """Creates prompt for synthesis of final report"""
    reviews_text = ""
    for review_data in model_reviews:
        if not review_data["error"]:
            reviews_text += f"\n**MODEL ANALYSIS {review_data['model']}:**\n{review_data['review']}\n"
    
    successful_models = [r["model"] for r in model_reviews if not r["error"]]
    models_list = ', '.join(successful_models)
    
    return f"""
You are an experienced senior developer. You have code analyses from multiple AI models. Your task is to create a comprehensive final report.

**FILES ACTUALLY CHANGED (only analyze these):**
{changed_files}

**CRITICAL RULES:**
1. Only use code examples that were actually provided in the model analyses below
2. Only include issues for files listed in "FILES ACTUALLY CHANGED" above
3. Never create synthetic examples or analyze non-existent files
4. If a model analyzed a file that doesn't exist in the changed files, ignore that analysis

{reviews_text}

**VERIFICATION CHECKLIST:**
- Only report issues for files that appear in "FILES ACTUALLY CHANGED"
- Ignore any model analysis of non-existent or unmodified files  
- Copy real code from analyses, never invent examples

**YOUR TASK:**
1. Analyze all model opinions
2. Extract only REAL issues (don't duplicate the same ones)
3. Ignore false positives
4. Create a clear structured report
5. MANDATORY show COMPLETE code for each issue

**CRITICAL CODE REQUIREMENTS - ABSOLUTELY MANDATORY:**
- For EVERY issue show EXACT code fragment from the original diff analysis
- Include minimum 8-15 lines of context around the problematic line
- ABSOLUTELY FORBIDDEN: creating synthetic code examples or fake code
- ONLY copy-paste REAL code that was provided in the model analyses above
- If you cannot find real code in the analyses, write "Code example unavailable" instead
- Match indentation, spacing, variable names, and syntax EXACTLY
- Verify every code line exists in the provided model analyses before including it

**RESPONSE FORMAT:**

If there are issues, for EVERY issue use EXACTLY this format:

**file.ext:line - detailed description of the issue and how to fix it**

```language
# ТЕКУЩИЙ КОД (из оригинального diff):
Copy-paste exact current code from model analyses above (with sufficient context)  # ❌ Описание проблемы

# ИСПРАВЛЕННЫЙ КОД:
Show the corrected version of the code with improvements  # ✅ Объяснение исправления
```

**EXAMPLES OF CORRECT REPORT FORMAT:**

**Example 1: Error handling issue**
**ai_review.py:25 - Function handles errors poorly and should include proper exception handling**

```python
# ТЕКУЩИЙ КОД (из оригинального diff):
def run_cmd(cmd):
    """Executes git command and returns result"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)  # ❌ Нет обработки ошибок и timeout
    return result.stdout.strip() if result.returncode == 0 else ""

# ИСПРАВЛЕННЫЙ КОД:
def run_cmd(cmd):
    """Executes git command and returns result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)  # ✅ Добавлен timeout
        if result.returncode != 0:
            print(f"Git command failed: {result.stderr}")  # ✅ Логируем ошибки
            return ""
        return result.stdout.strip()
    except subprocess.TimeoutExpired:  # ✅ Обработка timeout
        print(f"Command timed out: {cmd}")
        return ""
    except Exception as e:  # ✅ Общая обработка исключений
        print(f"Error executing command: {e}")
        return ""
```

**Example 2: Magic numbers**
**ai_review.py:14 - Magic numbers should be extracted to named constants**

```python
# ТЕКУЩИЙ КОД (из оригинального diff):
MAX_TOKENS_ANALYSIS = 3000  # ❌ Магические числа без объяснения логики
MAX_TOKENS_SYNTHESIS = 4000  # ❌ Непонятно почему именно эти значения

# ИСПРАВЛЕННЫЙ КОД:
# Token limits configuration with clear reasoning
ANALYSIS_BASE_TOKENS = 1500      # ✅ Базовый размер для анализа
ANALYSIS_CONTEXT_TOKENS = 1500   # ✅ Дополнительные токены для контекста
SYNTHESIS_BASE_TOKENS = 2000     # ✅ Базовый размер для синтеза  
SYNTHESIS_EXAMPLES_TOKENS = 2000 # ✅ Токены для примеров кода

MAX_TOKENS_ANALYSIS = ANALYSIS_BASE_TOKENS + ANALYSIS_CONTEXT_TOKENS      # ✅ 3000
MAX_TOKENS_SYNTHESIS = SYNTHESIS_BASE_TOKENS + SYNTHESIS_EXAMPLES_TOKENS  # ✅ 4000
```

**Example 3: Missing null checks**
**ai_review.py:45 - Function doesn't validate input parameters**

```python
# ТЕКУЩИЙ КОД (из оригинального diff):
def get_changes(base_branch=None):
    """Gets changes in Pull Request"""
    if not base_branch:  # ❌ Проверка только на falsy значения
        print("Error: base branch not specified")
        sys.exit(1)
    
    print(f"Comparing with branch: {base_branch}")  # ❌ Нет валидации формата ветки
    base_sha = f'origin/{base_branch}'
    
# ИСПРАВЛЕННЫЙ КОД:
def get_changes(base_branch=None):
    """Gets changes in Pull Request"""
    if not base_branch or not isinstance(base_branch, str) or not base_branch.strip():  # ✅ Полная валидация
        print("Error: base branch must be a non-empty string")
        sys.exit(1)
    
    base_branch = base_branch.strip()  # ✅ Очищаем пробелы
    if '/' in base_branch and not base_branch.startswith('origin/'):  # ✅ Валидация формата
        print(f"Warning: unusual branch format: {base_branch}")
    
    print(f"Comparing with branch: {base_branch}")
    base_sha = f'origin/{base_branch}'
```

**STRICT RULES:**
- Use SINGLE code block with both current and fixed code
- Mark problematic lines with # ❌ comments explaining issues
- Mark improvements with # ✅ comments explaining fixes
- Copy exact current code from model analyses, never invent
- Only include issues for files that actually exist in the diff
- If model analysis doesn't show real code, write "Code example not available"
- Always use format: "# ТЕКУЩИЙ КОД" followed by "# ИСПРАВЛЕННЫЙ КОД" in same block

---
*Reviewed by AI Ensemble: {models_list}*

If NO issues:
```
NO ISSUES
```

**ABSOLUTELY CRITICAL - FINAL VERIFICATION:** 
- Before including ANY code example, double-check it exists in the model analyses above
- DON'T abbreviate code! Show enough lines to understand context!
- DON'T use "..." or placeholders in code!
- NEVER create synthetic examples - only copy-paste from model analyses
- If model analyses don't contain proper code examples, write "Code example not available from analyses"
- Every single line of code must be traceable to the provided model analyses
- When in doubt, skip the code example rather than inventing one
"""

def create_final_report(model_reviews, changed_files=""):
    """Creates final report based on analyses from multiple models"""
    if not GROQ_API_KEY:
        return {"has_issues": True, "review": "GROQ_API_KEY not configured"}

    try:
        client = Groq(api_key=GROQ_API_KEY)
        synthesis_prompt = create_synthesis_prompt(model_reviews, changed_files)
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": synthesis_prompt}],
            max_tokens=MAX_TOKENS_SYNTHESIS,
            temperature=TEMPERATURE_SYNTHESIS
        )
        
        final_review = response.choices[0].message.content.strip()
        
        # Determine if there are issues
        has_issues = not (final_review == "NO ISSUES" or (
            "NO ISSUES" in final_review and 
            len(final_review.replace("NO ISSUES", "").strip()) < 10
        ))
        
        return {
            "has_issues": has_issues,
            "review": final_review
        }
        
    except Exception as e:
        return {"has_issues": True, "review": f"Error creating final report: {e}"}

def analyze_with_ai(changes):
    """Analyzes changes using multiple AI models and creates final report"""
    
    # List of models for analysis
    models_to_use = [
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
        "gemma2-9b-it"
    ]
    
    print("Starting analysis with multiple models...")
    
    # Get analyses from different models
    model_reviews = []
    for model in models_to_use:
        print(f"Analyzing with model {model}...")
        review = analyze_with_single_model(changes, model)
        model_reviews.append(review)
        
        if review["error"]:
            print(f"Error in model {model}: {review['review']}")
        else:
            print(f"Model {model} completed analysis")
    
    # Check that at least one model worked
    successful_reviews = [r for r in model_reviews if not r["error"]]
    if not successful_reviews:
        return {"has_issues": True, "review": "All models returned errors"}
    
    print("Creating final report...")
    final_result = create_final_report(model_reviews, changes['files'])
    
    print("Analysis completed!")
    return final_result

def get_pr_number_from_event():
    """Gets PR number from GitHub event"""
    event_path = os.environ.get('GITHUB_EVENT_PATH')
    if not event_path or not os.path.exists(event_path):
        return None
    
    try:
        with open(event_path, 'r') as f:
            event_data = json.load(f)
        return event_data.get('pull_request', {}).get('number')
    except Exception as e:
        print(f"Error reading event: {e}")
        return None

def post_comment(review):
    """Posts comment to PR with error handling"""
    if not GITHUB_TOKEN:
        print("GitHub Token not found")
        return False

    repo_name = os.environ.get('GITHUB_REPOSITORY')
    if not repo_name:
        print("Repository not found")
        return False

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(repo_name)

        comment = f"""## AI Code Review

{review}"""
        
        pr_number = get_pr_number_from_event()
        if not pr_number:
            print("Failed to get PR number")
            return False
            
        pr = repo.get_pull(pr_number)
        pr.create_issue_comment(comment)
        print(f"Comment added to PR #{pr_number}")
        return True
        
    except Exception as e:
        print(f"Publishing error: {e}")
        return False

def main():
    """Main function - program entry point"""
    # Base branch is mandatory for PR
    if len(sys.argv) < 2:
        print("Error: base branch not specified")
        sys.exit(1)
        
    base_branch = sys.argv[1]
    print(f"Base branch: {base_branch}")

    # Get changes
    changes = get_changes(base_branch)

    if not changes['files']:
        print("No changes to analyze")
        sys.exit(0)

    # AI analysis
    result = analyze_with_ai(changes)

    if result["has_issues"]:
        # Issues found - publish comment and exit with error
        print("\nCritical issues found in code!")
        
        success = post_comment(result["review"])
        if success:
            print("Comment with issues successfully published")
        else:
            print("Error publishing comment, but issues found")
            
        sys.exit(1)  # Exit with error
    else:
        # No issues - exit successfully without comment
        print("\nCode looks good! No critical issues found.")
        print("No comment required - changes approved.")
        sys.exit(0)  # Successful exit

if __name__ == "__main__":
    main()
