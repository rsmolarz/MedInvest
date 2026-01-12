// lib/ai/AIService.ts
/**
 * AI Features for MedInvest
 * - Content moderation
 * - Post summarization
 * - Deal analysis
 * - Smart search
 * - Personalized recommendations
 */

import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

// =============================================================================
// CONTENT MODERATION
// =============================================================================

export interface ModerationResult {
  flagged: boolean;
  categories: {
    harassment: boolean;
    hate: boolean;
    selfHarm: boolean;
    sexual: boolean;
    violence: boolean;
    spam: boolean;
    misinformation: boolean;
  };
  confidence: number;
  action: 'allow' | 'flag' | 'block';
  reason?: string;
}

export async function moderateContent(content: string): Promise<ModerationResult> {
  try {
    // Use OpenAI's moderation endpoint
    const moderation = await openai.moderations.create({
      input: content,
    });
    
    const result = moderation.results[0];
    
    // Custom healthcare-specific checks
    const healthcareCheck = await analyzeHealthcareContent(content);
    
    return {
      flagged: result.flagged || healthcareCheck.flagged,
      categories: {
        harassment: result.categories.harassment,
        hate: result.categories.hate,
        selfHarm: result.categories['self-harm'],
        sexual: result.categories.sexual,
        violence: result.categories.violence,
        spam: healthcareCheck.isSpam,
        misinformation: healthcareCheck.isMisinformation,
      },
      confidence: Math.max(...Object.values(result.category_scores)),
      action: determineAction(result, healthcareCheck),
      reason: healthcareCheck.reason,
    };
  } catch (error) {
    console.error('Moderation error:', error);
    return {
      flagged: false,
      categories: {
        harassment: false,
        hate: false,
        selfHarm: false,
        sexual: false,
        violence: false,
        spam: false,
        misinformation: false,
      },
      confidence: 0,
      action: 'allow',
    };
  }
}

async function analyzeHealthcareContent(content: string) {
  const response = await openai.chat.completions.create({
    model: 'gpt-4-turbo-preview',
    messages: [
      {
        role: 'system',
        content: `You are a healthcare content moderator. Analyze the following content for:
1. Medical misinformation (dangerous health claims, anti-vaccine content, etc.)
2. Spam or promotional content
3. Unverified medical advice that could be harmful

Respond in JSON format:
{
  "flagged": boolean,
  "isSpam": boolean,
  "isMisinformation": boolean,
  "reason": "explanation if flagged"
}`
      },
      {
        role: 'user',
        content,
      },
    ],
    response_format: { type: 'json_object' },
    max_tokens: 200,
  });
  
  return JSON.parse(response.choices[0].message.content || '{}');
}

function determineAction(modResult: any, healthcareCheck: any): 'allow' | 'flag' | 'block' {
  if (modResult.categories.hate || modResult.categories['self-harm'] || healthcareCheck.isMisinformation) {
    return 'block';
  }
  if (modResult.flagged || healthcareCheck.flagged) {
    return 'flag';
  }
  return 'allow';
}

// =============================================================================
// POST SUMMARIZATION
// =============================================================================

export interface PostSummary {
  summary: string;
  keyPoints: string[];
  sentiment: 'positive' | 'negative' | 'neutral';
  topics: string[];
}

export async function summarizePost(content: string): Promise<PostSummary> {
  const response = await openai.chat.completions.create({
    model: 'gpt-4-turbo-preview',
    messages: [
      {
        role: 'system',
        content: `You are a healthcare content analyst. Summarize the following post for a healthcare professional audience.

Respond in JSON format:
{
  "summary": "2-3 sentence summary",
  "keyPoints": ["point 1", "point 2", "point 3"],
  "sentiment": "positive" | "negative" | "neutral",
  "topics": ["topic1", "topic2"]
}`
      },
      {
        role: 'user',
        content,
      },
    ],
    response_format: { type: 'json_object' },
    max_tokens: 500,
  });
  
  return JSON.parse(response.choices[0].message.content || '{}');
}

// =============================================================================
// DEAL ANALYSIS
// =============================================================================

export interface DealAnalysis {
  overview: string;
  strengths: string[];
  risks: string[];
  marketOpportunity: string;
  competitiveLandscape: string;
  investmentThesis: string;
  score: number; // 1-10
}

export async function analyzeDeal(dealInfo: {
  title: string;
  companyName: string;
  description: string;
  sector: string;
  stage: string;
  targetRaise: number;
  valuation?: number;
}): Promise<DealAnalysis> {
  const response = await openai.chat.completions.create({
    model: 'gpt-4-turbo-preview',
    messages: [
      {
        role: 'system',
        content: `You are a healthcare investment analyst. Analyze this investment opportunity for accredited investors interested in healthcare.

Provide analysis in JSON format:
{
  "overview": "Brief overview of the opportunity",
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "risks": ["risk 1", "risk 2", "risk 3"],
  "marketOpportunity": "Analysis of market size and opportunity",
  "competitiveLandscape": "Analysis of competition",
  "investmentThesis": "Summary investment thesis",
  "score": 7 // 1-10 rating
}

Be balanced and objective. Highlight both opportunities and risks.`
      },
      {
        role: 'user',
        content: JSON.stringify(dealInfo),
      },
    ],
    response_format: { type: 'json_object' },
    max_tokens: 1000,
  });
  
  return JSON.parse(response.choices[0].message.content || '{}');
}

