"""
CodeQualityGuardian - Automated code review and quality analysis
Runs hourly to detect issues, suggest fixes, and recommend features

Features:
- Retry logic with exponential backoff for API resilience
- Parallel file processing for faster reviews
- File hash caching to skip unchanged files
- Enhanced metrics and performance tracking
"""
import os
import re
import uuid
import json
import hashlib
import logging
import subprocess
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
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

# Default configuration constants
DEFAULT_MAX_WORKERS = 3
DEFAULT_CACHE_FILE = '.code_quality_cache.json'
DEFAULT_MAX_FILE_SIZE = 50000
DEFAULT_MIN_FILE_SIZE = 50
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_MIN_WAIT = 2
DEFAULT_RETRY_MAX_WAIT = 10


class GuardianConfig:
    """Configuration management for CodeQualityGuardian via environment variables"""
    
    def __init__(self):
        # API Configuration
        self.api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('AI_INTEGRATIONS_GEMINI_API_KEY')
        self.model_name = os.environ.get('GUARDIAN_MODEL', 'gemini-2.0-flash')
        
        # Processing Configuration
        self.max_workers = int(os.environ.get('GUARDIAN_MAX_WORKERS', DEFAULT_MAX_WORKERS))
        self.cache_file = os.environ.get('GUARDIAN_CACHE_FILE', DEFAULT_CACHE_FILE)
        self.max_file_size = int(os.environ.get('GUARDIAN_MAX_FILE_SIZE', DEFAULT_MAX_FILE_SIZE))
        self.min_file_size = int(os.environ.get('GUARDIAN_MIN_FILE_SIZE', DEFAULT_MIN_FILE_SIZE))
        
        # Retry Configuration
        self.retry_attempts = int(os.environ.get('GUARDIAN_RETRY_ATTEMPTS', DEFAULT_RETRY_ATTEMPTS))
        self.retry_min_wait = int(os.environ.get('GUARDIAN_RETRY_MIN_WAIT', DEFAULT_RETRY_MIN_WAIT))
        self.retry_max_wait = int(os.environ.get('GUARDIAN_RETRY_MAX_WAIT', DEFAULT_RETRY_MAX_WAIT))
        
        # Feature Flags
        self.enable_caching = os.environ.get('GUARDIAN_ENABLE_CACHING', 'true').lower() == 'true'
        self.enable_parallel = os.environ.get('GUARDIAN_ENABLE_PARALLEL', 'true').lower() == 'true'
        self.verbose_logging = os.environ.get('GUARDIAN_VERBOSE', 'false').lower() == 'true'
        
        # Review Scope
        self.files_to_review = self._parse_list_env(
            'GUARDIAN_FILES_TO_REVIEW',
            ['routes/*.py', 'utils/*.py', 'models.py', 'app.py', 'main.py',
             'templates/*.html', 'templates/**/*.html', 'static/css/*.css', 'static/js/*.js']
        )
        self.exclude_patterns = self._parse_list_env(
            'GUARDIAN_EXCLUDE_PATTERNS',
            ['__pycache__', '.pyc', 'migrations/', 'test_', '_test.py', 'attached_assets/']
        )
    
    def _parse_list_env(self, key: str, default: List[str]) -> List[str]:
        """Parse comma-separated environment variable into list"""
        value = os.environ.get(key)
        if value:
            return [item.strip() for item in value.split(',') if item.strip()]
        return default
    
    def to_dict(self) -> Dict:
        """Return configuration as dictionary"""
        return {
            'model_name': self.model_name,
            'max_workers': self.max_workers,
            'cache_file': self.cache_file,
            'max_file_size': self.max_file_size,
            'min_file_size': self.min_file_size,
            'retry_attempts': self.retry_attempts,
            'retry_min_wait': self.retry_min_wait,
            'retry_max_wait': self.retry_max_wait,
            'enable_caching': self.enable_caching,
            'enable_parallel': self.enable_parallel,
            'verbose_logging': self.verbose_logging,
            'files_to_review': self.files_to_review,
            'exclude_patterns': self.exclude_patterns,
            'has_api_key': bool(self.api_key)
        }
    
    def get_retry_config(self) -> Dict:
        """Get tenacity retry configuration based on settings"""
        return {
            'stop': stop_after_attempt(self.retry_attempts),
            'wait': wait_exponential(multiplier=1, min=self.retry_min_wait, max=self.retry_max_wait),
            'retry': retry_if_exception_type((ResourceExhausted, ServiceUnavailable, ConnectionError, TimeoutError)),
            'before_sleep': before_sleep_log(logger, logging.WARNING),
            'reraise': True
        }


# Global config instance
guardian_config = GuardianConfig()

