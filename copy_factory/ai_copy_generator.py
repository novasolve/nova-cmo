#!/usr/bin/env python3
"""
AI-Powered Copy Generation Engine
Uses LLMs to generate personalized, contextual outreach copy
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib

from .core.models import ICPProfile, ProspectData, CopyTemplate
from .core.storage import CopyFactoryStorage

logger = logging.getLogger(__name__)


class AICopyGenerator:
    """AI-powered copy generation using LLMs"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.logger = logger

        # Cache for generated copy to avoid redundant API calls
        self.cache_dir = "copy_factory/data/ai_cache"
        os.makedirs(self.cache_dir, exist_ok=True)

    def generate_personalized_copy(self, prospect: ProspectData, icp: ICPProfile,
                                 tone: str = "professional", length: str = "medium",
                                 context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate AI-powered personalized copy for a prospect"""

        # Create cache key
        cache_key = self._create_cache_key(prospect, icp, tone, length, context)
        cached_result = self._get_cached_result(cache_key)

        if cached_result:
            self.logger.info(f"Using cached AI copy for {prospect.login}")
            return cached_result

        # Generate fresh copy
        result = self._generate_ai_copy(prospect, icp, tone, length, context)

        # Cache the result
        self._cache_result(cache_key, result)

        return result

    def _generate_ai_copy(self, prospect: ProspectData, icp: ICPProfile,
                         tone: str, length: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate copy using AI"""

        # Build prospect context
        prospect_context = self._build_prospect_context(prospect, icp)

        # Build ICP context
        icp_context = self._build_icp_context(icp)

        # Build generation prompt
        prompt = self._build_generation_prompt(prospect_context, icp_context, tone, length, context)

        try:
            # Call AI API (simplified - in real implementation would use OpenAI SDK)
            ai_response = self._call_ai_api(prompt)

            # Parse and structure the response
            subject, body = self._parse_ai_response(ai_response)

            return {
                'subject': subject,
                'body': body,
                'tone': tone,
                'length': length,
                'generated_at': datetime.now().isoformat(),
                'ai_model': self.model,
                'prospect_id': prospect.lead_id,
                'icp_id': icp.id,
                'context_used': context or {},
                'prompt_tokens': len(prompt.split()),  # Rough estimate
                'quality_score': self._assess_copy_quality(subject, body)
            }

        except Exception as e:
            self.logger.error(f"AI copy generation failed: {e}")
            # Fallback to template-based generation
            return self._fallback_generation(prospect, icp, tone, length)

    def _build_prospect_context(self, prospect: ProspectData, icp: ICPProfile) -> str:
        """Build comprehensive context about the prospect"""

        context_parts = []

        # Basic info
        if prospect.name:
            context_parts.append(f"Name: {prospect.name}")

        if prospect.company:
            context_parts.append(f"Company: {prospect.company}")

        if prospect.location:
            context_parts.append(f"Location: {prospect.location}")

        # Professional context
        if prospect.bio:
            context_parts.append(f"Bio: {prospect.bio}")

        if prospect.language:
            context_parts.append(f"Primary programming language: {prospect.language}")

        if prospect.repo_full_name:
            context_parts.append(f"Key repository: {prospect.repo_full_name}")

        if prospect.repo_description:
            context_parts.append(f"Repository description: {prospect.repo_description}")

        # Activity context
        if prospect.followers:
            context_parts.append(f"GitHub followers: {prospect.followers}")

        if prospect.contributions_last_year:
            context_parts.append(f"Contributions last year: {prospect.contributions_last_year}")

        if prospect.public_repos:
            context_parts.append(f"Public repositories: {prospect.public_repos}")

        # ICP relevance
        if prospect.icp_matches:
            context_parts.append(f"ICP matches: {', '.join(prospect.icp_matches)}")

        # Intelligence score
        if prospect.intelligence_score:
            context_parts.append(f"Lead intelligence score: {prospect.intelligence_score}/10")

        return "\n".join(context_parts)

    def _build_icp_context(self, icp: ICPProfile) -> str:
        """Build comprehensive context about the ICP"""

        context_parts = []

        context_parts.append(f"ICP Name: {icp.name}")
        context_parts.append(f"ICP ID: {icp.id}")

        if icp.description:
            context_parts.append(f"Description: {icp.description}")

        # Personas
        if icp.personas:
            personas = []
            for persona in icp.personas:
                if 'title_contains' in persona:
                    personas.extend(persona['title_contains'])
                if 'roles' in persona:
                    personas.extend(persona['roles'])
            if personas:
                context_parts.append(f"Target personas/roles: {', '.join(personas)}")

        # Firmographics
        if icp.firmographics:
            firmo_parts = []
            for key, value in icp.firmographics.items():
                firmo_parts.append(f"{key}: {value}")
            context_parts.append(f"Firmographics: {'; '.join(firmo_parts)}")

        # Technographics
        if icp.technographics:
            techno_parts = []
            for key, value in icp.technographics.items():
                if isinstance(value, list):
                    techno_parts.append(f"{key}: {', '.join(value)}")
                else:
                    techno_parts.append(f"{key}: {value}")
            context_parts.append(f"Technographics: {'; '.join(techno_parts)}")

        # Triggers
        if icp.triggers:
            context_parts.append(f"Key triggers: {'; '.join(icp.triggers)}")

        # Disqualifiers
        if icp.disqualifiers:
            context_parts.append(f"Disqualifiers: {'; '.join(icp.disqualifiers)}")

        return "\n".join(context_parts)

    def _build_generation_prompt(self, prospect_context: str, icp_context: str,
                               tone: str, length: str, context: Optional[Dict[str, Any]]) -> str:
        """Build the AI generation prompt"""

        length_guide = {
            'short': 'Keep it concise, 50-100 words',
            'medium': 'Balanced length, 100-200 words',
            'long': 'Detailed and comprehensive, 200-300 words'
        }

        tone_guide = {
            'professional': 'Formal, business-appropriate language',
            'friendly': 'Warm, conversational tone',
            'technical': 'Technical depth, industry-specific terms',
            'casual': 'Relaxed, approachable style'
        }

        prompt = f"""You are a sales outreach specialist writing personalized emails to software developers and technical leaders.

TARGET PROSPECT CONTEXT:
{prospect_context}

TARGET ICP PROFILE:
{icp_context}

ADDITIONAL CONTEXT:
{context or 'None provided'}

WRITING INSTRUCTIONS:
- Tone: {tone_guide.get(tone, tone)}
- Length: {length_guide.get(length, length)}
- Personalize based on their specific background, technologies, and interests
- Reference their actual work, repositories, or contributions when relevant
- Focus on their ICP characteristics and pain points
- Include a clear call-to-action
- Make it conversational and engaging

Write a compelling outreach email with:
1. A personalized subject line
2. A personalized email body

Format your response as:
SUBJECT: [subject line]
BODY: [email body]
"""

        return prompt

    def _call_ai_api(self, prompt: str) -> str:
        """Call AI API (placeholder - would integrate with actual LLM API)"""
        # This is a placeholder implementation
        # In a real implementation, this would call OpenAI, Anthropic, or other LLM APIs

        # For now, return a simulated response
        return self._simulate_ai_response(prompt)

    def _simulate_ai_response(self, prompt: str) -> str:
        """Simulate AI response for development/testing"""

        # Extract key information from prompt
        lines = prompt.split('\n')
        prospect_info = {}
        icp_info = {}

        current_section = None
        for line in lines:
            if 'TARGET PROSPECT CONTEXT:' in line:
                current_section = 'prospect'
            elif 'TARGET ICP PROFILE:' in line:
                current_section = 'icp'
            elif current_section == 'prospect' and ':' in line:
                key, value = line.split(':', 1)
                prospect_info[key.strip()] = value.strip()
            elif current_section == 'icp' and ':' in line:
                key, value = line.split(':', 1)
                icp_info[key.strip()] = value.strip()

        # Generate realistic response
        name = prospect_info.get('Name', 'there')
        company = prospect_info.get('Company', 'your company')
        language = prospect_info.get('Primary programming language', 'Python')
        repo = prospect_info.get('Key repository', 'your project')

        subject = f"Question about your {language} work at {company}"

        body = f"""Hi {name},

I came across your work on {repo} and was really impressed by your expertise in {language}.

As someone who helps {icp_info.get('ICP Name', 'technical teams')} optimize their development workflows, I noticed you might be dealing with some of the same challenges we're seeing in the {language} ecosystem.

I'd love to hear about your experience and see if there are any specific areas where we could help your team work more efficiently.

Would you be open to a quick chat about your current setup?

Best regards,
[Your Name]
"""

        return f"SUBJECT: {subject}\nBODY: {body}"

    def _parse_ai_response(self, response: str) -> Tuple[str, str]:
        """Parse AI response into subject and body"""
        lines = response.split('\n')
        subject = ""
        body = ""

        in_body = False
        for line in lines:
            if line.startswith('SUBJECT:'):
                subject = line.replace('SUBJECT:', '').strip()
            elif line.startswith('BODY:'):
                in_body = True
                body = line.replace('BODY:', '').strip() + '\n'
            elif in_body:
                body += line + '\n'

        return subject, body.strip()

    def _assess_copy_quality(self, subject: str, body: str) -> float:
        """Assess the quality of generated copy"""
        score = 0.0

        # Subject line quality
        if len(subject) > 10 and len(subject) < 80:
            score += 0.3
        if any(word in subject.lower() for word in ['question', 'work', 'experience', 'help']):
            score += 0.2

        # Body quality
        if len(body) > 100:
            score += 0.2
        if 'hi' in body.lower()[:10]:
            score += 0.1
        if any(word in body.lower() for word in ['experience', 'help', 'chat', 'team']):
            score += 0.2

        return min(1.0, score)

    def _fallback_generation(self, prospect: ProspectData, icp: ICPProfile,
                           tone: str, length: str) -> Dict[str, Any]:
        """Fallback to template-based generation if AI fails"""

        from .core.copy_generator import CopyGenerator

        generator = CopyGenerator()
        template = self._create_fallback_template(icp)

        result = generator.generate_copy(template, prospect, icp)

        return {
            'subject': result.get('subject'),
            'body': result.get('body'),
            'tone': tone,
            'length': length,
            'generated_at': datetime.now().isoformat(),
            'ai_model': 'fallback',
            'prospect_id': prospect.lead_id,
            'icp_id': icp.id,
            'fallback': True,
            'quality_score': 0.5
        }

    def _create_fallback_template(self, icp: ICPProfile) -> CopyTemplate:
        """Create a basic fallback template"""
        from .core.models import CopyTemplate

        return CopyTemplate(
            id=f"fallback_{icp.id}",
            name=f"Fallback Template for {icp.name}",
            icp_id=icp.id,
            template_type="email",
            subject_template="Question about your work - ${icp_name}",
            body_template="""Hi ${first_name},

I came across your work and wanted to reach out about ${icp_name}.

Would you be interested in learning more about how we help teams like yours?

Best regards,
[Your Name]
""",
            variables=["first_name", "icp_name"]
        )

    def _create_cache_key(self, prospect: ProspectData, icp: ICPProfile,
                         tone: str, length: str, context: Optional[Dict[str, Any]]) -> str:
        """Create a unique cache key for the generation request"""
        key_data = {
            'prospect_id': prospect.lead_id,
            'icp_id': icp.id,
            'tone': tone,
            'length': length,
            'context': context or {},
            'model': self.model
        }

        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached result if available"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cached = json.load(f)

                # Check if cache is still valid (24 hours)
                cached_time = datetime.fromisoformat(cached['generated_at'])
                if (datetime.now() - cached_time).total_seconds() < 86400:  # 24 hours
                    return cached

            except Exception as e:
                self.logger.warning(f"Error reading cache: {e}")

        return None

    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Cache the generation result"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        try:
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Error writing cache: {e}")

    def bulk_generate_copy(self, prospects: List[ProspectData], icp: ICPProfile,
                          tone: str = "professional", length: str = "medium",
                          max_workers: int = 4) -> List[Dict[str, Any]]:
        """Generate copy for multiple prospects in parallel"""

        results = []

        def generate_single(prospect):
            try:
                return self.generate_personalized_copy(prospect, icp, tone, length)
            except Exception as e:
                self.logger.error(f"Error generating copy for {prospect.login}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(generate_single, prospect) for prospect in prospects]
            for future in futures:
                result = future.result()
                if result:
                    results.append(result)

        self.logger.info(f"Generated AI copy for {len(results)} prospects")
        return results

    def optimize_copy_for_conversion(self, base_copy: Dict[str, Any],
                                   prospect: ProspectData, icp: ICPProfile,
                                   optimization_goal: str = "response_rate") -> Dict[str, Any]:
        """Use AI to optimize copy for better conversion rates"""

        prompt = f"""Optimize this outreach copy for better {optimization_goal}:

ORIGINAL SUBJECT: {base_copy['subject']}
ORIGINAL BODY: {base_copy['body']}

PROSPECT CONTEXT:
{self._build_prospect_context(prospect, icp)}

ICP CONTEXT:
{self._build_icp_context(icp)}

Provide an optimized version that:
1. Has higher chance of getting a response
2. Is more personalized and relevant
3. Has a clearer value proposition
4. Has a compelling call-to-action

Return in the same format:
SUBJECT: [optimized subject]
BODY: [optimized body]
"""

        try:
            optimized_response = self._call_ai_api(prompt)
            subject, body = self._parse_ai_response(optimized_response)

            return {
                'subject': subject,
                'body': body,
                'original_subject': base_copy['subject'],
                'original_body': base_copy['body'],
                'optimization_goal': optimization_goal,
                'optimized_at': datetime.now().isoformat(),
                'improvement_score': self._calculate_improvement_score(base_copy, subject, body)
            }

        except Exception as e:
            self.logger.error(f"Copy optimization failed: {e}")
            return base_copy

    def _calculate_improvement_score(self, original: Dict[str, Any],
                                   new_subject: str, new_body: str) -> float:
        """Calculate improvement score for optimized copy"""
        score = 0.0

        # Subject improvements
        if len(new_subject) > len(original['subject']) * 0.8:
            score += 0.2
        if any(word in new_subject.lower() for word in ['help', 'question', 'curious', 'interested']):
            score += 0.3

        # Body improvements
        if len(new_body) > len(original['body']) * 0.9:
            score += 0.2
        if 'value proposition' in new_body.lower() or 'benefit' in new_body.lower():
            score += 0.3

        return min(1.0, score)
