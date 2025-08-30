#!/usr/bin/env python3
"""
Phase 2 Runner Script
Command-line interface for Phase 2 Data Validation & Quality Assurance
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio

# Add lead_intelligence to path
sys.path.insert(0, str(Path(__file__).parent))

from lead_intelligence.core.phase2_orchestrator import Phase2Orchestrator, Phase2Config
from lead_intelligence.core.beautiful_logger import beautiful_logger, log_header, log_separator


def setup_logging(verbose: bool = False, log_file: Optional[str] = None):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def load_config_from_file(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file"""
    try:
        import yaml
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not load config from {config_path}: {e}")
        return {}


def create_phase2_config(args) -> Phase2Config:
    """Create Phase2Config from command line arguments"""

    # Load base config if provided
    base_config = {}
    if hasattr(args, 'config') and args.config:
        base_config = load_config_from_file(args.config)

    # Override with command line arguments
    icp_config = base_config.get('icp', {})
    activity_config = base_config.get('activity', {})
    normalization_config = base_config.get('normalization', {})
    quality_config = base_config.get('quality', {})

    # Override ICP config
    if hasattr(args, 'icp_relevance_threshold'):
        icp_config['relevance_threshold'] = args.icp_relevance_threshold
    if hasattr(args, 'icp_company_sizes'):
        icp_config['company_sizes'] = args.icp_company_sizes.split(',')
    if hasattr(args, 'icp_tech_stacks'):
        icp_config['tech_stacks'] = args.icp_tech_stacks.split(',')
    if hasattr(args, 'icp_preferred_locations'):
        icp_config['preferred_locations'] = args.icp_preferred_locations.split(',')

    # Override activity config
    if hasattr(args, 'activity_days_threshold'):
        activity_config['activity_days_threshold'] = args.activity_days_threshold
    if hasattr(args, 'activity_score_threshold'):
        activity_config['min_activity_score'] = args.activity_score_threshold
    if hasattr(args, 'require_maintainer_status'):
        activity_config['require_maintainer_status'] = args.require_maintainer_status

    # Override quality config
    if hasattr(args, 'quality_completeness_threshold'):
        quality_config['data_completeness_threshold'] = args.quality_completeness_threshold
    if hasattr(args, 'quality_accuracy_threshold'):
        quality_config['data_accuracy_threshold'] = args.quality_accuracy_threshold
    if hasattr(args, 'quality_consistency_threshold'):
        quality_config['data_consistency_threshold'] = args.quality_consistency_threshold
    if hasattr(args, 'blocked_email_domains'):
        quality_config['blocked_email_domains'] = args.blocked_email_domains.split(',')

    return Phase2Config(
        validation_enabled=not getattr(args, 'skip_validation', False),
        deduplication_enabled=not getattr(args, 'skip_deduplication', False),
        compliance_enabled=not getattr(args, 'skip_compliance', False),
        icp_filtering_enabled=not getattr(args, 'skip_icp_filtering', False),
        activity_filtering_enabled=not getattr(args, 'skip_activity_filtering', False),
        normalization_enabled=not getattr(args, 'skip_normalization', False),
        quality_gates_enabled=not getattr(args, 'skip_quality_gates', False),

        icp_config=icp_config,
        activity_config=activity_config,
        normalization_config=normalization_config,
        quality_config=quality_config,

        max_workers=getattr(args, 'max_workers', 4),
        batch_size=getattr(args, 'batch_size', 100),
        enable_parallel=getattr(args, 'enable_parallel', True),

        save_intermediate_results=getattr(args, 'save_intermediate', True),
        output_format=getattr(args, 'output_format', 'jsonl')
    )


def load_prospects_from_file(input_path: str) -> List[Dict[str, Any]]:
    """Load prospects from input file"""
    logger = logging.getLogger(__name__)

    if not Path(input_path).exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    file_ext = Path(input_path).suffix.lower()

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            if file_ext == '.jsonl':
                # JSONL format (one JSON object per line)
                prospects = []
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            prospect = json.loads(line)
                            prospects.append(prospect)
                        except json.JSONDecodeError as e:
                            logger.warning(f"Skipping invalid JSON at line {line_num}: {e}")
                return prospects

            elif file_ext == '.json':
                # JSON format (array of objects)
                data = json.load(f)
                if isinstance(data, list):
                    return data
                else:
                    return [data]

            else:
                raise ValueError(f"Unsupported file format: {file_ext}")

    except Exception as e:
        raise RuntimeError(f"Failed to load prospects from {input_path}: {e}")


