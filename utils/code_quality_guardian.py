"""
CodeQualityGuardian - Automated code review and quality analysis
Runs hourly to detect issues, suggest fixes, and recommend features
"""
import os
import re
import uuid
import logging
import subprocess
from datetime import datetime
from typing import List, Dict, Optional
import google.generativeai as genai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

logger = logging.getLogger(__name__)

# Retry configuration for Gemini API calls
RETRY_CONFIG = {
    'stop': stop_after_attempt(3),
    'wait': wait_exponential(multiplier=1, min=2, max=30),
    'retry': retry_if_exception_type((ResourceExhausted, ServiceUnavailable, ConnectionError, TimeoutError)),
    'before_sleep': before_sleep_log(logger, logging.WARNING),
    'reraise': True
}

ISSUE_TYPES = {
    'bug': 'Potential bug or logic error',
    'security': 'Security vulnerability or risk',
    'performance': 'Performance issue or optimization opportunity',
    'style': 'Code style or maintainability issue',
    'feature_suggestion': 'New feature recommendation'
}

SEVERITY_LEVELS = ['critical', 'high', 'medium', 'low', 'info']

REVIEW_PROMPT = """You are CodeQualityGuardian, an expert code reviewer for a Flask/Python web application called MedInvest.

Analyze the following code file and identify:
1. BUGS: Logic errors, potential crashes, undefined variables, type errors
2. SECURITY: SQL injection, XSS, CSRF, authentication bypasses, sensitive data exposure
3. PERFORMANCE: N+1 queries, inefficient loops, missing caching opportunities
4. STYLE: Dead code, code duplication, complex functions that should be refactored
5. FEATURE_SUGGESTIONS: Missing functionality, improvements based on code patterns

For each issue found, provide:
- issue_type: bug|security|performance|style|feature_suggestion
- severity: critical|high|medium|low|info
- line_number: approximate line number
- title: brief title (max 100 chars)
- description: detailed explanation
- suggested_fix: how to fix it (code snippet if applicable)
- auto_fixable: true if can be automatically fixed, false otherwise
- confidence: 0.0-1.0 how confident you are

Respond in JSON format:
{
    "issues": [
        {
            "issue_type": "bug",
            "severity": "high",
            "line_number": 42,
            "function_name": "process_payment",
            "title": "Missing null check on user object",
            "description": "The user object is accessed without checking if it exists first, which could cause AttributeError",
            "code_snippet": "user.email",
            "suggested_fix": "if user:\\n    user.email",
            "auto_fixable": false,
            "confidence": 0.9
        }
    ],
    "summary": "Found 3 issues: 1 high severity bug, 2 medium style issues"
}

Only report REAL issues with HIGH confidence. Do not report minor style preferences or theoretical issues.
Focus on actionable problems that would improve code quality.

FILE: {file_path}
```python
{code_content}
```
"""