# Backward compatible RETRY_CONFIG using global config
RETRY_CONFIG = guardian_config.get_retry_config()
MAX_WORKERS = guardian_config.max_workers
CACHE_FILE = guardian_config.cache_file

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
    """Main code quality review engine with parallel processing and caching"""
    
    def __init__(self, config: GuardianConfig = None):
        """Initialize Guardian with optional custom config
        
        Args:
            config: Optional GuardianConfig instance. Uses global guardian_config if not provided.
        """
        self.config = config or guardian_config
        self.api_key = self.config.api_key
        self.model_name = self.config.model_name
        self.files_to_review = self.config.files_to_review
        self.exclude_patterns = self.config.exclude_patterns
        self._file_cache = self._load_cache() if self.config.enable_caching else {}
        self._metrics = {
            'files_analyzed': 0,
            'files_skipped_cache': 0,
            'api_calls': 0,
            'api_errors': 0,
            'total_time_seconds': 0
        }
        
        if self.config.verbose_logging:
            logger.setLevel(logging.DEBUG)
    
    def get_config(self) -> Dict:
        """Get current configuration"""
        return self.config.to_dict()
    
    def _load_cache(self) -> Dict:
        """Load file hash cache from disk"""
        try:
            cache_file = self.config.cache_file
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.debug(f'Cache load failed: {e}')
        return {}
    
    def _save_cache(self):
        """Save file hash cache to disk"""
        if not self.config.enable_caching:
            return
        try:
            with open(self.config.cache_file, 'w') as f:
                json.dump(self._file_cache, f)
        except Exception as e:
            logger.debug(f'Cache save failed: {e}')
    
    def _get_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of file contents"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ''
    
    def _is_file_changed(self, file_path: str) -> bool:
        """Check if file has changed since last review"""
        current_hash = self._get_file_hash(file_path)
        cached_hash = self._file_cache.get(file_path, {}).get('hash', '')
        return current_hash != cached_hash
    
    def _update_file_cache(self, file_path: str, issues_count: int):
        """Update cache with file hash and review timestamp"""
        self._file_cache[file_path] = {
            'hash': self._get_file_hash(file_path),
            'reviewed_at': datetime.utcnow().isoformat(),
            'issues_count': issues_count
        }
    
    def get_metrics(self) -> Dict:
        """Get review metrics"""
        return self._metrics.copy()
        
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
        
        if len(code_content) > self.config.max_file_size:
            logger.info(f'Skipping {file_path} - too large for review ({len(code_content)} > {self.config.max_file_size})')
            return []
        
        if len(code_content.strip()) < self.config.min_file_size:
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
    
    def _analyze_file_with_cache(self, file_path: str, force: bool = False) -> Tuple[str, List[Dict]]:
        """Analyze a file, using cache to skip unchanged files"""
        # Check cache only if caching is enabled and not forcing
        if self.config.enable_caching and not force and not self._is_file_changed(file_path):
            self._metrics['files_skipped_cache'] += 1
            if self.config.verbose_logging:
                logger.debug(f'Skipping {file_path} - unchanged since last review')
            return file_path, []
        
        self._metrics['files_analyzed'] += 1
        self._metrics['api_calls'] += 1
        issues = self.analyze_file(file_path)
        
        if self.config.enable_caching:
            self._update_file_cache(file_path, len(issues))
        return file_path, issues
    
    def run_review(self, force_all: bool = False, max_workers: int = None) -> Dict:
        """Run a complete code review with parallel processing
        
        Args:
            force_all: If True, review all files regardless of cache
            max_workers: Number of parallel workers (uses config value if not specified)
        """
        # Use config defaults if not specified
        if max_workers is None:
            max_workers = self.config.max_workers if self.config.enable_parallel else 1
        from app import db
        from models import CodeQualityIssue, CodeReviewRun
        
        start_time = time.time()
        run_id = str(uuid.uuid4())[:8]
        
        # Reset metrics
        self._metrics = {
            'files_analyzed': 0,
            'files_skipped_cache': 0,
            'api_calls': 0,
            'api_errors': 0,
            'total_time_seconds': 0
        }
        
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
            
            # Run static analysis first
            static_issues = self.run_static_analysis()
            all_issues.extend(static_issues)
            
            # Parallel file analysis with ThreadPoolExecutor
            logger.info(f'Analyzing {len(files)} files with {max_workers} workers...')
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self._analyze_file_with_cache, f, force_all): f 
                    for f in files
                }
                
                for future in as_completed(futures):
                    file_path = futures[future]
                    try:
                        _, file_issues = future.result()
                        if file_issues:
                            all_issues.extend(file_issues)
                            logger.info(f'Found {len(file_issues)} issues in {file_path}')
                    except Exception as e:
                        self._metrics['api_errors'] += 1
                        logger.error(f'Failed to analyze {file_path}: {e}')
            
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
            
            # Save cache and calculate metrics
            self._save_cache()
            elapsed_time = time.time() - start_time
            self._metrics['total_time_seconds'] = round(elapsed_time, 2)
            
            review_run.completed_at = datetime.utcnow()
            review_run.status = 'completed'
            review_run.files_analyzed = self._metrics['files_analyzed']
            review_run.issues_found = issues_created
            review_run.summary = (
                f"Analyzed {self._metrics['files_analyzed']} files "
                f"(skipped {self._metrics['files_skipped_cache']} cached), "
                f"found {issues_created} new issues in {elapsed_time:.1f}s"
            )
            
            db.session.commit()
            
            logger.info(f'Code review completed: {review_run.summary}')
            
            return {
                'run_id': run_id,
                'files_analyzed': self._metrics['files_analyzed'],
                'files_skipped_cache': self._metrics['files_skipped_cache'],
                'issues_found': issues_created,
                'api_errors': self._metrics['api_errors'],
                'total_time_seconds': self._metrics['total_time_seconds'],
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f'Code review failed: {e}')
            review_run.status = 'failed'
            review_run.error_message = str(e)
            review_run.completed_at = datetime.utcnow()
            db.session.commit()
            self._save_cache()  # Save cache even on failure
            
            return {
                'run_id': run_id,
                'status': 'failed',
                'error': str(e),
                'metrics': self._metrics
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