// =============================================================================
// SMART SEARCH
// =============================================================================

export interface SmartSearchResult {
  query: string;
  refinedQuery: string;
  suggestedFilters: {
    specialty?: string[];
    dateRange?: { start: string; end: string };
    type?: ('posts' | 'users' | 'deals')[];
  };
  relatedTopics: string[];
}

export async function enhanceSearch(query: string): Promise<SmartSearchResult> {
  const response = await openai.chat.completions.create({
    model: 'gpt-4-turbo-preview',
    messages: [
      {
        role: 'system',
        content: `You are a healthcare search assistant. Enhance the user's search query for a healthcare investment platform.

Respond in JSON format:
{
  "refinedQuery": "improved search query",
  "suggestedFilters": {
    "specialty": ["Cardiology", "Oncology"],
    "type": ["posts", "deals"]
  },
  "relatedTopics": ["related topic 1", "related topic 2"]
}`
      },
      {
        role: 'user',
        content: query,
      },
    ],
    response_format: { type: 'json_object' },
    max_tokens: 300,
  });
  
  const result = JSON.parse(response.choices[0].message.content || '{}');
  return {
    query,
    ...result,
  };
}

// =============================================================================
// PERSONALIZED RECOMMENDATIONS
// =============================================================================

export interface UserPreferences {
  specialties: string[];
  interests: string[];
  investmentPreferences: {
    stages: string[];
    sectors: string[];
    minInvestment?: number;
    maxInvestment?: number;
  };
  engagementHistory: {
    likedTopics: string[];
    viewedDeals: string[];
    followedUsers: string[];
  };
}

export interface Recommendations {
  posts: { postId: number; reason: string; score: number }[];
  deals: { dealId: number; reason: string; score: number }[];
  users: { userId: number; reason: string; score: number }[];
  topics: string[];
}

export async function getRecommendations(
  preferences: UserPreferences,
  availableContent: {
    posts: { id: number; content: string; topics: string[] }[];
    deals: { id: number; title: string; sector: string; stage: string }[];
    users: { id: number; specialty: string; bio: string }[];
  }
): Promise<Recommendations> {
  const response = await openai.chat.completions.create({
    model: 'gpt-4-turbo-preview',
    messages: [
      {
        role: 'system',
        content: `You are a recommendation engine for a healthcare investment platform. 
Based on the user's preferences and available content, provide personalized recommendations.

Respond in JSON format:
{
  "posts": [{"postId": 1, "reason": "why recommended", "score": 0.9}],
  "deals": [{"dealId": 1, "reason": "why recommended", "score": 0.85}],
  "users": [{"userId": 1, "reason": "why recommended", "score": 0.8}],
  "topics": ["suggested topic to explore"]
}

Scores should be 0-1. Only include highly relevant items (score > 0.7).`
      },
      {
        role: 'user',
        content: JSON.stringify({ preferences, availableContent }),
      },
    ],
    response_format: { type: 'json_object' },
    max_tokens: 1000,
  });
  
  return JSON.parse(response.choices[0].message.content || '{}');
}

// =============================================================================
// AI CHAT ASSISTANT
// =============================================================================

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export async function chatWithAssistant(
  messages: ChatMessage[],
  context?: {
    userSpecialty?: string;
    currentPage?: string;
  }
): Promise<string> {
  const systemPrompt = `You are MedInvest AI, a helpful assistant for healthcare professionals and investors on the MedInvest platform.

Your capabilities:
- Answer questions about healthcare investing
- Explain medical and biotech concepts
- Help navigate the platform
- Provide general guidance on investment considerations

Guidelines:
- Be professional and knowledgeable
- Don't provide specific investment advice or medical advice
- Encourage users to consult professionals for specific decisions
- Be concise and helpful

${context?.userSpecialty ? `The user is a ${context.userSpecialty}.` : ''}
${context?.currentPage ? `They are currently on the ${context.currentPage} page.` : ''}`;

  const response = await openai.chat.completions.create({
    model: 'gpt-4-turbo-preview',
    messages: [
      { role: 'system', content: systemPrompt },
      ...messages.map(m => ({ role: m.role as 'user' | 'assistant', content: m.content })),
    ],
    max_tokens: 500,
    temperature: 0.7,
  });
  
  return response.choices[0].message.content || 'I apologize, I could not generate a response.';
}

// =============================================================================
// EMBEDDINGS FOR SEMANTIC SEARCH
// =============================================================================

export async function generateEmbedding(text: string): Promise<number[]> {
  const response = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: text,
  });
  
  return response.data[0].embedding;
}

export async function generateEmbeddings(texts: string[]): Promise<number[][]> {
  const response = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: texts,
  });
  
  return response.data.map(d => d.embedding);
}

// =============================================================================
// EXPORTS
// =============================================================================

export const AIService = {
  moderateContent,
  summarizePost,
  analyzeDeal,
  enhanceSearch,
  getRecommendations,
  chatWithAssistant,
  generateEmbedding,
  generateEmbeddings,
};

export default AIService;