class CodeQualityGuardian:
    """Main code quality review engine"""
    
    def __init__(self):
        self.api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('AI_INTEGRATIONS_GEMINI_API_KEY')
        self.model_name = 'gemini-2.0-flash'
        self.files_to_review = [
            'routes/*.py',
            'utils/*.py', 
            'models.py',
            'app.py',
            'main.py',
            'templates/*.html',
            'templates/**/*.html',
            'static/css/*.css',
            'static/js/*.js'
        ]
        self.exclude_patterns = [
            '__pycache__',
            '.pyc',
            'migrations/',
            'test_',
            '_test.py',
            'attached_assets/'
        ]
        
    def get_python_files(self) -> List[str]:
        """Get list of Python files to review"""
        import glob
        
        files = []
        for pattern in self.files_to_review:
            matches = glob.glob(pattern, recursive=True)
            files.extend(matches)
        
        filtered = []
        for f in files:
            exclude = False
            for excl in self.exclude_patterns:
                if excl in f:
                    exclude = True
                    break
            if not exclude and os.path.isfile(f):
                filtered.append(f)
        
        return filtered
    
    def analyze_file(self, file_path: str) -> List[Dict]:
        """Analyze a single file using AI"""
        if not self.api_key:
            logger.warning('No Gemini API key configured for code review')
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code_content = f.read()
        except Exception as e:
            logger.error(f'Failed to read file {file_path}: {e}')
            return []
        
        if len(code_content) > 50000:
            logger.info(f'Skipping {file_path} - too large for review')
            return []
        
        if len(code_content.strip()) < 50:
            return []
        
        try:
            issues = self._call_gemini_api(file_path, code_content)
            for issue in issues:
                issue['file_path'] = file_path
            return issues
            
        except Exception as e:
            logger.error(f'AI analysis failed for {file_path} after retries: {e}')
            return []
    
    @retry(**RETRY_CONFIG)
    def _call_gemini_api(self, file_path: str, code_content: str) -> List[Dict]:
        """Call Gemini API with retry logic and exponential backoff"""
        import json
        
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model_name)
        
        prompt = REVIEW_PROMPT.format(
            file_path=file_path,
            code_content=code_content
        )
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type='application/json',
                temperature=0.1
            )
        )
        
        result = json.loads(response.text)
        return result.get('issues', [])
    
    def run_static_analysis(self) -> List[Dict]:
        """Run static analysis tools (pylint, etc.)"""
        issues = []
        
        try:
            result = subprocess.run(
                ['python', '-m', 'py_compile', 'models.py'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                issues.append({
                    'issue_type': 'bug',
                    'severity': 'critical',
                    'file_path': 'models.py',
                    'title': 'Python syntax error',
                    'description': result.stderr,
                    'auto_fixable': False,
                    'confidence': 1.0
                })
        except Exception as e:
            logger.debug(f'Static analysis skipped: {e}')
        
        return issues
    
    def run_review(self) -> Dict:
        """Run a complete code review"""
        from app import db
        from models import CodeQualityIssue, CodeReviewRun
        
        run_id = str(uuid.uuid4())[:8]
        
        review_run = CodeReviewRun(
            run_id=run_id,
            started_at=datetime.utcnow(),
            status='running'
        )
        db.session.add(review_run)
        db.session.commit()
        
        try:
            files = self.get_python_files()
            all_issues = []
            
            static_issues = self.run_static_analysis()
            all_issues.extend(static_issues)
            
            for file_path in files:
                logger.info(f'Reviewing {file_path}...')
                file_issues = self.analyze_file(file_path)
                all_issues.extend(file_issues)
            
            issues_created = 0
            for issue_data in all_issues:
                existing = CodeQualityIssue.query.filter_by(
                    file_path=issue_data.get('file_path'),
                    title=issue_data.get('title'),
                    status='open'
                ).first()
                
                if existing:
                    continue
                
                issue = CodeQualityIssue(
                    issue_type=issue_data.get('issue_type', 'bug'),
                    severity=issue_data.get('severity', 'medium'),
                    status='open',
                    file_path=issue_data.get('file_path'),
                    line_number=issue_data.get('line_number'),
                    function_name=issue_data.get('function_name'),
                    title=issue_data.get('title', 'Unknown issue'),
                    description=issue_data.get('description'),
                    code_snippet=issue_data.get('code_snippet'),
                    suggested_fix=issue_data.get('suggested_fix'),
                    ai_confidence=issue_data.get('confidence'),
                    auto_fixable=issue_data.get('auto_fixable', False),
                    review_run_id=run_id
                )
                db.session.add(issue)
                issues_created += 1
            
            review_run.completed_at = datetime.utcnow()
            review_run.status = 'completed'
            review_run.files_analyzed = len(files)
            review_run.issues_found = issues_created
            review_run.summary = f'Analyzed {len(files)} files, found {issues_created} new issues'
            
            db.session.commit()
            
            logger.info(f'Code review completed: {review_run.summary}')
            
            return {
                'run_id': run_id,
                'files_analyzed': len(files),
                'issues_found': issues_created,
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f'Code review failed: {e}')
            review_run.status = 'failed'
            review_run.error_message = str(e)
            review_run.completed_at = datetime.utcnow()
            db.session.commit()
            
            return {
                'run_id': run_id,
                'status': 'failed',
                'error': str(e)
            }
    
    def get_open_issues(self, issue_type: str = None, severity: str = None) -> List[Dict]:
        """Get open issues, optionally filtered"""
        from models import CodeQualityIssue
        
        query = CodeQualityIssue.query.filter_by(status='open')
        
        if issue_type:
            query = query.filter_by(issue_type=issue_type)
        if severity:
            query = query.filter_by(severity=severity)
        
        issues = query.order_by(
            CodeQualityIssue.severity.desc(),
            CodeQualityIssue.detected_at.desc()
        ).all()
        
        return [issue.to_dict() for issue in issues]
    
    def update_issue_status(self, issue_id: int, status: str) -> bool:
        """Update issue status"""
        from app import db
        from models import CodeQualityIssue
        
        issue = CodeQualityIssue.query.get(issue_id)
        if not issue:
            return False
        
        issue.status = status
        if status in ['fixed', 'ignored', 'wont_fix']:
            issue.resolved_at = datetime.utcnow()
        
        db.session.commit()
        return True


def run_scheduled_review():
    """Function to be called by scheduler"""
    with app_context():
        guardian = CodeQualityGuardian()
        return guardian.run_review()


def app_context():
    """Get Flask app context for scheduled tasks"""
    from app import app
    return app.app_context()
