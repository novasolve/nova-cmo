#!/usr/bin/env python3
"""
ICP Wizard CLI - Command Line Interface for Interactive ICP Discovery
"""

import os
import sys
import argparse
import json
from pathlib import Path
from typing import Optional

# Add current directory and lead_intelligence to Python path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "lead_intelligence"))

from icp_wizard import ICPWizard
from lead_intelligence.core.beautiful_logger import beautiful_logger, log_header, log_separator


def setup_environment():
    """Setup environment variables and dependencies"""
    # Load environment variables
    env_path = Path(".env")
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)

    # Check for OpenAI API key
    if not os.environ.get('OPENAI_API_KEY'):
        print("❌ OPENAI_API_KEY environment variable is required")
        print("Please set it with: export OPENAI_API_KEY=your_key_here")
        sys.exit(1)


def run_icp_wizard(api_key: Optional[str] = None, output_file: Optional[str] = None, user_identifier: Optional[str] = None) -> Optional[dict]:
    """Run the enhanced interactive ICP wizard with memory"""
    try:
        log_header("🎯 Enhanced Interactive ICP Wizard")
        beautiful_logger.logger.info("Initializing ICP wizard with memory system...")

        # Setup environment
        setup_environment()

        # Create and run enhanced wizard
        wizard = ICPWizard(api_key=api_key, user_identifier=user_identifier)

        # Show memory insights for returning users
        memory_insights = wizard.get_memory_insights()
        if memory_insights["total_conversations"] > 0:
            print(f"\n📊 Welcome back! You've had {memory_insights['total_conversations']} previous conversations")
            print(f"   Success rate: {memory_insights['success_rate']:.1%}")

            if memory_insights["preferred_icp_types"]:
                print(f"   Your preferred ICPs: {', '.join(memory_insights['preferred_icp_types'])}")

            if memory_insights["common_industries"]:
                print(f"   Common industries: {', '.join(memory_insights['common_industries'])}")

            print("   I'll use this context to provide more personalized recommendations!\n")

        result = wizard.run_wizard()

        if result and result.get('final_icp_config'):
            config = result['final_icp_config']

            print("\n" + "="*60)
            print("✅ ICP Configuration Generated Successfully!")
            print("="*60)
            print(f"🎯 Selected ICP: {config['icp_name']}")
            print(f"📊 ICP ID: {config['icp_id']}")
            print(f"🔧 Generated at: {config['generated_at']}")
            print()

            # Show memory learning insights
            if memory_insights["total_conversations"] > 0:
                print("🧠 Memory System Update:")
                print("   ✅ Your preferences have been saved for future conversations")
                print("   📈 Success rate will improve with more interactions")
                print()

            # Save configuration
            if output_file:
                output_path = Path(output_file)
            else:
                output_path = Path("lead_intelligence/data/icp_wizard_config.json")

            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump(config, f, indent=2)

            print(f"💾 Configuration saved to: {output_path}")

            # Display key configuration details
            if config.get('technographics'):
                print(f"💻 Tech Stack: {', '.join(config['technographics'].get('language', []))}")

            if config.get('triggers'):
                print(f"🎯 Key Triggers: {len(config['triggers'])} defined")

            print("\n🚀 Ready to run intelligence pipeline with this ICP!")
            print(f"   make intelligence ICP_CONFIG={output_path}")

            # Show next steps
            print("\n💡 Next time you run the wizard, I'll remember your preferences!")
            print("   Run 'make wizard' again to see personalized recommendations.")

            return config
        else:
            print("\n❌ ICP wizard did not complete successfully")
            print("💡 Your conversation preferences are still saved for next time!")
            return None

    except KeyboardInterrupt:
        print("\n👋 ICP wizard interrupted by user")
        return None
    except Exception as e:
        beautiful_logger.logger.error(f"Error running ICP wizard: {e}")
        print(f"\n❌ Error: {e}")
        return None


def list_available_icps():
    """List all available ICPs"""
    try:
        log_header("🎯 Available ICP Options")
        print("Loading ICP configurations...\n")

        # Load ICP options directly without requiring OpenAI key
        from pathlib import Path
        import yaml

        icp_config_path = Path(__file__).parent / ".." / "configs" / "icp" / "options.yaml"
        if not icp_config_path.exists():
            # Try relative path from project root
            icp_config_path = Path("configs/icp/options.yaml")

        if not icp_config_path.exists():
            print("❌ ICP configuration file not found")
            return

        with open(icp_config_path, 'r') as f:
            config = yaml.safe_load(f) or {}

        icps = config.get('icp_options', [])

        if not icps:
            print("❌ No ICP options available")
            return

        print(f"Found {len(icps)} ICP options:")
        print("=" * 80)

        for i, icp in enumerate(icps, 1):
            print(f"{i:2d}. {icp['id']}")
            print(f"    📝 {icp['name']}")

            if 'technographics' in icp and 'language' in icp['technographics']:
                tech = icp['technographics']['language']
                print(f"    💻 Tech: {', '.join(tech)}")

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

    except Exception as e:
        beautiful_logger.logger.error(f"Error listing ICPs: {e}")
        print(f"❌ Error: {e}")


