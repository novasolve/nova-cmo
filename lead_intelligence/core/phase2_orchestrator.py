#!/usr/bin/env python3
"""
Phase 2 Orchestrator
Coordinates the entire Phase 2 validation and quality assurance pipeline
"""

import os
import json
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

from .data_validator import DataValidator
from .identity_deduper import IdentityDeduper
from .compliance_checker import ComplianceChecker
from .icp_filter import ICPRelevanceFilter
from .activity_filter import ActivityThresholdFilter
from .data_normalizer import DataNormalizer, NormalizationResult
from .quality_gate import QualityGate, QualityGateResult

logger = logging.getLogger(__name__)


@dataclass
class Phase2Config:
    """Configuration for Phase 2 pipeline"""
    # Data validation settings
    validation_enabled: bool = True
    strict_validation: bool = True

    # Deduplication settings
    deduplication_enabled: bool = True
    deduplication_method: str = "identity_keys"  # identity_keys, email, or name_company

    # Compliance settings
    compliance_enabled: bool = True
    block_high_risk: bool = True

    # ICP filtering settings
    icp_filtering_enabled: bool = True
    icp_config: Dict[str, Any] = field(default_factory=dict)

    # Activity filtering settings
    activity_filtering_enabled: bool = True
    activity_config: Dict[str, Any] = field(default_factory=dict)

    # Data normalization settings
    normalization_enabled: bool = True
    normalization_config: Dict[str, Any] = field(default_factory=dict)

    # Quality gates settings
    quality_gates_enabled: bool = True
    quality_config: Dict[str, Any] = field(default_factory=dict)

    # Processing settings
    max_workers: int = 4
    batch_size: int = 100
    enable_parallel: bool = True

    # Output settings
    save_intermediate_results: bool = True
    output_format: str = "jsonl"  # jsonl or json


@dataclass
class Phase2Result:
    """Results from Phase 2 processing"""
    success: bool
    qualified_prospects: List[Dict[str, Any]]
    rejected_prospects: List[Dict[str, Any]]
    stats: Dict[str, Any]
    processing_time: float
    errors: List[str]
    warnings: List[str]

    # Pipeline metadata
    pipeline_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineStepResult:
    """Result from a single pipeline step"""
    step_name: str
    success: bool
    input_count: int
    output_count: int
    rejected_count: int
    processing_time: float
    errors: List[str]
    data: List[Dict[str, Any]]


