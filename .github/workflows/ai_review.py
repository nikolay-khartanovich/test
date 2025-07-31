#!/usr/bin/env python3
"""
AI Code Reviewer - analyzes changes in the repository
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
    """Executes a git command"""
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
        'diff': detailed_diff[:10000],  # Increase limit for diff
        'commit_msg': run_cmd('git log -1 --pretty=format:"%s"')
    }

def analyze_with_ai(changes):
    """Analyzes changes using AI"""
    if not GROQ_API_KEY:
        return {"has_issues": True, "review": "GROQ_API_KEY not configured"}

    client = Groq(api_key=GROQ_API_KEY)

    prompt = """
You are an experienced senior developer. Analyze code changes based on the diff.

**Commit**: """ + changes['commit_msg'] + """

**Changed files**:
""" + changes['files'] + """

**Diff changes**:
```diff
""" + changes['diff'] + """
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

**IMPORTANT LOGIC:**
- "NO ISSUES" - ONLY if nothing is actually found
- Don't make general conclusions like "overall code is good" if there are issues

**DON'T analyze:**
- Dependency versions (unless vulnerable)
- Project names in titles/descriptions (not a code issue)

For each found issue specify: file.ext:line - description + show the problematic code

**Response format:**

If there are issues, show each with code snippet:

**file1.ts:11** - Using undefined variable err22 instead of err
```js
console.error('Meticulous failed to initialise: ${err22}');
//                                                ^^^^^ should be: err
```

**file2.js:45** - Missing error handling in async function
```js
async function fetchData() {
    return await api.get('/data'); // No try-catch block
}
```

**file3.tsx:12** - Deep nesting - consider extracting to separate functions
```jsx
for (let i = 0; i < items.length; i++) {
  if (items[i].active) {
    for (let j = 0; j < items[i].children.length; j++) {
      if (items[i].children[j].visible) {
        for (let k = 0; k < items[i].children[j].data.length; k++) {
          // 4 levels deep - too complex
        }
      }
    }
  }
}
```

**file4.js:23** - Function with too many parameters
```js
function processUser(id, name, email, phone, address, age, role, status) {
  // Consider using object parameter instead
}
```

If no issues - write only:
```
NO ISSUES
```

if issues are found, not write "NO ISSUES" in context of the review. Write "Rewiewer by LLLM models" and write model name

Don't add general conclusions, summaries or phrases like "overall code looks good".
ONLY list of issues with code snippets OR "NO ISSUES".
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.1
        )
        
        review_text = response.choices[0].message.content.strip()
        
        # Smart detection of issues presence
        has_issues = True  # By default assume there are issues
        
        # Only if AI clearly wrote "NO ISSUES" and nothing else substantial
        if review_text == "NO ISSUES" or (
            "NO ISSUES" in review_text and 
            len(review_text.replace("NO ISSUES", "").strip()) < 10
        ):
            has_issues = False
        
        # Additional check - if there are references to specific files with issues
        if "**" in review_text and ":" in review_text:
            has_issues = True
            
        # If there are words indicating problems
        problem_indicators = [
            "issue", "error", "bug", "vulnerabilit", "violation", 
            "undefined", "null", "warning", "fix", "problem"
        ]
        
        if any(indicator in review_text.lower() for indicator in problem_indicators):
            has_issues = True
        
        return {
            "has_issues": has_issues,
            "review": review_text
        }
        
    except Exception as e:
        return {"has_issues": True, "review": f"AI Error: {e}"}

def get_pr_number():
    """Gets PR number from GitHub event"""
    event_path = os.getenv('GITHUB_EVENT_PATH')
    if not event_path or not os.path.exists(event_path):
        return None
    
    try:
        with open(event_path, 'r') as f:
            event_data = json.load(f)
        return event_data.get('pull_request', {}).get('number')
    except Exception as e:
        print(f"Event reading error: {e}")
        return None

def post_comment(review):
    """Posts comment to PR"""
    if not GITHUB_TOKEN:
        print("GitHub Token not found")
        return False

    repo_name = os.getenv('GITHUB_REPOSITORY')
    if not repo_name:
        print("Repository not found")
        return False

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(repo_name)

        comment = f"""## AI Code Review

{review}"""
        # Get PR number and post comment
        pr_number = get_pr_number()
        if pr_number:
            pr = repo.get_pull(pr_number)
            pr.create_issue_comment(comment)
            print(f"Comment added to PR #{pr_number}")
            return True
        else:
            print("Unable to get PR number")
            return False
            
    except Exception as e:
        print(f"Publishing error: {e}")
        return False

def main():
    # Base branch is required for PR
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
            print("Error publishing comment, but issues were found")
            
        sys.exit(1)  # Exit with error
    else:
        # No issues - exit successfully without comment
        print("\nCode looks good! No critical issues found.")
        print("No comment required - changes approved.")
        sys.exit(0)  # Successful completion

if __name__ == "__main__":
    main()