def save_results(results: Dict[str, Any], output_dir: str, output_format: str = 'jsonl'):
    """Save Phase 2 results to files"""
    logger = logging.getLogger(__name__)

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save qualified prospects
    qualified_file = output_path / f"phase2_qualified_prospects_{timestamp}.{output_format}"
    save_prospects(results['qualified_prospects'], qualified_file, output_format)

    # Save rejected prospects
    rejected_file = output_path / f"phase2_rejected_prospects_{timestamp}.json"
    with open(rejected_file, 'w', encoding='utf-8') as f:
        json.dump(results['rejected_prospects'], f, indent=2, ensure_ascii=False)

    # Save pipeline metadata
    metadata_file = output_path / f"phase2_metadata_{timestamp}.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(results['pipeline_metadata'], f, indent=2, default=str)

    # Save summary stats
    stats_file = output_path / f"phase2_stats_{timestamp}.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(results['stats'], f, indent=2, default=str)

    logger.info("📁 Results saved:")
    logger.info(f"   • Qualified prospects: {qualified_file}")
    logger.info(f"   • Rejected prospects: {rejected_file}")
    logger.info(f"   • Pipeline metadata: {metadata_file}")
    logger.info(f"   • Statistics: {stats_file}")

    return {
        'qualified_file': str(qualified_file),
        'rejected_file': str(rejected_file),
        'metadata_file': str(metadata_file),
        'stats_file': str(stats_file)
    }


def save_prospects(prospects: List[Dict[str, Any]], file_path: Path, format_type: str):
    """Save prospects to file in specified format"""
    if format_type == 'jsonl':
        with open(file_path, 'w', encoding='utf-8') as f:
            for prospect in prospects:
                f.write(json.dumps(prospect, ensure_ascii=False) + '\n')
    elif format_type == 'json':
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(prospects, f, indent=2, ensure_ascii=False)
    else:
        raise ValueError(f"Unsupported output format: {format_type}")


def generate_report(results: Dict[str, Any]) -> str:
    """Generate a human-readable report"""
    stats = results['stats']
    metadata = results['pipeline_metadata']

    report_lines = []
    report_lines.append("# Phase 2 Processing Report")
    report_lines.append(f"Generated: {datetime.now().isoformat()}")
    report_lines.append("")

    # Summary
    report_lines.append("## Summary")
    report_lines.append(f"- **Input Prospects**: {stats['input_prospects']}")
    report_lines.append(f"- **Qualified Prospects**: {stats['qualified_prospects']}")
    report_lines.append(f"- **Rejected Prospects**: {stats['rejected_prospects']}")
    report_lines.append(".2%")
    report_lines.append(".2%")
    report_lines.append(f"- **Processing Time**: {stats['total_processing_time']:.2f} seconds")
    report_lines.append(".4f")
    report_lines.append("")

    # Pipeline steps
    report_lines.append("## Pipeline Steps")
    for step_name, step_stats in stats['step_stats'].items():
        success_indicator = "✅" if step_stats['success'] else "❌"
        report_lines.append(f"### {success_indicator} {step_name.replace('_', ' ').title()}")
        report_lines.append(f"- Input: {step_stats['input_count']}")
        report_lines.append(f"- Output: {step_stats['output_count']}")
        report_lines.append(f"- Rejected: {step_stats['rejected_count']}")
        report_lines.append(f"- Processing Time: {step_stats['processing_time']:.2f}s")
        if step_stats['error_count'] > 0:
            report_lines.append(f"- Errors: {step_stats['error_count']}")
        report_lines.append("")

    # Errors and warnings
    if results['errors']:
        report_lines.append("## Errors")
        for error in results['errors'][:10]:  # Show first 10 errors
            report_lines.append(f"- {error}")
        if len(results['errors']) > 10:
            report_lines.append(f"- ... and {len(results['errors']) - 10} more errors")
        report_lines.append("")

    if results['warnings']:
        report_lines.append("## Warnings")
        for warning in results['warnings'][:10]:  # Show first 10 warnings
            report_lines.append(f"- {warning}")
        if len(results['warnings']) > 10:
            report_lines.append(f"- ... and {len(results['warnings']) - 10} more warnings")
        report_lines.append("")

    return "\n".join(report_lines)


