"""
AI Routes - AI-powered financial assistant
"""
import os
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app import db

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')


@ai_bp.route('/')
@login_required
def chat():
    """AI chat interface"""
    return render_template('ai/chat.html')


@ai_bp.route('/ask', methods=['POST'])
@login_required
def ask_ai():
    """Process AI question"""
    data = request.get_json()
    question = data.get('question', '').strip()
    
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    
    # Check for Anthropic API key
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
    
    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            
            system_prompt = """You are MedInvest AI, a knowledgeable financial assistant specifically designed for physicians. 

Your expertise includes:
- Tax strategies for high-income earners (backdoor Roth, mega backdoor Roth, tax-loss harvesting)
- Investment strategies (index funds, real estate, alternative investments)
- Student loan management (PSLF, refinancing, repayment strategies)
- Retirement planning (401k, 403b, defined benefit plans)
- Insurance (disability, malpractice, life insurance)
- Practice ownership and transitions
- Physician-specific financial challenges

Guidelines:
1. Provide helpful, educational information
2. Always clarify you're an AI assistant, not a financial advisor
3. Recommend consulting qualified professionals for personalized advice
4. Be concise but thorough
5. Use physician-relevant examples when possible"""

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": question}
                ]
            )
            
            response_text = message.content[0].text
            
        except Exception as e:
            response_text = f"I apologize, but I'm having trouble connecting to the AI service. Error: {str(e)}"
    
    else:
        # Fallback responses without API key
        response_text = get_fallback_response(question)
    
    # Award points for using AI
    current_user.add_points(2)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'response': response_text
    })


def get_fallback_response(question):
    """Provide helpful responses without API key"""
    question_lower = question.lower()
    
    responses = {
        'backdoor roth': """**Backdoor Roth IRA Strategy**

A Backdoor Roth IRA lets high-income earners contribute to a Roth IRA despite income limits:

1. **Contribute to Traditional IRA** - Make a non-deductible contribution ($7,000 for 2024)
2. **Convert to Roth** - Convert the Traditional IRA to Roth IRA
3. **Pay taxes on gains** - Only taxable if there were gains between contribution and conversion

**Important considerations:**
- Pro-rata rule applies if you have existing Traditional IRA balances
- Keep documentation of non-deductible contributions (Form 8606)
- Some physicians use their 401(k) rollover to avoid pro-rata issues

*Note: Consult a tax professional for your specific situation.*""",

        'pslf': """**Public Service Loan Forgiveness (PSLF)**

PSLF forgives federal student loans after 120 qualifying payments while working for a qualifying employer.

**Key requirements:**
- Work full-time for qualifying employer (501(c)(3) nonprofits, government)
- Make 120 qualifying payments under income-driven repayment
- Have Direct Loans (consolidate if needed)

**For physicians:**
- Academic medical centers often qualify
- Training years count if at qualifying employer
- Submit Employment Certification Form annually

**Tips:**
- Use PSLF Help Tool on StudentAid.gov
- Income-driven plans (PAYE, REPAYE, IBR) work best
- Track everything meticulously

*Consider consulting a student loan specialist.*""",

        'index fund': """**Index Fund Investing for Physicians**

Index funds are a cornerstone of wealth building for busy physicians:

**Benefits:**
- Low fees (expense ratios often < 0.10%)
- Instant diversification
- No stock picking required
- Tax efficient

**Popular approach - Three Fund Portfolio:**
1. US Total Stock Market (e.g., VTSAX, VTI)
2. International Stock (e.g., VTIAX, VXUS)
3. US Bond Market (e.g., VBTLX, BND)

**Typical physician allocation:**
- Younger physicians: 80-90% stocks, 10-20% bonds
- Mid-career: 70-80% stocks, 20-30% bonds
- Near retirement: 50-60% stocks, 40-50% bonds

*Asset allocation should match your risk tolerance and timeline.*""",

        'real estate': """**Real Estate Investing for Physicians**

Real estate offers diversification and passive income potential:

**Options for busy physicians:**

1. **REITs** - Real Estate Investment Trusts
   - Liquid, low minimum
   - Dividend income
   - Public (traded) or private

2. **Syndications**
   - Passive investment in larger deals
   - Typically $50-100k minimum
   - Tax benefits (depreciation)

3. **Direct ownership**
   - More control, more work
   - Consider property management
   - 1031 exchanges for tax deferral

4. **Crowdfunding platforms**
   - Lower minimums
   - Variety of projects
   - Due diligence important

*Real estate requires research - understand the risks before investing.*""",

        'disability insurance': """**Disability Insurance for Physicians**

Disability insurance is arguably the most important insurance for physicians:

**Key features to look for:**
- **Own-occupation** definition (can't work in YOUR specialty)
- **Specialty-specific** coverage
- **Non-cancelable** and **guaranteed renewable**
- **Residual/partial** disability rider
- **Future increase** option rider
- **COLA** (Cost of Living Adjustment) rider

**Coverage amount:**
- Typically 60-70% of gross income
- Maximum usually $15,000-25,000/month

**When to buy:**
- During training (lower rates, easier qualification)
- Before any health issues arise

*Work with an independent insurance broker who specializes in physicians.*"""
    }
    
    # Check for keyword matches
    for keyword, response in responses.items():
        if keyword in question_lower:
            return response
    
    # Default response
    return """I'm MedInvest AI, your financial assistant for physicians.

I can help with topics like:
- **Backdoor Roth IRA** - Tax-advantaged retirement strategy
- **PSLF** - Public Service Loan Forgiveness
- **Index Fund Investing** - Building wealth simply
- **Real Estate** - Investment options for physicians
- **Disability Insurance** - Protecting your income

Try asking about any of these topics!

*For full AI capabilities, add your ANTHROPIC_API_KEY to the environment.*"""