class Phase2Orchestrator:
    """Orchestrates the complete Phase 2 validation pipeline"""

    def __init__(self, config: Phase2Config):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize all components
        self._init_components()

    def _init_components(self):
        """Initialize all Phase 2 pipeline components"""
        # Data validation
        self.data_validator = DataValidator({
            'strict_mode': self.config.strict_validation
        })

        # Deduplication
        self.identity_deduper = IdentityDeduper()

        # Compliance checking
        self.compliance_checker = ComplianceChecker(self.config.icp_config)

        # ICP filtering
        self.icp_filter = ICPRelevanceFilter(self.config.icp_config)

        # Activity filtering
        self.activity_filter = ActivityThresholdFilter(self.config.activity_config)

        # Data normalization
        self.data_normalizer = DataNormalizer(self.config.normalization_config)

        # Quality gates
        self.quality_gate = QualityGate(self.config.quality_config)

    async def process_phase2_async(self, raw_prospects: List[Dict[str, Any]]) -> Phase2Result:
        """Process prospects through Phase 2 pipeline asynchronously"""
        start_time = time.time()

        try:
            # Initialize pipeline results
            current_prospects = raw_prospects.copy()
            pipeline_steps = []
            all_warnings = []
            all_errors = []

            # Step 1: Initial data validation
            if self.config.validation_enabled:
                step_result = await self._run_validation_step(current_prospects)
                pipeline_steps.append(step_result)
                current_prospects = step_result.data
                all_errors.extend(step_result.errors)

            # Step 2: Deduplication
            if self.config.deduplication_enabled:
                step_result = await self._run_deduplication_step(current_prospects)
                pipeline_steps.append(step_result)
                current_prospects = step_result.data
                all_errors.extend(step_result.errors)

            # Step 3: Compliance filtering
            if self.config.compliance_enabled:
                step_result = await self._run_compliance_step(current_prospects)
                pipeline_steps.append(step_result)
                current_prospects = step_result.data
                all_errors.extend(step_result.errors)

            # Step 4: ICP relevance filtering
            if self.config.icp_filtering_enabled:
                step_result = await self._run_icp_filtering_step(current_prospects)
                pipeline_steps.append(step_result)
                current_prospects = step_result.data
                all_errors.extend(step_result.errors)

            # Step 5: Activity threshold filtering
            if self.config.activity_filtering_enabled:
                step_result = await self._run_activity_filtering_step(current_prospects)
                pipeline_steps.append(step_result)
                current_prospects = step_result.data
                all_errors.extend(step_result.errors)

            # Step 6: Data normalization
            if self.config.normalization_enabled:
                step_result = await self._run_normalization_step(current_prospects)
                pipeline_steps.append(step_result)
                current_prospects = step_result.data
                all_errors.extend(step_result.errors)

            # Step 7: Quality gate validation
            if self.config.quality_gates_enabled:
                step_result = await self._run_quality_gate_step(current_prospects)
                pipeline_steps.append(step_result)
                qualified_prospects = step_result.data
                rejected_prospects = []  # Quality gates don't reject, they just score

                # Separate qualified and rejected based on quality gate results
                qualified_prospects = []
                rejected_prospects = []

                for prospect in current_prospects:
                    gate_result = self.quality_gate.validate_prospect(prospect)
                    if gate_result.passes_all_gates:
                        qualified_prospects.append(prospect)
                    else:
                        rejected_prospects.append({
                            'prospect': prospect,
                            'rejection_reasons': gate_result.failure_reasons,
                            'quality_score': gate_result.quality_score
                        })

                all_errors.extend(step_result.errors)

            processing_time = time.time() - start_time

            # Calculate final statistics
            stats = self._calculate_final_stats(raw_prospects, qualified_prospects,
                                              rejected_prospects, pipeline_steps)

            # Create pipeline metadata
            pipeline_metadata = {
                'config': self._config_to_dict(),
                'steps': [self._step_result_to_dict(step) for step in pipeline_steps],
                'processing_time': processing_time,
                'timestamp': datetime.now().isoformat(),
                'version': '2.0.0'
            }

            return Phase2Result(
                success=len(all_errors) == 0,
                qualified_prospects=qualified_prospects,
                rejected_prospects=rejected_prospects,
                stats=stats,
                processing_time=processing_time,
                errors=all_errors,
                warnings=all_warnings,
                pipeline_metadata=pipeline_metadata
            )

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Phase 2 processing failed: {e}")

            return Phase2Result(
                success=False,
                qualified_prospects=[],
                rejected_prospects=[],
                stats={},
                processing_time=processing_time,
                errors=[str(e)],
                warnings=[],
                pipeline_metadata={'error': str(e)}
            )

    def process_phase2_sync(self, raw_prospects: List[Dict[str, Any]]) -> Phase2Result:
        """Process prospects through Phase 2 pipeline synchronously"""
        # Create event loop for synchronous execution
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, we need to handle this differently
                return self._process_sync_without_loop(raw_prospects)
            else:
                return loop.run_until_complete(self.process_phase2_async(raw_prospects))
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.process_phase2_async(raw_prospects))

    def _process_sync_without_loop(self, raw_prospects: List[Dict[str, Any]]) -> Phase2Result:
        """Process synchronously without async event loop"""
        start_time = time.time()

        try:
            # Initialize pipeline results
            current_prospects = raw_prospects.copy()
            pipeline_steps = []
            all_warnings = []
            all_errors = []

            # Step 1: Initial data validation
            if self.config.validation_enabled:
                step_result = self._run_validation_step_sync(current_prospects)
                pipeline_steps.append(step_result)
                current_prospects = step_result.data
                all_errors.extend(step_result.errors)

            # Step 2: Deduplication
            if self.config.deduplication_enabled:
                step_result = self._run_deduplication_step_sync(current_prospects)
                pipeline_steps.append(step_result)
                current_prospects = step_result.data
                all_errors.extend(step_result.errors)

            # Step 3: Compliance filtering
            if self.config.compliance_enabled:
                step_result = self._run_compliance_step_sync(current_prospects)
                pipeline_steps.append(step_result)
                current_prospects = step_result.data
                all_errors.extend(step_result.errors)

            # Step 4: ICP relevance filtering
            if self.config.icp_filtering_enabled:
                step_result = self._run_icp_filtering_step_sync(current_prospects)
                pipeline_steps.append(step_result)
                current_prospects = step_result.data
                all_errors.extend(step_result.errors)

            # Step 5: Activity threshold filtering
            if self.config.activity_filtering_enabled:
                step_result = self._run_activity_filtering_step_sync(current_prospects)
                pipeline_steps.append(step_result)
                current_prospects = step_result.data
                all_errors.extend(step_result.errors)

            # Step 6: Data normalization
            if self.config.normalization_enabled:
                step_result = self._run_normalization_step_sync(current_prospects)
                pipeline_steps.append(step_result)
                current_prospects = step_result.data
                all_errors.extend(step_result.errors)

            # Step 7: Quality gate validation
            if self.config.quality_gates_enabled:
                step_result = self._run_quality_gate_step_sync(current_prospects)
                pipeline_steps.append(step_result)
                qualified_prospects = step_result.data
                all_errors.extend(step_result.errors)

                # Separate qualified and rejected based on quality gate results
                qualified_prospects = []
                rejected_prospects = []

                for prospect in current_prospects:
                    gate_result = self.quality_gate.validate_prospect(prospect)
                    if gate_result.passes_all_gates:
                        qualified_prospects.append(prospect)
                    else:
                        rejected_prospects.append({
                            'prospect': prospect,
                            'rejection_reasons': gate_result.failure_reasons,
                            'quality_score': gate_result.quality_score
                        })

            processing_time = time.time() - start_time

            # Calculate final statistics
            stats = self._calculate_final_stats(raw_prospects, qualified_prospects,
                                              rejected_prospects, pipeline_steps)

            # Create pipeline metadata
            pipeline_metadata = {
                'config': self._config_to_dict(),
                'steps': [self._step_result_to_dict(step) for step in pipeline_steps],
                'processing_time': processing_time,
                'timestamp': datetime.now().isoformat(),
                'version': '2.0.0'
            }

            return Phase2Result(
                success=len(all_errors) == 0,
                qualified_prospects=qualified_prospects,
                rejected_prospects=rejected_prospects,
                stats=stats,
                processing_time=processing_time,
                errors=all_errors,
                warnings=all_warnings,
                pipeline_metadata=pipeline_metadata
            )

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Phase 2 processing failed: {e}")

            return Phase2Result(
                success=False,
                qualified_prospects=[],
                rejected_prospects=[],
                stats={},
                processing_time=processing_time,
                errors=[str(e)],
                warnings=[],
                pipeline_metadata={'error': str(e)}
            )

    async def _run_validation_step(self, prospects: List[Dict[str, Any]]) -> PipelineStepResult:
        """Run data validation step"""
        start_time = time.time()
        errors = []

        try:
            if self.config.enable_parallel and len(prospects) > self.config.batch_size:
                validated_prospects = await self._run_parallel_validation(prospects)
            else:
                validated_prospects = []
                for prospect in prospects:
                    is_valid, error_list, quality_score = self.data_validator.validate_lead(prospect)
                    if is_valid:
                        validated_prospects.append(prospect)
                    else:
                        errors.extend(error_list)

            processing_time = time.time() - start_time

            return PipelineStepResult(
                step_name="data_validation",
                success=True,
                input_count=len(prospects),
                output_count=len(validated_prospects),
                rejected_count=len(prospects) - len(validated_prospects),
                processing_time=processing_time,
                errors=errors,
                data=validated_prospects
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return PipelineStepResult(
                step_name="data_validation",
                success=False,
                input_count=len(prospects),
                output_count=0,
                rejected_count=len(prospects),
                processing_time=processing_time,
                errors=[str(e)],
                data=[]
            )

    def _run_validation_step_sync(self, prospects: List[Dict[str, Any]]) -> PipelineStepResult:
        """Run data validation step synchronously"""
        start_time = time.time()
        errors = []

        try:
            validated_prospects = []
            for prospect in prospects:
                is_valid, error_list, quality_score = self.data_validator.validate_lead(prospect)
                if is_valid:
                    validated_prospects.append(prospect)
                else:
                    errors.extend(error_list)

            processing_time = time.time() - start_time

            return PipelineStepResult(
                step_name="data_validation",
                success=True,
                input_count=len(prospects),
                output_count=len(validated_prospects),
                rejected_count=len(prospects) - len(validated_prospects),
                processing_time=processing_time,
                errors=errors,
                data=validated_prospects
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return PipelineStepResult(
                step_name="data_validation",
                success=False,
                input_count=len(prospects),
                output_count=0,
                rejected_count=len(prospects),
                processing_time=processing_time,
                errors=[str(e)],
                data=[]
            )

    async def _run_parallel_validation(self, prospects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run validation in parallel batches"""
        validated_prospects = []

        # Split into batches
        batches = [prospects[i:i + self.config.batch_size]
                  for i in range(0, len(prospects), self.config.batch_size)]

        async def validate_batch(batch):
            batch_results = []
            for prospect in batch:
                is_valid, _, _ = self.data_validator.validate_lead(prospect)
                if is_valid:
                    batch_results.append(prospect)
            return batch_results

        # Process batches concurrently
        tasks = [validate_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks)

        # Flatten results
        for batch_result in batch_results:
            validated_prospects.extend(batch_result)

        return validated_prospects

    async def _run_deduplication_step(self, prospects: List[Dict[str, Any]]) -> PipelineStepResult:
        """Run deduplication step"""
        start_time = time.time()

        try:
            deduped_prospects = self.identity_deduper.deduplicate_prospects(prospects)

            processing_time = time.time() - start_time

            return PipelineStepResult(
                step_name="deduplication",
                success=True,
                input_count=len(prospects),
                output_count=len(deduped_prospects),
                rejected_count=len(prospects) - len(deduped_prospects),
                processing_time=processing_time,
                errors=[],
                data=deduped_prospects
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return PipelineStepResult(
                step_name="deduplication",
                success=False,
                input_count=len(prospects),
                output_count=0,
                rejected_count=len(prospects),
                processing_time=processing_time,
                errors=[str(e)],
                data=[]
            )

    def _run_deduplication_step_sync(self, prospects: List[Dict[str, Any]]) -> PipelineStepResult:
        """Run deduplication step synchronously"""
        start_time = time.time()

        try:
            deduped_prospects = self.identity_deduper.deduplicate_prospects(prospects)

            processing_time = time.time() - start_time

            return PipelineStepResult(
                step_name="deduplication",
                success=True,
                input_count=len(prospects),
                output_count=len(deduped_prospects),
                rejected_count=len(prospects) - len(deduped_prospects),
                processing_time=processing_time,
                errors=[],
                data=deduped_prospects
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return PipelineStepResult(
                step_name="deduplication",
                success=False,
                input_count=len(prospects),
                output_count=0,
                rejected_count=len(prospects),
                processing_time=processing_time,
                errors=[str(e)],
                data=[]
            )

    async def _run_compliance_step(self, prospects: List[Dict[str, Any]]) -> PipelineStepResult:
        """Run compliance filtering step"""
        start_time = time.time()
        errors = []

        try:
            compliant_prospects = []
            rejected_count = 0

            for prospect in prospects:
                compliance_result = self.compliance_checker.check_compliance(prospect)

                if self.config.block_high_risk and compliance_result.risk_level == 'block':
                    rejected_count += 1
                elif compliance_result.compliant:
                    compliant_prospects.append(prospect)
                else:
                    rejected_count += 1

            processing_time = time.time() - start_time

            return PipelineStepResult(
                step_name="compliance",
                success=True,
                input_count=len(prospects),
                output_count=len(compliant_prospects),
                rejected_count=rejected_count,
                processing_time=processing_time,
                errors=errors,
                data=compliant_prospects
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return PipelineStepResult(
                step_name="compliance",
                success=False,
                input_count=len(prospects),
                output_count=0,
                rejected_count=len(prospects),
                processing_time=processing_time,
                errors=[str(e)],
                data=[]
            )

    def _run_compliance_step_sync(self, prospects: List[Dict[str, Any]]) -> PipelineStepResult:
        """Run compliance filtering step synchronously"""
        start_time = time.time()
        errors = []

        try:
            compliant_prospects = []
            rejected_count = 0

            for prospect in prospects:
                compliance_result = self.compliance_checker.check_compliance(prospect)

                if self.config.block_high_risk and compliance_result.risk_level == 'block':
                    rejected_count += 1
                elif compliance_result.compliant:
                    compliant_prospects.append(prospect)
                else:
                    rejected_count += 1

            processing_time = time.time() - start_time

            return PipelineStepResult(
                step_name="compliance",
                success=True,
                input_count=len(prospects),
                output_count=len(compliant_prospects),
                rejected_count=rejected_count,
                processing_time=processing_time,
                errors=errors,
                data=compliant_prospects
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return PipelineStepResult(
                step_name="compliance",
                success=False,
                input_count=len(prospects),
                output_count=0,
                rejected_count=len(prospects),
                processing_time=processing_time,
                errors=[str(e)],
                data=[]
            )

    async def _run_icp_filtering_step(self, prospects: List[Dict[str, Any]]) -> PipelineStepResult:
        """Run ICP relevance filtering step"""
        start_time = time.time()
        errors = []

        try:
            relevant_prospects, rejected_prospects = self.icp_filter.filter_prospects(prospects)

            processing_time = time.time() - start_time

            return PipelineStepResult(
                step_name="icp_filtering",
                success=True,
                input_count=len(prospects),
                output_count=len(relevant_prospects),
                rejected_count=len(rejected_prospects),
                processing_time=processing_time,
                errors=errors,
                data=relevant_prospects
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return PipelineStepResult(
                step_name="icp_filtering",
                success=False,
                input_count=len(prospects),
                output_count=0,
                rejected_count=len(prospects),
                processing_time=processing_time,
                errors=[str(e)],
                data=[]
            )

    def _run_icp_filtering_step_sync(self, prospects: List[Dict[str, Any]]) -> PipelineStepResult:
        """Run ICP relevance filtering step synchronously"""
        start_time = time.time()
        errors = []

        try:
            relevant_prospects, rejected_prospects = self.icp_filter.filter_prospects(prospects)

            processing_time = time.time() - start_time

            return PipelineStepResult(
                step_name="icp_filtering",
                success=True,
                input_count=len(prospects),
                output_count=len(relevant_prospects),
                rejected_count=len(rejected_prospects),
                processing_time=processing_time,
                errors=errors,
                data=relevant_prospects
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return PipelineStepResult(
                step_name="icp_filtering",
                success=False,
                input_count=len(prospects),
                output_count=0,
                rejected_count=len(prospects),
                processing_time=processing_time,
                errors=[str(e)],
                data=[]
            )

    async def _run_activity_filtering_step(self, prospects: List[Dict[str, Any]]) -> PipelineStepResult:
        """Run activity threshold filtering step"""
        start_time = time.time()
        errors = []

        try:
            active_prospects, rejected_prospects = self.activity_filter.filter_prospects(prospects)

            processing_time = time.time() - start_time

            return PipelineStepResult(
                step_name="activity_filtering",
                success=True,
                input_count=len(prospects),
                output_count=len(active_prospects),
                rejected_count=len(rejected_prospects),
                processing_time=processing_time,
                errors=errors,
                data=active_prospects
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return PipelineStepResult(
                step_name="activity_filtering",
                success=False,
                input_count=len(prospects),
                output_count=0,
                rejected_count=len(prospects),
                processing_time=processing_time,
                errors=[str(e)],
                data=[]
            )

    def _run_activity_filtering_step_sync(self, prospects: List[Dict[str, Any]]) -> PipelineStepResult:
        """Run activity threshold filtering step synchronously"""
        start_time = time.time()
        errors = []

        try:
            active_prospects, rejected_prospects = self.activity_filter.filter_prospects(prospects)

            processing_time = time.time() - start_time

            return PipelineStepResult(
                step_name="activity_filtering",
                success=True,
                input_count=len(prospects),
                output_count=len(active_prospects),
                rejected_count=len(rejected_prospects),
                processing_time=processing_time,
                errors=errors,
                data=active_prospects
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return PipelineStepResult(
                step_name="activity_filtering",
                success=False,
                input_count=len(prospects),
                output_count=0,
                rejected_count=len(prospects),
                processing_time=processing_time,
                errors=[str(e)],
                data=[]
            )

    async def _run_normalization_step(self, prospects: List[Dict[str, Any]]) -> PipelineStepResult:
        """Run data normalization step"""
        start_time = time.time()
        errors = []

        try:
            normalization_results = self.data_normalizer.normalize_batch(prospects)
            normalized_prospects = [result.normalized_prospect for result in normalization_results]

            # Collect any normalization warnings/errors
            for result in normalization_results:
                if result.normalization_warnings:
                    errors.extend(result.normalization_warnings)

            processing_time = time.time() - start_time

            return PipelineStepResult(
                step_name="normalization",
                success=True,
                input_count=len(prospects),
                output_count=len(normalized_prospects),
                rejected_count=0,  # Normalization doesn't reject, it fixes
                processing_time=processing_time,
                errors=errors,
                data=normalized_prospects
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return PipelineStepResult(
                step_name="normalization",
                success=False,
                input_count=len(prospects),
                output_count=0,
                rejected_count=len(prospects),
                processing_time=processing_time,
                errors=[str(e)],
                data=[]
            )

    def _run_normalization_step_sync(self, prospects: List[Dict[str, Any]]) -> PipelineStepResult:
        """Run data normalization step synchronously"""
        start_time = time.time()
        errors = []

        try:
            normalization_results = self.data_normalizer.normalize_batch(prospects)
            normalized_prospects = [result.normalized_prospect for result in normalization_results]

            # Collect any normalization warnings/errors
            for result in normalization_results:
                if result.normalization_warnings:
                    errors.extend(result.normalization_warnings)

            processing_time = time.time() - start_time

            return PipelineStepResult(
                step_name="normalization",
                success=True,
                input_count=len(prospects),
                output_count=len(normalized_prospects),
                rejected_count=0,  # Normalization doesn't reject, it fixes
                processing_time=processing_time,
                errors=errors,
                data=normalized_prospects
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return PipelineStepResult(
                step_name="normalization",
                success=False,
                input_count=len(prospects),
                output_count=0,
                rejected_count=len(prospects),
                processing_time=processing_time,
                errors=[str(e)],
                data=[]
            )

    async def _run_quality_gate_step(self, prospects: List[Dict[str, Any]]) -> PipelineStepResult:
        """Run quality gate validation step"""
        start_time = time.time()
        errors = []

        try:
            gate_results = self.quality_gate.validate_batch(prospects)

            # Quality gates don't reject prospects, they just validate them
            # The actual filtering happens in the main processing logic
            processing_time = time.time() - start_time

            return PipelineStepResult(
                step_name="quality_gates",
                success=True,
                input_count=len(prospects),
                output_count=len(prospects),  # All prospects pass through
                rejected_count=0,
                processing_time=processing_time,
                errors=errors,
                data=prospects  # Return original prospects with quality scores added
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return PipelineStepResult(
                step_name="quality_gates",
                success=False,
                input_count=len(prospects),
                output_count=0,
                rejected_count=len(prospects),
                processing_time=processing_time,
                errors=[str(e)],
                data=[]
            )

    def _run_quality_gate_step_sync(self, prospects: List[Dict[str, Any]]) -> PipelineStepResult:
        """Run quality gate validation step synchronously"""
        start_time = time.time()
        errors = []

        try:
            gate_results = self.quality_gate.validate_batch(prospects)

            # Quality gates don't reject prospects, they just validate them
            # The actual filtering happens in the main processing logic
            processing_time = time.time() - start_time

            return PipelineStepResult(
                step_name="quality_gates",
                success=True,
                input_count=len(prospects),
                output_count=len(prospects),  # All prospects pass through
                rejected_count=0,
                processing_time=processing_time,
                errors=errors,
                data=prospects  # Return original prospects with quality scores added
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return PipelineStepResult(
                step_name="quality_gates",
                success=False,
                input_count=len(prospects),
                output_count=0,
                rejected_count=len(prospects),
                processing_time=processing_time,
                errors=[str(e)],
                data=[]
            )

    def _calculate_final_stats(self, raw_prospects: List[Dict[str, Any]],
                             qualified_prospects: List[Dict[str, Any]],
                             rejected_prospects: List[Dict[str, Any]],
                             pipeline_steps: List[PipelineStepResult]) -> Dict[str, Any]:
        """Calculate final statistics for the Phase 2 pipeline"""

        stats = {
            'input_prospects': len(raw_prospects),
            'qualified_prospects': len(qualified_prospects),
            'rejected_prospects': len(rejected_prospects),
            'qualification_rate': len(qualified_prospects) / len(raw_prospects) if raw_prospects else 0,
            'rejection_rate': len(rejected_prospects) / len(raw_prospects) if raw_prospects else 0,
            'pipeline_steps': len(pipeline_steps),
            'step_stats': {}
        }

        # Add step-by-step statistics
        for step in pipeline_steps:
            stats['step_stats'][step.step_name] = {
                'input_count': step.input_count,
                'output_count': step.output_count,
                'rejected_count': step.rejected_count,
                'processing_time': step.processing_time,
                'success': step.success,
                'error_count': len(step.errors)
            }

        # Calculate overall processing efficiency
        total_processing_time = sum(step.processing_time for step in pipeline_steps)
        stats['total_processing_time'] = total_processing_time
        stats['avg_processing_time_per_prospect'] = total_processing_time / len(raw_prospects) if raw_prospects else 0

        return stats

    def _config_to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization"""
        return {
            'validation_enabled': self.config.validation_enabled,
            'deduplication_enabled': self.config.deduplication_enabled,
            'compliance_enabled': self.config.compliance_enabled,
            'icp_filtering_enabled': self.config.icp_filtering_enabled,
            'activity_filtering_enabled': self.config.activity_filtering_enabled,
            'normalization_enabled': self.config.normalization_enabled,
            'quality_gates_enabled': self.config.quality_gates_enabled,
            'max_workers': self.config.max_workers,
            'batch_size': self.config.batch_size,
            'enable_parallel': self.config.enable_parallel
        }

    def _step_result_to_dict(self, step: PipelineStepResult) -> Dict[str, Any]:
        """Convert step result to dictionary for serialization"""
        return {
            'step_name': step.step_name,
            'success': step.success,
            'input_count': step.input_count,
            'output_count': step.output_count,
            'rejected_count': step.rejected_count,
            'processing_time': step.processing_time,
            'error_count': len(step.errors)
        }
