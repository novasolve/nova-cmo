#!/usr/bin/env python3
"""
AI-Powered Smart ICP Matching System
Uses embeddings and semantic similarity for intelligent prospect-ICP matching
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import numpy as np
from collections import defaultdict
import hashlib

from .core.models import ICPProfile, ProspectData
from .core.storage import CopyFactoryStorage

logger = logging.getLogger(__name__)


class SmartICPMatcher:
    """AI-powered ICP matching using embeddings and semantic similarity"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.logger = logger

        # Embedding cache
        self.embedding_cache_dir = "copy_factory/data/embeddings"
        os.makedirs(self.embedding_cache_dir, exist_ok=True)

        # Matching thresholds
        self.similarity_threshold = 0.7  # Minimum similarity score
        self.top_matches_limit = 3  # Number of top matches to return

    def match_prospect_to_icps(self, prospect: ProspectData,
                              icps: List[ICPProfile]) -> List[Tuple[str, float]]:
        """Match a prospect to ICPs using AI-powered semantic similarity"""

        if not icps:
            return []

        # Get prospect embedding
        prospect_embedding = self._get_prospect_embedding(prospect)
        if prospect_embedding is None:
            self.logger.warning(f"Could not generate embedding for prospect {prospect.login}")
            return []

        # Get ICP embeddings
        icp_embeddings = []
        for icp in icps:
            embedding = self._get_icp_embedding(icp)
            if embedding is not None:
                icp_embeddings.append((icp.id, embedding))

        if not icp_embeddings:
            self.logger.warning("Could not generate embeddings for any ICPs")
            return []

        # Calculate similarities
        matches = []
        for icp_id, icp_embedding in icp_embeddings:
            similarity = self._calculate_cosine_similarity(prospect_embedding, icp_embedding)
            if similarity >= self.similarity_threshold:
                matches.append((icp_id, similarity))

        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x[1], reverse=True)

        # Return top matches
        return matches[:self.top_matches_limit]

    def batch_match_prospects(self, prospects: List[ProspectData],
                            icps: List[ICPProfile], max_workers: int = 4) -> Dict[str, List[Tuple[str, float]]]:
        """Match multiple prospects to ICPs efficiently"""

        from concurrent.futures import ThreadPoolExecutor

        results = {}

        def match_single(prospect):
            try:
                matches = self.match_prospect_to_icps(prospect, icps)
                return prospect.lead_id, matches
            except Exception as e:
                self.logger.error(f"Error matching prospect {prospect.login}: {e}")
                return prospect.lead_id, []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(match_single, prospect) for prospect in prospects]
            for future in futures:
                prospect_id, matches = future.result()
                if matches:
                    results[prospect_id] = matches

        self.logger.info(f"Smart matched {len(results)} prospects to ICPs")
        return results

    def _get_prospect_embedding(self, prospect: ProspectData) -> Optional[np.ndarray]:
        """Generate embedding for a prospect"""

        # Create prospect text representation
        prospect_text = self._prospect_to_text(prospect)

        # Check cache first
        cache_key = self._create_cache_key(prospect_text, "prospect")
        cached = self._get_cached_embedding(cache_key)
        if cached is not None:
            return cached

        # Generate new embedding
        embedding = self._generate_embedding(prospect_text)
        if embedding is not None:
            self._cache_embedding(cache_key, embedding)

        return embedding

    def _get_icp_embedding(self, icp: ICPProfile) -> Optional[np.ndarray]:
        """Generate embedding for an ICP"""

        # Create ICP text representation
        icp_text = self._icp_to_text(icp)

        # Check cache first
        cache_key = self._create_cache_key(icp_text, "icp")
        cached = self._get_cached_embedding(cache_key)
        if cached is not None:
            return cached

        # Generate new embedding
        embedding = self._generate_embedding(icp_text)
        if embedding is not None:
            self._cache_embedding(cache_key, embedding)

        return embedding

    def _prospect_to_text(self, prospect: ProspectData) -> str:
        """Convert prospect data to text for embedding"""

        text_parts = []

        # Basic info
        if prospect.name:
            text_parts.append(f"Name: {prospect.name}")
        if prospect.company:
            text_parts.append(f"Company: {prospect.company}")
        if prospect.location:
            text_parts.append(f"Location: {prospect.location}")

        # Professional info
        if prospect.bio:
            text_parts.append(f"Bio: {prospect.bio}")
        if prospect.language:
            text_parts.append(f"Programming language: {prospect.language}")
        if prospect.repo_description:
            text_parts.append(f"Repository description: {prospect.repo_description}")

        # Activity info
        if prospect.followers:
            text_parts.append(f"GitHub followers: {prospect.followers}")
        if prospect.contributions_last_year:
            text_parts.append(f"Contributions last year: {prospect.contributions_last_year}")
        if prospect.public_repos:
            text_parts.append(f"Public repositories: {prospect.public_repos}")

        # Technical topics
        if prospect.topics:
            text_parts.append(f"Topics: {', '.join(prospect.topics)}")

        return ". ".join(text_parts)

    def _icp_to_text(self, icp: ICPProfile) -> str:
        """Convert ICP data to text for embedding"""

        text_parts = []

        # Basic info
        text_parts.append(f"ICP Name: {icp.name}")
        if icp.description:
            text_parts.append(f"Description: {icp.description}")

        # Personas
        if icp.personas:
            personas = []
            for persona in icp.personas:
                if 'title_contains' in persona:
                    personas.extend(persona['title_contains'])
                if 'roles' in persona:
                    personas.extend(persona['roles'])
            if personas:
                text_parts.append(f"Target personas: {', '.join(personas)}")

        # Firmographics
        if icp.firmographics:
            firmo = []
            for key, value in icp.firmographics.items():
                firmo.append(f"{key}: {value}")
            text_parts.append(f"Firmographics: {'; '.join(firmo)}")

        # Technographics
        if icp.technographics:
            techno = []
            for key, value in icp.technographics.items():
                if isinstance(value, list):
                    techno.append(f"{key}: {', '.join(value)}")
                else:
                    techno.append(f"{key}: {value}")
            text_parts.append(f"Technographics: {'; '.join(techno)}")

        # Triggers
        if icp.triggers:
            text_parts.append(f"Triggers: {'; '.join(icp.triggers)}")

        # GitHub queries (for context)
        if icp.github_queries:
            text_parts.append(f"GitHub search patterns: {'; '.join(icp.github_queries[:3])}")  # Limit to first 3

        return ". ".join(text_parts)

    def _generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for text using AI"""

        if not text or len(text.strip()) < 10:
            return None

        try:
            # This is a placeholder - in real implementation would use OpenAI embeddings API
            # For now, return a simulated embedding
            return self._simulate_embedding(text)

        except Exception as e:
            self.logger.error(f"Error generating embedding: {e}")
            return None

    def _simulate_embedding(self, text: str) -> np.ndarray:
        """Simulate embedding generation for development/testing"""

        # Create a deterministic but varied embedding based on text content
        # This ensures similar texts get similar embeddings
        hash_value = hashlib.md5(text.encode()).hexdigest()
        np.random.seed(int(hash_value[:8], 16))

        # Generate a 1536-dimensional embedding (similar to OpenAI's text-embedding-ada-002)
        embedding = np.random.normal(0, 1, 1536)

        # Normalize to unit vector
        return embedding / np.linalg.norm(embedding)

    def _calculate_cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings"""

        if embedding1.shape != embedding2.shape:
            return 0.0

        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _create_cache_key(self, text: str, content_type: str) -> str:
        """Create a cache key for embeddings"""

        content_hash = hashlib.md5(text.encode()).hexdigest()
        return f"{content_type}_{content_hash}"

    def _get_cached_embedding(self, cache_key: str) -> Optional[np.ndarray]:
        """Get cached embedding if available"""

        cache_file = os.path.join(self.embedding_cache_dir, f"{cache_key}.npy")

        if os.path.exists(cache_file):
            try:
                return np.load(cache_file)
            except Exception as e:
                self.logger.warning(f"Error loading cached embedding: {e}")

        return None

    def _cache_embedding(self, cache_key: str, embedding: np.ndarray) -> None:
        """Cache an embedding"""

        cache_file = os.path.join(self.embedding_cache_dir, f"{cache_key}.npy")

        try:
            np.save(cache_file, embedding)
        except Exception as e:
            self.logger.warning(f"Error caching embedding: {e}")

    def analyze_matching_performance(self, prospects: List[ProspectData],
                                   icps: List[ICPProfile]) -> Dict[str, Any]:
        """Analyze the performance of ICP matching"""

        if not prospects or not icps:
            return {}

        # Perform matching
        matches = self.batch_match_prospects(prospects, icps)

        # Calculate statistics
        total_prospects = len(prospects)
        matched_prospects = len(matches)
        match_rate = matched_prospects / total_prospects if total_prospects > 0 else 0

        # ICP distribution
        icp_match_counts = defaultdict(int)
        similarity_scores = []

        for prospect_matches in matches.values():
            for icp_id, similarity in prospect_matches:
                icp_match_counts[icp_id] += 1
                similarity_scores.append(similarity)

        # Average matches per prospect
        avg_matches_per_prospect = sum(len(matches) for matches in matches.values()) / matched_prospects if matched_prospects > 0 else 0

        # Similarity score statistics
        avg_similarity = np.mean(similarity_scores) if similarity_scores else 0
        min_similarity = min(similarity_scores) if similarity_scores else 0
        max_similarity = max(similarity_scores) if similarity_scores else 0

        return {
            'total_prospects': total_prospects,
            'matched_prospects': matched_prospects,
            'match_rate': round(match_rate, 3),
            'avg_matches_per_prospect': round(avg_matches_per_prospect, 2),
            'icp_distribution': dict(icp_match_counts),
            'similarity_stats': {
                'average': round(avg_similarity, 3),
                'min': round(min_similarity, 3),
                'max': round(max_similarity, 3)
            },
            'matching_threshold': self.similarity_threshold,
            'top_matches_limit': self.top_matches_limit
        }

    def find_similar_prospects(self, target_prospect: ProspectData,
                             prospects: List[ProspectData], top_k: int = 5) -> List[Tuple[str, float]]:
        """Find prospects similar to a target prospect"""

        # Get target embedding
        target_embedding = self._get_prospect_embedding(target_prospect)
        if target_embedding is None:
            return []

        similarities = []

        for prospect in prospects:
            if prospect.lead_id == target_prospect.lead_id:
                continue  # Skip self

            prospect_embedding = self._get_prospect_embedding(prospect)
            if prospect_embedding is not None:
                similarity = self._calculate_cosine_similarity(target_embedding, prospect_embedding)
                similarities.append((prospect.lead_id, similarity))

        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]

    def cluster_prospects_by_similarity(self, prospects: List[ProspectData],
                                      icps: List[ICPProfile], n_clusters: int = 5) -> Dict[str, List[str]]:
        """Cluster prospects based on similarity for ICP targeting"""

        if len(prospects) < n_clusters:
            return {}

        # Get all prospect embeddings
        embeddings = []
        valid_prospects = []

        for prospect in prospects:
            embedding = self._get_prospect_embedding(prospect)
            if embedding is not None:
                embeddings.append(embedding)
                valid_prospects.append(prospect)

        if len(embeddings) < n_clusters:
            return {}

        # Simple clustering using embeddings (in real implementation would use more sophisticated clustering)
        from sklearn.cluster import KMeans

        embeddings_array = np.array(embeddings)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(embeddings_array)

        # Group prospects by cluster
        clusters = defaultdict(list)
        for prospect, label in zip(valid_prospects, cluster_labels):
            clusters[f"cluster_{label}"].append(prospect.lead_id)

        return dict(clusters)

    def generate_icp_recommendations(self, prospect: ProspectData,
                                   icps: List[ICPProfile]) -> List[Dict[str, Any]]:
        """Generate detailed ICP recommendations with explanations"""

        matches = self.match_prospect_to_icps(prospect, icps)

        recommendations = []

        for icp_id, similarity_score in matches:
            icp = next((icp for icp in icps if icp.id == icp_id), None)
            if not icp:
                continue

            # Generate explanation for the match
            explanation = self._generate_match_explanation(prospect, icp, similarity_score)

            recommendation = {
                'icp_id': icp_id,
                'icp_name': icp.name,
                'similarity_score': round(similarity_score, 3),
                'confidence': self._calculate_confidence_score(similarity_score),
                'explanation': explanation,
                'recommended_actions': self._generate_recommended_actions(prospect, icp)
            }

            recommendations.append(recommendation)

        return recommendations

    def _generate_match_explanation(self, prospect: ProspectData,
                                  icp: ICPProfile, similarity: float) -> str:
        """Generate human-readable explanation for ICP match"""

        reasons = []

        # Language match
        if prospect.language and icp.technographics.get('language'):
            if prospect.language.lower() in [lang.lower() for lang in icp.technographics['language']]:
                reasons.append(f"Primary language ({prospect.language}) matches ICP requirements")

        # Company size inference
        if prospect.followers and icp.firmographics.get('size'):
            follower_indicators = {
                'startup': prospect.followers < 50,
                'small': prospect.followers < 200,
                'medium': 200 <= prospect.followers < 1000,
                'large': prospect.followers >= 1000
            }

            for size_category, matches in follower_indicators.items():
                if matches and size_category in icp.firmographics['size'].lower():
                    reasons.append(f"Follower count suggests {size_category} company size match")

        # Repository topics
        if prospect.topics and icp.technographics.get('frameworks'):
            matching_topics = set(prospect.topics) & set(icp.technographics['frameworks'])
            if matching_topics:
                reasons.append(f"Repository topics ({', '.join(matching_topics)}) align with ICP technologies")

        # Overall similarity
        if similarity > 0.8:
            reasons.append("High semantic similarity between prospect profile and ICP characteristics")
        elif similarity > 0.7:
            reasons.append("Good semantic similarity between prospect profile and ICP characteristics")

        if not reasons:
            reasons.append("Semantic similarity analysis indicates potential ICP alignment")

        return "; ".join(reasons)

    def _calculate_confidence_score(self, similarity: float) -> str:
        """Calculate confidence level for the match"""

        if similarity >= 0.85:
            return "high"
        elif similarity >= 0.75:
            return "medium"
        elif similarity >= 0.7:
            return "low"
        else:
            return "very_low"

    def _generate_recommended_actions(self, prospect: ProspectData, icp: ICPProfile) -> List[str]:
        """Generate recommended actions for this ICP-prospect match"""

        actions = []

        # Basic outreach
        actions.append("Send personalized outreach email")

        # ICP-specific actions
        if icp.technographics.get('language'):
            actions.append(f"Reference {prospect.language} expertise in communication")

        if prospect.repo_full_name:
            actions.append("Reference specific repository work")

        if prospect.contributions_last_year and prospect.contributions_last_year > 50:
            actions.append("Highlight high contribution activity")

        if icp.firmographics.get('size'):
            actions.append(f"Tailor messaging for {icp.firmographics['size']} company profile")

        return actions