def print_summary(results: Dict[str, Any]):
    """Print a concise summary to console"""
    stats = results['stats']

    print("\n" + "="*60)
    print("🎯 PHASE 2 PROCESSING COMPLETE")
    print("="*60)

    print("📊 Summary:")
    print(f"   Input prospects:     {stats['input_prospects']}")
    print(f"   Qualified prospects: {stats['qualified_prospects']}")
    print(f"   Rejected prospects:  {stats['rejected_prospects']}")
    print(".2%")
    print(".2%")
    print(".2f")

    print("
⏱️  Performance:"    print(".2f")
    print(".4f")

    # Show top rejection reasons if any
    rejected = results['rejected_prospects']
    if rejected:
        print("
❌ Top Rejection Reasons:"        reason_counts = {}
        for rejection in rejected:
            reasons = rejection.get('rejection_reasons', [])
            for reason in reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

        sorted_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
        for reason, count in sorted_reasons[:5]:
            print(f"   • {reason}: {count}")

    print("\n✅ Success!" if results['success'] else "\n❌ Completed with errors!")
    print("="*60)


async def run_phase2_async(args):
    """Run Phase 2 processing asynchronously"""
    logger = logging.getLogger(__name__)

    try:
        # Load prospects
        log_separator("📥 Loading Prospects")
        logger.info(f"Loading prospects from: {args.input}")
        prospects = load_prospects_from_file(args.input)
        logger.info(f"Loaded {len(prospects)} prospects")

        # Create configuration
        log_separator("⚙️ Configuring Pipeline")
        config = create_phase2_config(args)
        logger.info("Phase 2 configuration created")

        # Create orchestrator
        log_separator("🚀 Initializing Phase 2 Orchestrator")
        orchestrator = Phase2Orchestrator(config)
        logger.info("Phase 2 orchestrator initialized")

        # Run pipeline
        log_separator("🔄 Running Phase 2 Pipeline")
        logger.info("Starting Phase 2 processing...")
        start_time = datetime.now()

        results = await orchestrator.process_phase2_async(prospects)

        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        logger.info(".2f")

        # Save results
        if not getattr(args, 'dry_run', False):
            log_separator("💾 Saving Results")
            saved_files = save_results(results.__dict__, args.output_dir, config.output_format)

            # Save report
            report = generate_report(results.__dict__)
            report_file = Path(args.output_dir) / f"phase2_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)

            logger.info(f"📄 Report saved: {report_file}")

        # Print summary
        print_summary(results.__dict__)

        return results.success

    except Exception as e:
        logger.error(f"❌ Phase 2 processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_phase2_sync(args):
    """Run Phase 2 processing synchronously"""
    logger = logging.getLogger(__name__)

    try:
        # Load prospects
        log_separator("📥 Loading Prospects")
        logger.info(f"Loading prospects from: {args.input}")
        prospects = load_prospects_from_file(args.input)
        logger.info(f"Loaded {len(prospects)} prospects")

        # Create configuration
        log_separator("⚙️ Configuring Pipeline")
        config = create_phase2_config(args)
        logger.info("Phase 2 configuration created")

        # Create orchestrator
        log_separator("🚀 Initializing Phase 2 Orchestrator")
        orchestrator = Phase2Orchestrator(config)
        logger.info("Phase 2 orchestrator initialized")

        # Run pipeline
        log_separator("🔄 Running Phase 2 Pipeline")
        logger.info("Starting Phase 2 processing...")
        start_time = datetime.now()

        results = orchestrator.process_phase2_sync(prospects)

        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        logger.info(".2f")

        # Save results
        if not getattr(args, 'dry_run', False):
            log_separator("💾 Saving Results")
            saved_files = save_results(results.__dict__, args.output_dir, config.output_format)

            # Save report
            report = generate_report(results.__dict__)
            report_file = Path(args.output_dir) / f"phase2_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)

            logger.info(f"📄 Report saved: {report_file}")

        # Print summary
        print_summary(results.__dict__)

        return results.success

    except Exception as e:
        logger.error(f"❌ Phase 2 processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description='Phase 2: Data Validation & Quality Assurance Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python run_phase2.py --input data/raw_prospects.jsonl --output-dir results/

  # With custom configuration
  python run_phase2.py --input data/prospects.json --config config/phase2.yaml --output-dir results/

  # Skip certain steps
  python run_phase2.py --input data/prospects.jsonl --skip-normalization --output-dir results/

  # Custom ICP settings
  python run_phase2.py --input data/prospects.jsonl \\
    --icp-company-sizes seed,series_a \\
    --icp-tech-stacks python_ml,web_dev \\
    --output-dir results/

  # Dry run (show what would be done)
  python run_phase2.py --input data/prospects.jsonl --dry-run
        """
    )

    # Required arguments
    parser.add_argument('--input', '-i', required=True,
                       help='Input file containing raw prospects (JSON/JSONL)')

    # Output options
    parser.add_argument('--output-dir', '-o', default='lead_intelligence/data/phase2_results',
                       help='Output directory for results (default: lead_intelligence/data/phase2_results)')
    parser.add_argument('--output-format', choices=['jsonl', 'json'], default='jsonl',
                       help='Output format for qualified prospects (default: jsonl)')

    # Configuration
    parser.add_argument('--config', '-c',
                       help='Configuration file (YAML) to override defaults')

    # Pipeline control
    parser.add_argument('--skip-validation', action='store_true',
                       help='Skip data validation step')
    parser.add_argument('--skip-deduplication', action='store_true',
                       help='Skip deduplication step')
    parser.add_argument('--skip-compliance', action='store_true',
                       help='Skip compliance filtering step')
    parser.add_argument('--skip-icp-filtering', action='store_true',
                       help='Skip ICP relevance filtering step')
    parser.add_argument('--skip-activity-filtering', action='store_true',
                       help='Skip activity threshold filtering step')
    parser.add_argument('--skip-normalization', action='store_true',
                       help='Skip data normalization step')
    parser.add_argument('--skip-quality-gates', action='store_true',
                       help='Skip quality gate validation step')

    # ICP filtering options
    parser.add_argument('--icp-relevance-threshold', type=float, default=0.6,
                       help='ICP relevance threshold (0.0-1.0, default: 0.6)')
    parser.add_argument('--icp-company-sizes', default='seed,series_a,series_b_plus',
                       help='Target company sizes (comma-separated)')
    parser.add_argument('--icp-tech-stacks', default='python_ml,web_dev,devops',
                       help='Target technology stacks (comma-separated)')
    parser.add_argument('--icp-preferred-locations', default='us,united kingdom,canada',
                       help='Preferred locations (comma-separated)')

    # Activity filtering options
    parser.add_argument('--activity-days-threshold', type=int, default=90,
                       help='Activity recency threshold in days (default: 90)')
    parser.add_argument('--activity-score-threshold', type=float, default=0.6,
                       help='Minimum activity score (0.0-1.0, default: 0.6)')
    parser.add_argument('--require-maintainer-status', action='store_true',
                       help='Require maintainer status for qualification')

    # Quality gate options
    parser.add_argument('--quality-completeness-threshold', type=float, default=0.8,
                       help='Data completeness threshold (0.0-1.0, default: 0.8)')
    parser.add_argument('--quality-accuracy-threshold', type=float, default=0.7,
                       help='Data accuracy threshold (0.0-1.0, default: 0.7)')
    parser.add_argument('--quality-consistency-threshold', type=float, default=0.9,
                       help='Data consistency threshold (0.0-1.0, default: 0.9)')
    parser.add_argument('--blocked-email-domains', default='',
                       help='Blocked email domains (comma-separated)')

    # Performance options
    parser.add_argument('--max-workers', type=int, default=4,
                       help='Maximum number of worker threads (default: 4)')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='Batch size for processing (default: 100)')
    parser.add_argument('--disable-parallel', action='store_true',
                       help='Disable parallel processing')

    # Other options
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--log-file',
                       help='Log file path (default: console only)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without actually processing')
    parser.add_argument('--async', action='store_true',
                       help='Use asynchronous processing (default: synchronous)')

    return parser


def main():
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose, log_file=getattr(args, 'log_file', None))

    # Create output directory
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    # Show header
    log_header("🚀 Phase 2: Data Validation & Quality Assurance")

    # Check if this is a dry run
    if getattr(args, 'dry_run', False):
        print("🔍 DRY RUN MODE")
        print("Configuration that would be used:")
        config = create_phase2_config(args)
        print(f"  Input: {args.input}")
        print(f"  Output: {args.output_dir}")
        print(f"  Format: {config.output_format}")
        print(f"  Workers: {config.max_workers}")
        print(f"  Parallel: {config.enable_parallel}")
        print("\nWould run Phase 2 pipeline with above configuration.")
        return 0

    # Run Phase 2
    try:
        if getattr(args, 'async', False):
            # Run asynchronously
            success = asyncio.run(run_phase2_async(args))
        else:
            # Run synchronously
            success = run_phase2_sync(args)

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())
