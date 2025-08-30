#!/usr/bin/env python3
"""
ICP Wizard CLI - Command Line Interface for Interactive ICP Discovery
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional

# Add current directory and parent to Python path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from icp_wizard.core.icp_wizard import ICPWizard
from icp_wizard.core.memory_system import ConversationMemory
from icp_wizard.utils.logging_utils import setup_logging, get_logger

logger = get_logger(__name__)


def setup_environment():
    """Setup environment variables and dependencies"""
    # Load environment variables from .env if present
    env_path = Path(".env")
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
            logger.info("Loaded environment variables from .env")
        except ImportError:
            logger.warning("python-dotenv not installed, skipping .env loading")

    # Check for OpenAI API key
    if not os.environ.get('OPENAI_API_KEY'):
        print("❌ OPENAI_API_KEY environment variable is required")
        print("Please set it with: export OPENAI_API_KEY=your_key_here")
        print("Or create a .env file with: OPENAI_API_KEY=your_key_here")
        sys.exit(1)


def run_icp_wizard(
    api_key: Optional[str] = None,
    output_file: Optional[str] = None,
    user_identifier: Optional[str] = None,
    memory_dir: Optional[Path] = None,
    config_dir: Optional[Path] = None,
    verbose: bool = False
) -> Optional[dict]:
    """Run the enhanced interactive ICP wizard with memory"""
    try:
        # Setup logging
        log_level = "DEBUG" if verbose else "INFO"
        setup_logging(log_level)

        logger.info("Initializing ICP wizard with memory system...")

        # Setup environment
        setup_environment()

        # Create and run enhanced wizard
        wizard = ICPWizard(
            api_key=api_key,
            user_identifier=user_identifier,
            memory_dir=memory_dir,
            config_dir=config_dir
        )

        # Show memory insights for returning users
        memory_insights = wizard.get_memory_insights()
        if memory_insights["conversation_count"] > 0:
            print(f"\n📊 Welcome back! You've had {memory_insights['conversation_count']} previous conversations")
            print(f"   Success rate: {memory_insights['success_rate']:.1%}")

            if memory_insights["preferred_icps"]:
                print(f"   Your preferred ICPs: {', '.join(memory_insights['preferred_icps'])}")

            if memory_insights["common_industries"]:
                print(f"   Common industries: {', '.join(memory_insights['common_industries'])}")

            print("   I'll use this context to provide more personalized recommendations!\n")

        result = wizard.run_wizard()

        if result:
            config = result

            print("\n" + "="*60)
            print("✅ ICP Configuration Generated Successfully!")
            print("="*60)
            print(f"🎯 Selected ICP: {config.icp_name}")
            print(f"📊 ICP ID: {config.icp_id}")
            print(f"🔧 Generated at: {config.generated_at}")
            print()

            # Show memory learning insights
            if memory_insights["conversation_count"] > 0:
                print("🧠 Memory System Update:")
                print("   ✅ Your preferences have been saved for future conversations")
                print("   📈 Success rate will improve with more interactions")
                print()

            # Export configuration
            if output_file:
                output_path = Path(output_file)
            else:
                output_path = Path("lead_intelligence/data/icp_wizard_config.json")

            success = wizard.export_configuration(config, output_path)

            if success:
                print(f"💾 Configuration saved to: {output_path}")

                # Display key configuration details
                if config.technographics:
                    tech_languages = config.technographics.get('language', [])
                    if tech_languages:
                        print(f"💻 Tech Stack: {', '.join(tech_languages)}")

                if config.triggers:
                    print(f"🎯 Key Triggers: {len(config.triggers)} defined")

                print("\n🚀 Ready to run intelligence pipeline with this ICP!")
                print(f"   python run_intelligence.py --icp-config {output_path}")
            else:
                print("❌ Failed to save configuration file")

            # Show next steps
            print("\n💡 Next time you run the wizard, I'll remember your preferences!")
            print("   Run 'make wizard' again to see personalized recommendations.")

            return config.to_dict()
        else:
            print("\n❌ ICP wizard did not complete successfully")
            print("💡 Your conversation preferences are still saved for next time!")
            return None

    except KeyboardInterrupt:
        print("\n👋 ICP wizard interrupted by user")
        return None
    except Exception as e:
        logger.error(f"Error running ICP wizard: {e}")
        print(f"\n❌ Error: {e}")
        return None


def list_available_icps(config_dir: Optional[Path] = None, verbose: bool = False):
    """List all available ICPs"""
    try:
        setup_logging("DEBUG" if verbose else "INFO")

        # Setup environment (for potential future features)
        setup_environment()

        print("Loading ICP configurations...\n")

        # Load ICP options directly without requiring OpenAI key
        config_dir = config_dir or Path("configs/icp")
        options_file = config_dir / "options.yaml"

        if not options_file.exists():
            print("❌ ICP configuration file not found")
            print(f"   Expected location: {options_file}")
            print("   Make sure the configs/icp/options.yaml file exists")
            return

        try:
            import yaml
        except ImportError:
            print("❌ PyYAML is required to load ICP configurations")
            print("   Install with: pip install PyYAML")
            return

        with open(options_file, 'r') as f:
            config = yaml.safe_load(f) or {}

        icps = config.get('icp_options', [])

        if not icps:
            print("❌ No ICP options available")
            print("   Check your configs/icp/options.yaml file")
            return

        print(f"Found {len(icps)} ICP options:")
        print("=" * 80)

        for i, icp in enumerate(icps, 1):
            print(f"{i:2d}. {icp['id']}")
            print(f"    📝 {icp['name']}")

            if 'technographics' in icp and 'language' in icp['technographics']:
                tech = icp['technographics']['language']
                if isinstance(tech, list):
                    print(f"    💻 Tech: {', '.join(tech)}")
                else:
                    print(f"    💻 Tech: {tech}")

            if 'firmographics' in icp:
                firmo = icp['firmographics']
                if 'size' in firmo:
                    print(f"    🏢 Size: {firmo['size']}")
                if 'geo' in firmo:
                    geo = firmo['geo']
                    if isinstance(geo, list):
                        print(f"    🌍 Geo: {', '.join(geo)}")
                    else:
                        print(f"    🌍 Geo: {geo}")

            if 'triggers' in icp:
                triggers = icp['triggers']
                if triggers:
                    print(f"    🎯 Triggers: {len(triggers)} defined")

            print()

        print("=" * 80)
        print("💡 Use 'icp-wizard show <icp_id>' to see detailed information")

    except Exception as e:
        logger.error(f"Error listing ICPs: {e}")
        print(f"❌ Error: {e}")


def show_icp_details(icp_id: str, config_dir: Optional[Path] = None, verbose: bool = False):
    """Show detailed information about a specific ICP"""
    try:
        setup_logging("DEBUG" if verbose else "INFO")

        # Setup environment
        setup_environment()

        # Load ICP options
        config_dir = config_dir or Path("configs/icp")
        options_file = config_dir / "options.yaml"

        if not options_file.exists():
            print("❌ ICP configuration file not found")
            return

        try:
            import yaml
        except ImportError:
            print("❌ PyYAML is required to load ICP configurations")
            return

        with open(options_file, 'r') as f:
            config = yaml.safe_load(f) or {}

        icps = config.get('icp_options', [])
        icp = next((icp for icp in icps if icp['id'] == icp_id), None)

        if not icp:
            print(f"❌ ICP '{icp_id}' not found")
            print("Available ICPs:")
            for available_icp in icps:
                print(f"  - {available_icp['id']}: {available_icp['name']}")
            return

        print(f"🎯 ICP Details: {icp['name']}")
        print(f"ID: {icp['id']}")
        print()

        if 'description' in icp:
            print(f"📝 Description: {icp['description']}")
            print()

        if 'technographics' in icp:
            print("💻 TECHNOGRAPHICS:")
            tech = icp['technographics']
            for key, value in tech.items():
                if isinstance(value, list):
                    print(f"  • {key}: {', '.join(value)}")
                else:
                    print(f"  • {key}: {value}")
            print()

        if 'firmographics' in icp:
            print("🏢 FIRMOGRAPHICS:")
            firmo = icp['firmographics']
            for key, value in firmo.items():
                if isinstance(value, list):
                    print(f"  • {key}: {', '.join(value)}")
                else:
                    print(f"  • {key}: {value}")
            print()

        if 'personas' in icp:
            print("👥 PERSONAS:")
            personas = icp['personas']
            for persona in personas:
                for key, value in persona.items():
                    if isinstance(value, list):
                        print(f"  • {key}: {', '.join(value)}")
                    else:
                        print(f"  • {key}: {value}")
            print()

        if 'triggers' in icp:
            print("🎯 TRIGGERS:")
            for trigger in icp['triggers']:
                print(f"  • {trigger}")
            print()

        if 'disqualifiers' in icp:
            print("❌ DISQUALIFIERS:")
            for disqualifier in icp['disqualifiers']:
                print(f"  • {disqualifier}")
            print()

        if 'github' in icp and 'repo_queries' in icp['github']:
            print("🔍 GITHUB QUERIES:")
            for query in icp['github']['repo_queries']:
                print(f"  • {query}")
            print()

    except Exception as e:
        logger.error(f"Error showing ICP details: {e}")
        print(f"❌ Error: {e}")


def show_memory_stats(
    user_identifier: Optional[str] = None,
    memory_dir: Optional[Path] = None,
    verbose: bool = False
):
    """Show memory and conversation statistics"""
    try:
        setup_logging("DEBUG" if verbose else "INFO")

        # Setup environment
        setup_environment()

        print("🧠 Memory System Statistics")
        print("=" * 50)

        # Initialize memory system
        memory_system = ConversationMemory(memory_dir)

        # Create wizard instance to access memory
        wizard = ICPWizard(user_identifier=user_identifier, memory_dir=memory_dir)

        memory_insights = wizard.get_memory_insights()
        global_stats = memory_system.get_memory_stats()

        print(f"\n📊 User Memory Overview:")
        print(f"User ID: {wizard.user_identifier}")
        print(f"Total Conversations: {memory_insights['conversation_count']}")
        print(f"Successful ICPs Created: {len(memory_insights.get('preferred_icps', []))}")
        print(f"Success Rate: {memory_insights['success_rate']:.1%}")

        if memory_insights['preferred_icps']:
            print(f"\n🎯 Preferred ICP Types:")
            for icp in memory_insights['preferred_icps']:
                print(f"   • {icp}")

        if memory_insights['common_industries']:
            print(f"\n🏭 Common Industries:")
            for industry in memory_insights['common_industries']:
                print(f"   • {industry}")

        if memory_insights['technical_preferences']:
            print(f"\n💻 Technical Preferences:")
            for tech in memory_insights['technical_preferences']:
                print(f"   • {tech}")

        print(f"\n📊 Global Memory Statistics:")
        print(f"Total Users: {global_stats['total_users']}")
        print(f"Total Conversations: {global_stats['total_conversations']}")

        if global_stats['popular_icps']:
            print(f"\n🔥 Popular ICPs:")
            for icp_id, count in global_stats['popular_icps'].items():
                print(f"   • {icp_id}: {count} times")

        # Show memory file location
        memory_dir_path = memory_dir or Path("lead_intelligence/data/conversation_memory")
        memory_file = memory_dir_path / f"{wizard.user_identifier}_memory.json"
        if memory_file.exists():
            print(f"\n💾 Memory File: {memory_file}")

        print("\n💡 The memory system learns from your conversations to provide")
        print("   more personalized ICP recommendations over time!")

    except Exception as e:
        logger.error(f"Error showing memory stats: {e}")
        print(f"❌ Error: {e}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Interactive ICP Wizard - Discover your ideal customer profile',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start interactive ICP wizard
  python icp_wizard/cli.py

  # List all available ICPs
  python icp_wizard/cli.py --list

  # Show details for specific ICP
  python icp_wizard/cli.py --show icp01_pypi_maintainers

  # Run wizard with custom output file
  python icp_wizard/cli.py --output my_icp_config.json

  # Show memory statistics
  python icp_wizard/cli.py --memory-stats

  # Custom configuration directory
  python icp_wizard/cli.py --config-dir /path/to/configs

  # Verbose logging
  python icp_wizard/cli.py --verbose
        """
    )

    # Main commands
    parser.add_argument('--list', '-l', action='store_true',
                       help='List all available ICPs')
    parser.add_argument('--show', '-s',
                       help='Show detailed information about a specific ICP')
    parser.add_argument('--memory-stats', action='store_true',
                       help='Show memory and conversation statistics')

    # Configuration options
    parser.add_argument('--output', '-o',
                       help='Output file for ICP configuration (default: lead_intelligence/data/icp_wizard_config.json)')
    parser.add_argument('--config-dir',
                       help='Directory containing ICP configuration files (default: configs/icp)')
    parser.add_argument('--memory-dir',
                       help='Directory for conversation memory files')
    parser.add_argument('--api-key', '-k',
                       help='OpenAI API key (can also be set via OPENAI_API_KEY env var)')
    parser.add_argument('--user-id', '-u',
                       help='User identifier for memory system (auto-generated if not provided)')

    # Debugging options
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode with detailed logging')

    args = parser.parse_args()

    # Handle different modes
    if args.list:
        list_available_icps(
            config_dir=Path(args.config_dir) if args.config_dir else None,
            verbose=args.verbose or args.debug
        )
    elif args.show:
        show_icp_details(
            args.show,
            config_dir=Path(args.config_dir) if args.config_dir else None,
            verbose=args.verbose or args.debug
        )
    elif args.memory_stats:
        show_memory_stats(
            user_identifier=args.user_id,
            memory_dir=Path(args.memory_dir) if args.memory_dir else None,
            verbose=args.verbose or args.debug
        )
    else:
        # Run interactive wizard
        config = run_icp_wizard(
            api_key=args.api_key,
            output_file=args.output,
            user_identifier=args.user_id,
            memory_dir=Path(args.memory_dir) if args.memory_dir else None,
            config_dir=Path(args.config_dir) if args.config_dir else None,
            verbose=args.verbose or args.debug
        )

        if config:
            # Optionally integrate with intelligence system
            print("\n🔄 Would you like to run the intelligence pipeline with this ICP?")
            response = input("Run pipeline now? (y/N): ").strip().lower()
            if response in ['y', 'yes']:
                print("🚀 Starting intelligence pipeline...")
                # This would integrate with the existing intelligence system
                print("Integration with intelligence pipeline would go here")
        else:
            print("\n❌ ICP wizard did not complete successfully")


if __name__ == "__main__":
    main()
