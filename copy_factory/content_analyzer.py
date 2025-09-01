#!/usr/bin/env python3
"""
AI-Powered Content Analysis System
Analyzes GitHub profiles, repositories, and content for deep insights
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import re
from collections import defaultdict, Counter
import hashlib

from .core.models import ProspectData
from .ai_copy_generator import AICopyGenerator

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """AI-powered analysis of prospect content and profiles"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.ai_generator = AICopyGenerator(api_key)
        self.logger = logger

        # Analysis cache
        self.analysis_cache_dir = "copy_factory/data/content_analysis"
        os.makedirs(self.analysis_cache_dir, exist_ok=True)

    def analyze_prospect_content(self, prospect: ProspectData,
                               include_repo_analysis: bool = True) -> Dict[str, Any]:
        """Perform comprehensive AI analysis of prospect content"""

        analysis = {
            'prospect_id': prospect.lead_id,
            'analysis_timestamp': datetime.now().isoformat(),
            'insights': {},
            'pain_points': [],
            'interests': [],
            'communication_style': {},
            'technical_expertise': {},
            'engagement_patterns': {},
            'content_themes': []
        }

        try:
            # Analyze bio and profile information
            if prospect.bio:
                bio_analysis = self._analyze_bio(prospect.bio)
                analysis['insights'].update(bio_analysis)

            # Analyze repository content
            if include_repo_analysis and prospect.repo_description:
                repo_analysis = self._analyze_repository_content(prospect)
                analysis['insights'].update(repo_analysis)

            # Extract technical expertise
            analysis['technical_expertise'] = self._extract_technical_expertise(prospect)

            # Identify pain points and challenges
            analysis['pain_points'] = self._identify_pain_points(prospect)

            # Analyze interests and motivations
            analysis['interests'] = self._analyze_interests(prospect)

            # Determine communication style preferences
            analysis['communication_style'] = self._determine_communication_style(prospect)

            # Analyze engagement patterns
            analysis['engagement_patterns'] = self._analyze_engagement_patterns(prospect)

            # Extract content themes
            analysis['content_themes'] = self._extract_content_themes(prospect)

        except Exception as e:
            self.logger.error(f"Error analyzing prospect {prospect.login}: {e}")
            analysis['error'] = str(e)

        return analysis

    def _analyze_bio(self, bio: str) -> Dict[str, Any]:
        """Analyze prospect bio for insights"""

        insights = {}

        # Extract key information using AI
        prompt = f"""Analyze this GitHub bio and extract key insights:

BIO: {bio}

Provide analysis in JSON format with these fields:
- role: Their primary role or job title
- experience_level: junior/mid/senior/expert
- interests: List of main interests
- personality_traits: Key personality indicators
- communication_style: formal/casual/technical
- motivation_signals: What drives them

Return only valid JSON:
"""

        try:
            response = self.ai_generator._call_ai_api(prompt)
            # Parse JSON response (simplified)
            insights = self._parse_bio_analysis(response)
        except Exception as e:
            self.logger.warning(f"Bio analysis failed: {e}")
            insights = self._fallback_bio_analysis(bio)

        return insights

    def _parse_bio_analysis(self, response: str) -> Dict[str, Any]:
        """Parse AI response for bio analysis"""
        try:
            # Extract JSON from response (simplified parsing)
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
        except:
            pass

        return self._fallback_bio_analysis("")

    def _fallback_bio_analysis(self, bio: str) -> Dict[str, Any]:
        """Fallback bio analysis using rules"""

        insights = {
            'role': 'developer',
            'experience_level': 'unknown',
            'interests': [],
            'personality_traits': [],
            'communication_style': 'technical',
            'motivation_signals': []
        }

        # Simple keyword-based analysis
        bio_lower = bio.lower()

        if any(word in bio_lower for word in ['senior', 'lead', 'principal', 'architect']):
            insights['experience_level'] = 'senior'
        elif any(word in bio_lower for word in ['junior', 'intern', 'new grad']):
            insights['experience_level'] = 'junior'
        else:
            insights['experience_level'] = 'mid'

        if 'open source' in bio_lower:
            insights['interests'].append('open source')
            insights['motivation_signals'].append('community contribution')

        if any(word in bio_lower for word in ['learning', 'study', 'research']):
            insights['interests'].append('continuous learning')

        return insights

    def _analyze_repository_content(self, prospect: ProspectData) -> Dict[str, Any]:
        """Analyze repository content for deeper insights"""

        content = f"{prospect.repo_description or ''} {prospect.bio or ''}"

        prompt = f"""Analyze this repository description and extract technical insights:

CONTENT: {content}

Identify:
- primary_technologies: Main technologies used
- project_complexity: simple/moderate/complex
- project_maturity: early/mature/maintained
- collaboration_signals: Signs of team collaboration
- innovation_indicators: Novel approaches or techniques
- scalability_concerns: Performance or scaling considerations

Return as JSON:
"""

        try:
            response = self.ai_generator._call_ai_api(prompt)
            return self._parse_repo_analysis(response)
        except Exception as e:
            self.logger.warning(f"Repository analysis failed: {e}")
            return self._fallback_repo_analysis(prospect)

    def _parse_repo_analysis(self, response: str) -> Dict[str, Any]:
        """Parse repository analysis response"""
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
        except:
            pass

        return {}

    def _fallback_repo_analysis(self, prospect: ProspectData) -> Dict[str, Any]:
        """Fallback repository analysis"""

        analysis = {
            'primary_technologies': [prospect.language] if prospect.language else [],
            'project_complexity': 'moderate',
            'project_maturity': 'maintained',
            'collaboration_signals': [],
            'innovation_indicators': [],
            'scalability_concerns': []
        }

        # Analyze based on available data
        if prospect.stars is not None and prospect.stars > 100:
            analysis['project_maturity'] = 'mature'

        if prospect.forks is not None and prospect.forks > 10:
            analysis['collaboration_signals'].append('active forking')

        return analysis

    def _extract_technical_expertise(self, prospect: ProspectData) -> Dict[str, Any]:
        """Extract technical expertise indicators"""

        expertise = {
            'primary_language': prospect.language,
            'expertise_level': 'unknown',
            'specializations': [],
            'toolchain': [],
            'domain_expertise': []
        }

        # Analyze based on activity metrics
        total_activity = (prospect.contributions_last_year or 0) + (prospect.public_repos or 0)

        if total_activity > 100:
            expertise['expertise_level'] = 'expert'
        elif total_activity > 50:
            expertise['expertise_level'] = 'advanced'
        elif total_activity > 20:
            expertise['expertise_level'] = 'intermediate'
        else:
            expertise['expertise_level'] = 'beginner'

        # Extract specializations from topics
        if prospect.topics:
            # Group topics by category
            topic_categories = {
                'web': ['javascript', 'typescript', 'react', 'vue', 'angular', 'html', 'css'],
                'backend': ['python', 'java', 'go', 'rust', 'node', 'django', 'flask', 'spring'],
                'data': ['pandas', 'numpy', 'tensorflow', 'pytorch', 'machine-learning', 'data-science'],
                'devops': ['docker', 'kubernetes', 'aws', 'terraform', 'ci-cd', 'jenkins']
            }

            for category, keywords in topic_categories.items():
                if any(topic.lower() in keywords for topic in prospect.topics):
                    expertise['specializations'].append(category)

        # Infer toolchain from topics
        toolchain_indicators = ['pytest', 'docker', 'github-actions', 'pre-commit', 'black']
        expertise['toolchain'] = [topic for topic in (prospect.topics or [])
                                if topic.lower() in toolchain_indicators]

        return expertise

    def _identify_pain_points(self, prospect: ProspectData) -> List[str]:
        """Identify potential pain points and challenges"""

        pain_points = []

        # Based on repository and activity patterns
        if prospect.contributions_last_year is not None and prospect.contributions_last_year < 10:
            pain_points.append("Low contribution activity - may indicate maintenance challenges")

        if prospect.followers is not None and prospect.followers < 5:
            pain_points.append("Low profile visibility - networking or marketing challenges")

        if prospect.public_repos is not None and prospect.public_repos > 50:
            pain_points.append("Managing many repositories - organization and maintenance overhead")

        # Based on topics indicating problem areas
        if prospect.topics:
            topic_pain_points = {
                'deprecated': "Working with outdated technologies",
                'legacy': "Maintaining legacy codebases",
                'technical-debt': "Accumulated technical debt",
                'monolith': "Managing monolithic architectures",
                'scalability': "Scaling challenges"
            }

            for topic in prospect.topics:
                if topic.lower() in topic_pain_points:
                    pain_points.append(topic_pain_points[topic.lower()])

        # AI-powered pain point identification
        if prospect.bio or prospect.repo_description:
            content = f"{prospect.bio or ''} {prospect.repo_description or ''}"
            ai_pain_points = self._ai_identify_pain_points(content)
            pain_points.extend(ai_pain_points)

        return list(set(pain_points))  # Remove duplicates

    def _ai_identify_pain_points(self, content: str) -> List[str]:
        """Use AI to identify pain points from content"""

        prompt = f"""Analyze this content and identify potential pain points or challenges:

CONTENT: {content}

Look for signals of:
- Technical debt
- Scaling issues
- Maintenance challenges
- Technology migration needs
- Performance problems
- Team collaboration issues

List specific pain points identified:
"""

        try:
            response = self.ai_generator._call_ai_api(prompt)
            return self._parse_pain_points(response)
        except:
            return []

    def _parse_pain_points(self, response: str) -> List[str]:
        """Parse pain points from AI response"""
        # Simple parsing - split by lines and clean up
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        pain_points = [line for line in lines if len(line) > 10 and not line.startswith('-')]
        return pain_points[:5]  # Limit to top 5

    def _analyze_interests(self, prospect: ProspectData) -> List[str]:
        """Analyze prospect interests and motivations"""

        interests = []

        # From bio analysis
        if prospect.bio:
            bio_lower = prospect.bio.lower()

            interest_keywords = {
                'open source': ['open source', 'oss', 'community'],
                'machine learning': ['ml', 'machine learning', 'ai', 'artificial intelligence'],
                'web development': ['web', 'frontend', 'backend', 'full-stack'],
                'devops': ['devops', 'infrastructure', 'cloud', 'deployment'],
                'security': ['security', 'cryptography', 'authentication'],
                'performance': ['performance', 'optimization', 'scalability'],
                'education': ['teaching', 'mentoring', 'learning']
            }

            for interest, keywords in interest_keywords.items():
                if any(keyword in bio_lower for keyword in keywords):
                    interests.append(interest)

        # From repository topics
        if prospect.topics:
            topic_interests = {
                'machine-learning': 'machine learning',
                'data-science': 'data science',
                'web-development': 'web development',
                'api': 'API development',
                'testing': 'software testing',
                'documentation': 'technical writing'
            }

            for topic in prospect.topics:
                if topic.lower() in topic_interests:
                    interests.append(topic_interests[topic.lower()])

        return list(set(interests))

    def _determine_communication_style(self, prospect: ProspectData) -> Dict[str, Any]:
        """Determine prospect's preferred communication style"""

        style = {
            'formality': 'neutral',
            'technical_level': 'intermediate',
            'engagement_preference': 'professional',
            'response_expectations': 'balanced'
        }

        # Analyze based on available data
        content = f"{prospect.bio or ''} {prospect.repo_description or ''}"

        if content:
            content_lower = content.lower()

            # Formality analysis
            if any(word in content_lower for word in ['professional', 'enterprise', 'corporate']):
                style['formality'] = 'formal'
            elif any(word in content_lower for word in ['hey', 'awesome', 'cool', 'love']):
                style['formality'] = 'casual'

            # Technical level
            technical_indicators = ['algorithm', 'architecture', 'optimization', 'scalability']
            if any(indicator in content_lower for indicator in technical_indicators):
                style['technical_level'] = 'advanced'

            # Engagement preference
            if 'community' in content_lower or 'open source' in content_lower:
                style['engagement_preference'] = 'community'
            elif 'collaboration' in content_lower or 'team' in content_lower:
                style['engagement_preference'] = 'collaborative'

        return style

    def _analyze_engagement_patterns(self, prospect: ProspectData) -> Dict[str, Any]:
        """Analyze prospect's engagement patterns"""

        patterns = {
            'activity_level': 'moderate',
            'consistency': 'regular',
            'collaboration_style': 'individual',
            'response_time': 'moderate'
        }

        # Activity level based on contributions
        if prospect.contributions_last_year:
            if prospect.contributions_last_year > 100:
                patterns['activity_level'] = 'high'
            elif prospect.contributions_last_year < 20:
                patterns['activity_level'] = 'low'

        # Collaboration style based on repo metrics
        if prospect.forks and prospect.forks > prospect.public_repos:
            patterns['collaboration_style'] = 'collaborative'

        return patterns

    def _extract_content_themes(self, prospect: ProspectData) -> List[str]:
        """Extract main content themes from prospect data"""

        themes = []

        # From topics
        if prospect.topics:
            themes.extend(prospect.topics[:5])  # Top 5 topics

        # From bio keywords
        if prospect.bio:
            bio_words = re.findall(r'\b\w+\b', prospect.bio.lower())
            common_words = [word for word in bio_words if len(word) > 3]
            word_counts = Counter(common_words)
            top_words = [word for word, count in word_counts.most_common(3) if count > 1]
            themes.extend(top_words)

        return list(set(themes))

    def generate_personalized_insights(self, prospect: ProspectData) -> Dict[str, Any]:
        """Generate comprehensive personalized insights for copy generation"""

        # Get cached analysis or perform new analysis
        cache_key = f"insights_{prospect.lead_id}"
        cached = self._get_cached_analysis(cache_key)

        if cached:
            return cached

        # Perform full analysis
        analysis = self.analyze_prospect_content(prospect)

        # Generate actionable insights
        insights = {
            'prospect_id': prospect.lead_id,
            'personalized_angles': self._generate_personalized_angles(analysis),
            'recommended_tone': self._recommend_tone(analysis),
            'key_value_props': self._identify_value_propositions(analysis),
            'avoid_topics': self._identify_topics_to_avoid(analysis),
            'engagement_hooks': self._create_engagement_hooks(analysis),
            'timing_recommendations': self._recommend_timing(analysis)
        }

        # Combine analysis with insights
        full_insights = {**analysis, **insights}

        # Cache the results
        self._cache_analysis(cache_key, full_insights)

        return full_insights

    def _generate_personalized_angles(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate personalized outreach angles"""

        angles = []

        # Based on technical expertise
        expertise = analysis.get('technical_expertise', {})
        if expertise.get('expertise_level') == 'expert':
            angles.append("Leverage their deep technical expertise")

        # Based on interests
        interests = analysis.get('interests', [])
        if 'open source' in interests:
            angles.append("Connect through open source community involvement")

        # Based on pain points
        pain_points = analysis.get('pain_points', [])
        if pain_points:
            angles.append("Address their specific technical challenges")

        # Based on communication style
        comm_style = analysis.get('communication_style', {})
        if comm_style.get('formality') == 'casual':
            angles.append("Use a friendly, collaborative approach")

        return angles

    def _recommend_tone(self, analysis: Dict[str, Any]) -> str:
        """Recommend communication tone"""

        comm_style = analysis.get('communication_style', {})

        if comm_style.get('formality') == 'formal':
            return 'professional'
        elif comm_style.get('formality') == 'casual':
            return 'friendly'
        else:
            return 'professional'

    def _identify_value_propositions(self, analysis: Dict[str, Any]) -> List[str]:
        """Identify relevant value propositions"""

        value_props = []

        # Based on pain points
        pain_points = analysis.get('pain_points', [])
        if 'technical debt' in ' '.join(pain_points).lower():
            value_props.append("Help reduce technical debt")

        # Based on interests
        interests = analysis.get('interests', [])
        if 'machine learning' in interests:
            value_props.append("Accelerate ML development")

        # Based on technical expertise
        expertise = analysis.get('technical_expertise', {})
        if 'web' in expertise.get('specializations', []):
            value_props.append("Improve web application performance")

        return value_props

    def _identify_topics_to_avoid(self, analysis: Dict[str, Any]) -> List[str]:
        """Identify topics that might be sensitive or irrelevant"""

        avoid = []

        # If they're focused on a specific technology, don't push alternatives
        expertise = analysis.get('technical_expertise', {})
        primary_lang = expertise.get('primary_language')
        if primary_lang:
            avoid.append(f"Avoid pushing non-{primary_lang} solutions")

        # If they're very senior, avoid basic content
        if expertise.get('expertise_level') == 'expert':
            avoid.append("Avoid beginner-level content or obvious advice")

        return avoid

    def _create_engagement_hooks(self, analysis: Dict[str, Any]) -> List[str]:
        """Create personalized engagement hooks"""

        hooks = []

        # Based on repository work
        if analysis.get('insights', {}).get('project_maturity') == 'mature':
            hooks.append("Reference their successful project as social proof")

        # Based on community involvement
        interests = analysis.get('interests', [])
        if 'open source' in interests:
            hooks.append("Highlight mutual open source interests")

        # Based on technical expertise
        expertise = analysis.get('technical_expertise', {})
        if 'expert' in expertise.get('expertise_level', ''):
            hooks.append("Position as peer-to-peer technical discussion")

        return hooks

    def _recommend_timing(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend optimal timing for outreach"""

        timing = {
            'best_days': ['Tuesday', 'Wednesday', 'Thursday'],
            'best_times': ['10:00', '14:00', '16:00'],
            'reasoning': 'Standard developer work hours'
        }

        # Adjust based on engagement patterns
        patterns = analysis.get('engagement_patterns', {})
        if patterns.get('activity_level') == 'high':
            timing['reasoning'] = 'High activity suggests flexible availability'

        return timing

    def _get_cached_analysis(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached analysis if available"""

        cache_file = os.path.join(self.analysis_cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cached = json.load(f)

                # Check if cache is still valid (7 days)
                cached_time = datetime.fromisoformat(cached['analysis_timestamp'])
                if (datetime.now() - cached_time).total_seconds() < 604800:  # 7 days
                    return cached

            except Exception as e:
                self.logger.warning(f"Error reading cached analysis: {e}")

        return None

    def _cache_analysis(self, cache_key: str, analysis: Dict[str, Any]) -> None:
        """Cache analysis results"""

        cache_file = os.path.join(self.analysis_cache_dir, f"{cache_key}.json")

        try:
            with open(cache_file, 'w') as f:
                json.dump(analysis, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Error caching analysis: {e}")

    def batch_analyze_prospects(self, prospects: List[ProspectData],
                              max_workers: int = 4) -> Dict[str, Dict[str, Any]]:
        """Analyze multiple prospects in batch"""

        from concurrent.futures import ThreadPoolExecutor

        results = {}

        def analyze_single(prospect):
            try:
                return prospect.lead_id, self.generate_personalized_insights(prospect)
            except Exception as e:
                self.logger.error(f"Error analyzing prospect {prospect.login}: {e}")
                return prospect.lead_id, {'error': str(e)}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(analyze_single, prospect) for prospect in prospects]
            for future in futures:
                prospect_id, analysis = future.result()
                results[prospect_id] = analysis

        self.logger.info(f"Analyzed {len(results)} prospects")
        return results
