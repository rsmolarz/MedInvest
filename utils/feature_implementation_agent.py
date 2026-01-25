"""
FeatureImplementationAgent - AI agent that implements approved feature suggestions
Works with CodeQualityGuardian to auto-implement features after admin approval
"""
import os
import logging
import json
from datetime import datetime
from typing import Dict, Optional
import google.generativeai as genai

logger = logging.getLogger(__name__)

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