def show_icp_details(icp_id: str):
    """Show detailed information about a specific ICP"""
    try:
        # Load ICP options directly without requiring OpenAI key
        from pathlib import Path
        import yaml

        icp_config_path = Path(__file__).parent / ".." / "configs" / "icp" / "options.yaml"
        if not icp_config_path.exists():
            # Try relative path from project root
            icp_config_path = Path("configs/icp/options.yaml")

        if not icp_config_path.exists():
            print("❌ ICP configuration file not found")
            return

        with open(icp_config_path, 'r') as f:
            config = yaml.safe_load(f) or {}

        icps = config.get('icp_options', [])
        icp = next((icp for icp in icps if icp['id'] == icp_id), None)

        if not icp:
            print(f"❌ ICP '{icp_id}' not found")
            return

        log_header(f"🎯 ICP Details: {icp['name']}")
        print(f"ID: {icp['id']}")
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
        beautiful_logger.logger.error(f"Error showing ICP details: {e}")
        print(f"❌ Error: {e}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Interactive ICP Wizard - Discover your ideal customer profile',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start interactive ICP wizard
  python icp_wizard_cli.py

  # List all available ICPs
  python icp_wizard_cli.py --list

  # Show details for specific ICP
  python icp_wizard_cli.py --details icp01_pypi_maintainers

  # Run wizard with custom output file
  python icp_wizard_cli.py --output my_icp_config.json

  # Use custom OpenAI API key
  python icp_wizard_cli.py --api-key your_openai_key
        """
    )

    parser.add_argument('--list', '-l', action='store_true',
                       help='List all available ICPs')
    parser.add_argument('--details', '-d',
                       help='Show detailed information about a specific ICP')
    parser.add_argument('--output', '-o',
                       help='Output file for ICP configuration (default: lead_intelligence/data/icp_wizard_config.json)')
    parser.add_argument('--api-key', '-k',
                       help='OpenAI API key (can also be set via OPENAI_API_KEY env var)')
    parser.add_argument('--user-id', '-u',
                       help='User identifier for memory system (auto-generated if not provided)')
    parser.add_argument('--memory-stats', action='store_true',
                       help='Show memory and conversation statistics')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    else:
        import logging
        logging.basicConfig(level=logging.INFO)

    # Handle different modes
    if args.list:
        list_available_icps()
    elif args.details:
        show_icp_details(args.details)
    elif args.memory_stats:
        show_memory_stats(args.user_id)
    else:
        # Run interactive wizard
        config = run_icp_wizard(
            api_key=args.api_key,
            output_file=args.output,
            user_identifier=args.user_id
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


def show_memory_stats(user_identifier: Optional[str] = None):
    """Show memory and conversation statistics"""
    try:
        log_header("🧠 Memory System Statistics")

        # Setup environment to access memory system
        setup_environment()

        # Create wizard instance to access memory
        wizard = ICPWizard(user_identifier=user_identifier)

        memory_insights = wizard.get_memory_insights()

        print("\n📊 Conversation Memory Overview:")
        print("=" * 50)
        print(f"User ID: {wizard.user_identifier}")
        print(f"Total Conversations: {memory_insights['total_conversations']}")
        print(f"Successful ICPs Created: {memory_insights['successful_icps']}")
        print(f"Success Rate: {memory_insights['success_rate']:.1%}")

        if memory_insights['preferred_icp_types']:
            print(f"\n🎯 Preferred ICP Types:")
            for icp in memory_insights['preferred_icp_types']:
                print(f"   • {icp}")

        if memory_insights['common_industries']:
            print(f"\n🏭 Common Industries:")
            for industry in memory_insights['common_industries']:
                print(f"   • {industry}")

        if memory_insights['technical_preferences']:
            print(f"\n💻 Technical Preferences:")
            for tech in memory_insights['technical_preferences']:
                print(f"   • {tech}")

        # Show memory file location
        memory_dir = Path("lead_intelligence/data/conversation_memory")
        memory_file = memory_dir / f"{wizard.user_identifier}_memory.pkl"
        if memory_file.exists():
            print(f"\n💾 Memory File: {memory_file}")
            import time
            print(f"📅 Last Modified: {time.ctime(memory_file.stat().st_mtime)}")

        print("\n💡 The memory system learns from your conversations to provide")
        print("   more personalized ICP recommendations over time!")

    except Exception as e:
        beautiful_logger.logger.error(f"Error showing memory stats: {e}")
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
