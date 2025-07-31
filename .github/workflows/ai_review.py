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
MAX_TOKENS_ANALYSIS = 2000  # Increased for more detailed code examples
MAX_TOKENS_SYNTHESIS = 2500  # Increased for detailed final report
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

**CRITICAL REQUIREMENTS FOR CODE EXAMPLES:**
- For EVERY issue you find, you MUST show the COMPLETE problematic code fragment
- Include AT LEAST 3-5 lines of context BEFORE and AFTER the problematic line
- Show the FULL function/method if it's short (under 15 lines)
- DO NOT use placeholder comments like "# ... rest of code ..." or "// ... existing code ..."
- Show REAL, ACTUAL code from the diff

**IMPORTANT:**
- Be specific and precise in your analysis
- Focus on actual code issues, not theoretical problems
- If no issues found, write only "NO ISSUES"

**RESPONSE FORMAT - MANDATORY:**
For each issue use this EXACT format:

file.ext:line - detailed description of the problem
```language
actual complete code fragment with sufficient context
```

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

def create_synthesis_prompt(model_reviews):
    """Creates prompt for synthesis of final report"""
    reviews_text = ""
    for review_data in model_reviews:
        if not review_data["error"]:
            reviews_text += f"\n**MODEL ANALYSIS {review_data['model']}:**\n{review_data['review']}\n"
    
    successful_models = [r["model"] for r in model_reviews if not r["error"]]
    models_list = ', '.join(successful_models)
    
    return f"""
You are an experienced senior developer. You have code analyses from multiple AI models. Your task is to create a comprehensive final report.

{reviews_text}

**YOUR TASK:**
1. Analyze all model opinions
2. Extract only REAL issues (don't duplicate the same ones)
3. Ignore false positives
4. Create a clear structured report
5. MANDATORY show COMPLETE code for each issue

**CRITICAL CODE REQUIREMENTS:**
- For EVERY issue show COMPLETE code fragment with context
- Include minimum 5-10 lines of context around the problematic line
- DO NOT use placeholders like "# ... rest of code ...", "// ... existing code ..."
- Show REAL code from diff, not examples
- If function is short (up to 20 lines) - show it entirely
- Specify correct line numbers

**RESPONSE FORMAT:**

If there are issues, for EVERY issue use EXACTLY this format:

- file.ext:line - detailed description of the issue and how to fix it
```python
def example_function():
    # show real code with sufficient context
    # minimum 5-10 lines around problematic line
    # no placeholders or ellipsis!
    problematic_line = "real code here"
    return result
```

- file.ext:line - another issue
```python
class ExampleClass:
    def method_with_issue(self):
        # complete context of real code
        real_problematic_code = value
        return something
```

---
*Reviewed by AI Ensemble: {models_list}*

If NO issues:
```
NO ISSUES
```

**ABSOLUTELY CRITICAL:** 
- DON'T abbreviate code! Show enough lines to understand context!
- DON'T use "..." or placeholders in code!
- Every example must contain REAL code from the file!
"""

def create_final_report(model_reviews):
    """Creates final report based on analyses from multiple models"""
    if not GROQ_API_KEY:
        return {"has_issues": True, "review": "GROQ_API_KEY not configured"}

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
        "llama-3.1-70b-versatile", 
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
    final_result = create_final_report(model_reviews)
    
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
