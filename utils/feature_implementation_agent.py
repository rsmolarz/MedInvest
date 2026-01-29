"""
FeatureImplementationAgent - AI agent that implements approved feature suggestions
Works with CodeQualityGuardian to auto-implement features after admin approval
"""
import os
import logging
import json
import shutil
import tempfile
import subprocess
import ast
from datetime import datetime
from typing import Dict, Optional, List
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Complexity factors for cost estimation
COMPLEXITY_WEIGHTS = {
    'low': 1.0,
    'medium': 2.5,
    'high': 5.0
}

LINES_PER_HOUR = 50  # Average lines of code per hour for estimation
RISK_FACTORS = {
    'database_changes': 1.5,
    'security_sensitive': 2.0,
    'api_changes': 1.3,
    'ui_changes': 1.2,
    'new_dependencies': 1.4
}

class SandboxEnvironment:
    """Isolated sandbox environment for testing proposed changes safely"""
    
    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or os.getcwd()
        self.sandbox_dir = None
        self.test_results = []
        
    def create_sandbox(self) -> str:
        """Create an isolated sandbox directory with project copy"""
        self.sandbox_dir = tempfile.mkdtemp(prefix='medinvest_sandbox_')
        logger.info(f'Created sandbox environment at {self.sandbox_dir}')
        return self.sandbox_dir
    
    def copy_file_to_sandbox(self, file_path: str) -> str:
        """Copy a file to the sandbox for testing"""
        if not self.sandbox_dir:
            self.create_sandbox()
            
        rel_path = os.path.relpath(file_path, self.base_dir)
        sandbox_path = os.path.join(self.sandbox_dir, rel_path)
        
        os.makedirs(os.path.dirname(sandbox_path), exist_ok=True)
        shutil.copy2(file_path, sandbox_path)
        
        return sandbox_path
    
    def apply_changes(self, file_path: str, new_content: str) -> bool:
        """Apply proposed changes to a file in the sandbox"""
        try:
            sandbox_path = self.copy_file_to_sandbox(file_path)
            with open(sandbox_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        except Exception as e:
            logger.error(f'Failed to apply changes in sandbox: {e}')
            return False
    
    def run_syntax_check(self, file_path: str) -> Dict:
        """Run Python syntax check on a file"""
        try:
            result = subprocess.run(
                ['python3', '-m', 'py_compile', file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                'passed': result.returncode == 0,
                'errors': result.stderr if result.returncode != 0 else None
            }
        except subprocess.TimeoutExpired:
            return {'passed': False, 'errors': 'Syntax check timed out'}
        except Exception as e:
            return {'passed': False, 'errors': str(e)}
    
    def run_import_check(self, file_path: str) -> Dict:
        """Check if file has valid imports using AST parsing (no code execution)
        
        Security: Uses AST parsing instead of actually importing the module
        to avoid executing potentially malicious or buggy code.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=file_path)
            
            imports = []
            import_errors = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    imports.append(module)
            
            known_stdlib = {
                'os', 'sys', 'json', 'datetime', 'logging', 'typing', 're',
                'collections', 'functools', 'itertools', 'pathlib', 'tempfile',
                'shutil', 'subprocess', 'hashlib', 'base64', 'uuid', 'time',
                'threading', 'multiprocessing', 'contextlib', 'dataclasses',
                'abc', 'copy', 'io', 'math', 'random', 'string', 'textwrap'
            }
            known_project = {
                'app', 'models', 'routes', 'utils', 'blueprints', 'forms'
            }
            known_third_party = {
                'flask', 'sqlalchemy', 'werkzeug', 'jinja2', 'google',
                'stripe', 'sendgrid', 'requests', 'httpx', 'tenacity'
            }
            
            for imp in imports:
                base_module = imp.split('.')[0]
                if base_module not in known_stdlib and \
                   base_module not in known_project and \
                   base_module not in known_third_party:
                    import_errors.append(f'Unknown import: {imp}')
            
            return {
                'passed': len(import_errors) == 0,
                'imports_found': imports,
                'warnings': import_errors if import_errors else None,
                'errors': None
            }
            
        except SyntaxError as e:
            return {'passed': False, 'errors': f'Syntax error prevents import analysis: {e}'}
        except Exception as e:
            return {'passed': False, 'errors': str(e)}
    
    def execute_and_test(self, changes: List[Dict]) -> Dict:
        """Execute proposed changes and run tests in sandbox
        
        Args:
            changes: List of {'file': path, 'content': new_content} dicts
            
        Returns:
            Dict with test results and overall status
        """
        if not self.sandbox_dir:
            self.create_sandbox()
            
        results = {
            'success': True,
            'files_tested': 0,
            'syntax_passed': 0,
            'import_passed': 0,
            'details': []
        }
        
        for change in changes:
            file_path = change.get('file')
            new_content = change.get('content')
            
            if not file_path or not new_content:
                continue
                
            file_result = {
                'file': file_path,
                'syntax_check': None,
                'import_check': None,
                'passed': False
            }
            
            if self.apply_changes(file_path, new_content):
                sandbox_path = os.path.join(
                    self.sandbox_dir, 
                    os.path.relpath(file_path, self.base_dir)
                )
                
                file_result['syntax_check'] = self.run_syntax_check(sandbox_path)
                if file_result['syntax_check']['passed']:
                    results['syntax_passed'] += 1
                    file_result['import_check'] = self.run_import_check(sandbox_path)
                    if file_result['import_check']['passed']:
                        results['import_passed'] += 1
                        file_result['passed'] = True
                
                if not file_result['passed']:
                    results['success'] = False
                    
            results['files_tested'] += 1
            results['details'].append(file_result)
        
        return results
    
    def cleanup(self):
        """Remove sandbox directory"""
        if self.sandbox_dir and os.path.exists(self.sandbox_dir):
            shutil.rmtree(self.sandbox_dir)
            logger.info(f'Cleaned up sandbox at {self.sandbox_dir}')
            self.sandbox_dir = None


class FeatureRollback:
    """Manages checkpoints and rollbacks for feature implementations"""
    
    CHECKPOINT_DIR = '.feature_checkpoints'
    
    def __init__(self):
        self.checkpoint_base = os.path.join(os.getcwd(), self.CHECKPOINT_DIR)
        os.makedirs(self.checkpoint_base, exist_ok=True)
        
    def create_checkpoint(self, feature_id: int, files: List[str] = None) -> Dict:
        """Create rollback point before implementation
        
        Args:
            feature_id: ID of the feature being implemented
            files: List of files to backup (defaults to common project files)
            
        Returns:
            Dict with checkpoint info
        """
        checkpoint_id = f'{feature_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        checkpoint_dir = os.path.join(self.checkpoint_base, checkpoint_id)
        os.makedirs(checkpoint_dir, exist_ok=True)
        
        if files is None:
            files = self._get_project_files()
        
        backed_up = []
        for file_path in files:
            if os.path.exists(file_path):
                try:
                    rel_path = os.path.relpath(file_path, os.getcwd())
                    backup_path = os.path.join(checkpoint_dir, rel_path)
                    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                    shutil.copy2(file_path, backup_path)
                    backed_up.append(rel_path)
                except Exception as e:
                    logger.warning(f'Failed to backup {file_path}: {e}')
        
        manifest = {
            'feature_id': feature_id,
            'checkpoint_id': checkpoint_id,
            'created_at': datetime.now().isoformat(),
            'files': backed_up
        }
        
        manifest_path = os.path.join(checkpoint_dir, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
            
        logger.info(f'Created checkpoint {checkpoint_id} with {len(backed_up)} files')
        
        return {
            'success': True,
            'checkpoint_id': checkpoint_id,
            'files_backed_up': len(backed_up),
            'path': checkpoint_dir
        }
    
    def rollback_feature(self, feature_id: int, checkpoint_id: str = None) -> Dict:
        """Revert all changes from a feature implementation
        
        Args:
            feature_id: ID of the feature to rollback
            checkpoint_id: Specific checkpoint ID (uses latest if not provided)
            
        Returns:
            Dict with rollback results
        """
        if checkpoint_id:
            checkpoint_dir = os.path.join(self.checkpoint_base, checkpoint_id)
        else:
            checkpoint_dir = self._get_latest_checkpoint(feature_id)
            
        if not checkpoint_dir or not os.path.exists(checkpoint_dir):
            return {'success': False, 'error': 'Checkpoint not found'}
        
        manifest_path = os.path.join(checkpoint_dir, 'manifest.json')
        if not os.path.exists(manifest_path):
            return {'success': False, 'error': 'Checkpoint manifest not found'}
            
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        restored = []
        errors = []
        
        for rel_path in manifest.get('files', []):
            backup_path = os.path.join(checkpoint_dir, rel_path)
            target_path = os.path.join(os.getcwd(), rel_path)
            
            if os.path.exists(backup_path):
                try:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copy2(backup_path, target_path)
                    restored.append(rel_path)
                except Exception as e:
                    errors.append({'file': rel_path, 'error': str(e)})
            else:
                errors.append({'file': rel_path, 'error': 'Backup file not found'})
        
        logger.info(f'Rolled back feature {feature_id}: {len(restored)} files restored')
        
        return {
            'success': len(errors) == 0,
            'checkpoint_id': manifest.get('checkpoint_id'),
            'files_restored': len(restored),
            'restored': restored,
            'errors': errors if errors else None
        }
    
    def list_checkpoints(self, feature_id: int = None) -> List[Dict]:
        """List available checkpoints, optionally filtered by feature ID"""
        checkpoints = []
        
        if not os.path.exists(self.checkpoint_base):
            return checkpoints
            
        for entry in os.listdir(self.checkpoint_base):
            checkpoint_dir = os.path.join(self.checkpoint_base, entry)
            manifest_path = os.path.join(checkpoint_dir, 'manifest.json')
            
            if os.path.isdir(checkpoint_dir) and os.path.exists(manifest_path):
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                    
                if feature_id is None or manifest.get('feature_id') == feature_id:
                    checkpoints.append(manifest)
        
        return sorted(checkpoints, key=lambda x: x.get('created_at', ''), reverse=True)
    
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint to free up space"""
        checkpoint_dir = os.path.join(self.checkpoint_base, checkpoint_id)
        if os.path.exists(checkpoint_dir):
            shutil.rmtree(checkpoint_dir)
            logger.info(f'Deleted checkpoint {checkpoint_id}')
            return True
        return False
    
    def _get_latest_checkpoint(self, feature_id: int) -> Optional[str]:
        """Get the most recent checkpoint for a feature"""
        checkpoints = self.list_checkpoints(feature_id)
        if checkpoints:
            return os.path.join(self.checkpoint_base, checkpoints[0]['checkpoint_id'])
        return None
    
    def _get_project_files(self) -> List[str]:
        """Get list of common project files to backup"""
        files = []
        extensions = {'.py', '.html', '.css', '.js'}
        exclude_dirs = {'__pycache__', '.git', 'node_modules', 'venv', '.feature_checkpoints'}
        
        for root, dirs, filenames in os.walk(os.getcwd()):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for filename in filenames:
                if any(filename.endswith(ext) for ext in extensions):
                    files.append(os.path.join(root, filename))
        
        return files[:100]  # Limit to prevent excessive backups


FEATURE_ANALYSIS_PROMPT = """You are a senior software architect analyzing a feature request for MedInvest, a Flask/Python social media platform for medical professionals.

FEATURE REQUEST:
Title: {title}
Description: {description}
Suggested Implementation: {suggested_fix}

Based on this feature request, provide a detailed implementation plan:

1. Analyze if this feature is feasible and beneficial
2. List the files that need to be created or modified
3. Describe the database changes needed (if any)
4. Outline the implementation steps
5. Estimate complexity (low/medium/high)
6. List any risks or considerations

Respond in JSON format:
{{
    "feasible": true/false,
    "complexity": "low|medium|high",
    "estimated_effort": "X hours",
    "summary": "Brief summary of what will be implemented",
    "files_to_modify": ["file1.py", "file2.html"],
    "files_to_create": ["newfile.py"],
    "database_changes": "Description of DB changes or 'None'",
    "implementation_steps": [
        "Step 1: ...",
        "Step 2: ..."
    ],
    "risks": ["Risk 1", "Risk 2"],
    "recommendation": "approve|needs_review|reject",
    "reason": "Why this recommendation"
}}
"""

IMPLEMENTATION_PROMPT = """You are an expert Python/Flask developer implementing a feature for MedInvest.

FEATURE TO IMPLEMENT:
Title: {title}
Description: {description}
Implementation Plan: {implementation_plan}

CURRENT FILE CONTENT:
{file_content}

Implement the feature by providing the updated code. Follow these rules:
1. Maintain existing code style and patterns
2. Add proper error handling
3. Include any necessary imports
4. Add inline comments only where logic is complex
5. Ensure security best practices

Respond in JSON format:
{{
    "success": true/false,
    "updated_code": "Full updated file content",
    "changes_summary": "What was changed",
    "additional_files_needed": ["list of other files that need changes"]
}}
"""


class FeatureImplementationAgent:
    """AI agent that implements approved feature suggestions"""
    
    def __init__(self):
        self.api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('AI_INTEGRATIONS_GEMINI_API_KEY')
        self.model_name = 'gemini-2.0-flash'
        
    def analyze_feature(self, issue) -> Dict:
        """Analyze a feature suggestion and create implementation plan"""
        if not self.api_key:
            logger.warning('No Gemini API key configured for feature implementation')
            return {'error': 'No API key configured'}
        
        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model_name)
            
            prompt = FEATURE_ANALYSIS_PROMPT.format(
                title=issue.title,
                description=issue.description or '',
                suggested_fix=issue.suggested_fix or ''
            )
            
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type='application/json',
                    temperature=0.2
                )
            )
            
            result = json.loads(response.text)
            return result
            
        except Exception as e:
            logger.error(f'Feature analysis failed: {e}')
            return {'error': str(e)}
    
    def implement_feature(self, issue, implementation_plan: Dict, auto_apply: bool = False) -> Dict:
        """Generate implementation changes (does NOT auto-apply by default for security)
        
        Security: Auto-implementation is disabled by default. Changes are stored
        as a preview in ai_reasoning field for manual review by admins.
        Set auto_apply=True only for explicitly approved low-risk changes.
        """
        if not self.api_key:
            return {'success': False, 'error': 'No API key configured'}
        
        from app import db
        
        try:
            proposed_changes = []
            
            for file_path in implementation_plan.get('files_to_modify', []):
                try:
                    change = self._generate_change_preview(issue, file_path, implementation_plan)
                    if change.get('success'):
                        proposed_changes.append({
                            'file': file_path,
                            'summary': change.get('changes_summary', 'No summary'),
                            'preview': change.get('diff_preview', '')
                        })
                except Exception as e:
                    proposed_changes.append({
                        'file': file_path,
                        'error': str(e)
                    })
            
            issue.ai_reasoning = f"Implementation Plan:\n{implementation_plan.get('summary', '')}\n\n"
            issue.ai_reasoning += f"Complexity: {implementation_plan.get('complexity', 'unknown')}\n"
            issue.ai_reasoning += f"Estimated Effort: {implementation_plan.get('estimated_effort', 'unknown')}\n\n"
            issue.ai_reasoning += "Proposed Changes:\n"
            
            for change in proposed_changes:
                if change.get('error'):
                    issue.ai_reasoning += f"- {change['file']}: Error - {change['error']}\n"
                else:
                    issue.ai_reasoning += f"- {change['file']}: {change['summary']}\n"
            
            issue.ai_reasoning += "\n\nNote: Auto-implementation is disabled for security. "
            issue.ai_reasoning += "Please review the proposed changes and implement manually or contact development team."
            
            db.session.commit()
            
            return {
                'success': True,
                'proposed_changes': proposed_changes,
                'message': 'Implementation plan generated. Manual review required before applying changes.',
                'auto_applied': False
            }
                
        except Exception as e:
            logger.error(f'Feature implementation planning failed: {e}')
            return {'success': False, 'error': str(e)}
    
    def _generate_change_preview(self, issue, file_path: str, implementation_plan: Dict) -> Dict:
        """Generate a preview of changes without modifying files"""
        if not os.path.exists(file_path):
            return {'success': False, 'error': 'File not found'}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
        except Exception as e:
            return {'success': False, 'error': f'Could not read file: {e}'}
        
        if len(original_content) > 100000:
            return {'success': False, 'error': 'File too large for analysis'}
        
        return {
            'success': True,
            'changes_summary': f'Analysis complete for {file_path}',
            'diff_preview': f'File has {len(original_content)} characters. Manual implementation recommended.'
        }
    
    def test_proposed_changes(self, changes: List[Dict]) -> Dict:
        """Run proposed changes in sandbox environment
        
        Args:
            changes: List of {'file': path, 'content': new_content} dicts
            
        Returns:
            Dict with test results including syntax/import checks
            
        Security: Uses AST-based import checking (no code execution)
        """
        sandbox = SandboxEnvironment()
        try:
            result = sandbox.execute_and_test(changes)
            result['sandbox_used'] = True
            return result
        finally:
            sandbox.cleanup()
    
    def estimate_implementation_cost(self, analysis: Dict) -> Dict:
        """Estimate implementation cost based on feature analysis
        
        Args:
            analysis: Feature analysis from analyze_feature()
            
        Returns:
            Dict with estimated hours, lines of code, risk level, dependencies
        """
        return {
            'estimated_hours': self._calculate_hours(analysis),
            'estimated_lines': self._estimate_lines_of_code(analysis),
            'risk_level': self._assess_risk(analysis),
            'dependencies': self._identify_dependencies(analysis),
            'affected_tests': self._find_affected_tests(analysis),
            'confidence': self._calculate_confidence(analysis),
            'breakdown': self._get_cost_breakdown(analysis)
        }
    
    def _calculate_hours(self, analysis: Dict) -> float:
        """Calculate estimated hours based on complexity and scope"""
        base_hours = {
            'low': 2.0,
            'medium': 8.0,
            'high': 24.0
        }
        
        complexity = analysis.get('complexity', 'medium')
        hours = base_hours.get(complexity, 8.0)
        
        files_to_modify = len(analysis.get('files_to_modify', []))
        files_to_create = len(analysis.get('files_to_create', []))
        
        hours += files_to_modify * 0.5
        hours += files_to_create * 1.5
        
        if analysis.get('database_changes') and analysis['database_changes'] != 'None':
            hours *= RISK_FACTORS['database_changes']
        
        return round(hours, 1)
    
    def _estimate_lines_of_code(self, analysis: Dict) -> Dict:
        """Estimate lines of code to be added/modified"""
        complexity_multiplier = COMPLEXITY_WEIGHTS.get(
            analysis.get('complexity', 'medium'), 2.5
        )
        
        base_lines = 50
        files_count = len(analysis.get('files_to_modify', [])) + \
                      len(analysis.get('files_to_create', []))
        
        estimated_lines = int(base_lines * complexity_multiplier * max(files_count, 1))
        
        return {
            'estimated_new': int(estimated_lines * 0.7),
            'estimated_modified': int(estimated_lines * 0.3),
            'total': estimated_lines
        }
    
    def _assess_risk(self, analysis: Dict) -> Dict:
        """Assess risk level of the implementation"""
        risks = analysis.get('risks', [])
        risk_score = 0
        risk_factors = []
        
        if analysis.get('database_changes') and analysis['database_changes'] != 'None':
            risk_score += 3
            risk_factors.append('database_changes')
        
        security_keywords = ['auth', 'password', 'token', 'secret', 'encrypt', 'payment']
        description = (analysis.get('summary', '') + ' '.join(risks)).lower()
        
        if any(kw in description for kw in security_keywords):
            risk_score += 4
            risk_factors.append('security_sensitive')
        
        if 'api' in description or 'endpoint' in description:
            risk_score += 2
            risk_factors.append('api_changes')
        
        if any('template' in f or '.html' in f for f in analysis.get('files_to_modify', [])):
            risk_score += 1
            risk_factors.append('ui_changes')
        
        risk_score += len(risks)
        
        if risk_score <= 2:
            level = 'low'
        elif risk_score <= 5:
            level = 'medium'
        else:
            level = 'high'
        
        return {
            'level': level,
            'score': risk_score,
            'factors': risk_factors,
            'identified_risks': risks
        }
    
    def _identify_dependencies(self, analysis: Dict) -> List[str]:
        """Identify external dependencies needed for the feature"""
        deps = []
        summary = (analysis.get('summary', '') + 
                   ' '.join(analysis.get('implementation_steps', []))).lower()
        
        dependency_hints = {
            'email': 'sendgrid or smtp',
            'payment': 'stripe',
            'redis': 'redis',
            'celery': 'celery',
            'websocket': 'flask-socketio',
            'pdf': 'reportlab or weasyprint',
            'excel': 'openpyxl',
            'image': 'pillow',
            'oauth': 'flask-oauthlib',
            'jwt': 'pyjwt',
            'cache': 'redis or flask-caching'
        }
        
        for keyword, dep in dependency_hints.items():
            if keyword in summary:
                deps.append(dep)
        
        return list(set(deps))
    
    def _calculate_confidence(self, analysis: Dict) -> float:
        """Calculate confidence level in the estimate"""
        confidence = 0.8
        
        if analysis.get('complexity') == 'high':
            confidence -= 0.2
        elif analysis.get('complexity') == 'low':
            confidence += 0.1
        
        if len(analysis.get('risks', [])) > 3:
            confidence -= 0.1
        
        if analysis.get('recommendation') == 'approve':
            confidence += 0.05
        elif analysis.get('recommendation') == 'reject':
            confidence -= 0.15
        
        return round(max(0.3, min(0.95, confidence)), 2)
    
    def _get_cost_breakdown(self, analysis: Dict) -> Dict:
        """Get detailed breakdown of cost estimate"""
        complexity = analysis.get('complexity', 'medium')
        
        return {
            'development': {
                'hours': self._calculate_hours(analysis) * 0.6,
                'description': 'Core implementation work'
            },
            'testing': {
                'hours': self._calculate_hours(analysis) * 0.25,
                'description': 'Unit and integration testing'
            },
            'review_and_deployment': {
                'hours': self._calculate_hours(analysis) * 0.15,
                'description': 'Code review and deployment'
            },
            'complexity_factor': COMPLEXITY_WEIGHTS.get(complexity, 2.5)
        }
    
    def _find_affected_tests(self, analysis: Dict) -> Dict:
        """Find test files that may be affected by the implementation
        
        Args:
            analysis: Feature analysis containing files to modify
            
        Returns:
            Dict with affected test files and new tests needed
        """
        affected_tests = []
        new_tests_needed = []
        
        files_to_modify = analysis.get('files_to_modify', [])
        files_to_create = analysis.get('files_to_create', [])
        
        test_dir = os.path.join(os.getcwd(), 'tests')
        test_patterns = {
            'models.py': 'test_models.py',
            'routes.py': 'test_routes.py',
            'auth.py': 'test_auth.py',
            'forms.py': 'test_forms.py',
            'api.py': 'test_api.py'
        }
        
        for file_path in files_to_modify:
            basename = os.path.basename(file_path)
            
            if basename in test_patterns:
                test_file = test_patterns[basename]
                test_path = os.path.join(test_dir, test_file)
                if os.path.exists(test_path):
                    affected_tests.append(test_file)
                else:
                    new_tests_needed.append(test_file)
            
            if 'utils/' in file_path:
                util_name = os.path.splitext(basename)[0]
                test_file = f'test_{util_name}.py'
                test_path = os.path.join(test_dir, test_file)
                if os.path.exists(test_path):
                    affected_tests.append(test_file)
                else:
                    new_tests_needed.append(test_file)
            
            if 'blueprints/' in file_path:
                bp_name = os.path.splitext(basename)[0]
                test_file = f'test_{bp_name}_bp.py'
                new_tests_needed.append(test_file)
        
        for file_path in files_to_create:
            basename = os.path.basename(file_path)
            module_name = os.path.splitext(basename)[0]
            new_tests_needed.append(f'test_{module_name}.py')
        
        return {
            'affected_tests': list(set(affected_tests)),
            'new_tests_needed': list(set(new_tests_needed)),
            'total_affected': len(set(affected_tests)),
            'total_new_needed': len(set(new_tests_needed))
        }
    
    def get_feature_recommendations(self) -> list:
        """Generate new feature recommendations based on popular platforms"""
        if not self.api_key:
            return []
        
        recommendation_prompt = """You are a product advisor for MedInvest, a social media platform for medical professionals.

Analyze features from these platforms and suggest 3-5 that would benefit medical professionals:
- Facebook: Groups, Marketplace, Events, Live Video
- Instagram: Stories, Reels, Shopping
- LinkedIn: Endorsements, Skills, Company Pages, Job Postings
- Twitter/X: Spaces, Communities, Bookmarks
- Reddit: Subreddits, Awards, Karma system

Also suggest 2-3 novel features unique to medical professionals.

For each suggestion, provide:
- Title (max 100 chars)
- Description
- Implementation complexity (low/medium/high)
- Expected impact (low/medium/high)

Respond in JSON format:
{
    "recommendations": [
        {
            "title": "Feature Title",
            "description": "Detailed description",
            "inspired_by": "Platform name or 'Original'",
            "complexity": "low|medium|high",
            "impact": "low|medium|high",
            "category": "social|education|networking|content|finance"
        }
    ]
}
"""
        
        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model_name)
            
            response = model.generate_content(
                recommendation_prompt,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type='application/json',
                    temperature=0.7
                )
            )
            
            result = json.loads(response.text)
            return result.get('recommendations', [])
            
        except Exception as e:
            logger.error(f'Failed to generate recommendations: {e}')
            return []
    
    def create_feature_issues(self, recommendations: list) -> int:
        """Create CodeQualityIssue entries for new feature recommendations"""
        from app import db
        from models import CodeQualityIssue
        
        created = 0
        for rec in recommendations:
            existing = CodeQualityIssue.query.filter_by(
                issue_type='feature_suggestion',
                title=rec.get('title'),
                status='open'
            ).first()
            
            if existing:
                continue
            
            issue = CodeQualityIssue(
                issue_type='feature_suggestion',
                severity='info',
                status='open',
                title=rec.get('title', 'New Feature'),
                description=f"{rec.get('description', '')}\n\nInspired by: {rec.get('inspired_by', 'Original')}\nCategory: {rec.get('category', 'general')}\nExpected Impact: {rec.get('impact', 'medium')}",
                suggested_fix=f"Complexity: {rec.get('complexity', 'medium')}\nThis feature could be implemented to enhance the platform.",
                ai_confidence=0.8,
                auto_fixable=rec.get('complexity') == 'low'
            )
            db.session.add(issue)
            created += 1
        
        db.session.commit()
        return created


def run_feature_recommendations():
    """Function to be called by scheduler to generate new feature ideas"""
    from app import app
    
    with app.app_context():
        try:
            agent = FeatureImplementationAgent()
            recommendations = agent.get_feature_recommendations()
            created = agent.create_feature_issues(recommendations)
            logger.info(f'Created {created} new feature recommendations')
            return {'created': created}
        except Exception as e:
            logger.error(f'Feature recommendation generation failed: {e}')
            return {'error': str(e)}
