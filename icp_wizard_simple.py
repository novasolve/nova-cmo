#!/usr/bin/env python3
"""
Simplified Conversational ICP Wizard
A direct, natural conversation-based ICP discovery system
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add parent directories to Python path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "lead_intelligence"))

from lead_intelligence.core.beautiful_logger import beautiful_logger, log_header


class SimpleConversationMemory:
    """Simplified conversation memory for the basic ICP wizard"""

    def __init__(self, memory_dir: Optional[Path] = None):
        self.memory_dir = memory_dir or Path("lead_intelligence/data/conversation_memory")
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def load_user_memory(self, user_identifier: str) -> Dict[str, Any]:
        """Load user's basic memory"""
        memory_file = self.memory_dir / f"{user_identifier}_simple_memory.json"

        if memory_file.exists():
            try:
                with open(memory_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass

        return {
            "conversation_count": 0,
            "successful_icps": [],
            "preferred_icp_types": [],
            "common_industries": [],
            "technical_preferences": []
        }

    def save_user_memory(self, user_identifier: str, memory: Dict[str, Any]):
        """Save user's basic memory"""
        memory_file = self.memory_dir / f"{user_identifier}_simple_memory.json"

        try:
            with open(memory_file, 'w') as f:
                json.dump(memory, f, indent=2)
        except Exception as e:
            beautiful_logger.logger.error(f"Could not save memory: {e}")

    def update_memory(self, user_identifier: str, conversation_data: Dict[str, Any]):
        """Update user's memory with conversation insights"""
        memory = self.load_user_memory(user_identifier)

        memory["conversation_count"] += 1

        if conversation_data.get("final_icp_config"):
            icp_config = conversation_data["final_icp_config"]
            icp_id = icp_config.get("icp_id", "")
            if icp_id not in memory["successful_icps"]:
                memory["successful_icps"].append(icp_id)

        # Extract preferences from conversation
        messages = conversation_data.get("messages", [])
        conversation_text = " ".join([msg.get("content", "") for msg in messages if msg.get("role") == "user"])

        # Simple preference extraction
        text_lower = conversation_text.lower()
        if "python" in text_lower and "python" not in memory["technical_preferences"]:
            memory["technical_preferences"].append("python")
        if any(word in text_lower for word in ["saas", "startup"]) and "saas" not in memory["common_industries"]:
            memory["common_industries"].append("saas")
        if any(word in text_lower for word in ["machine learning", "ml", "ai"]) and "ai" not in memory["technical_preferences"]:
            memory["technical_preferences"].append("ai")

        self.save_user_memory(user_identifier, memory)
        return memory

    def get_memory_insights(self, user_identifier: str) -> Dict[str, Any]:
        """Get basic memory insights"""
        memory = self.load_user_memory(user_identifier)
        return {
            "total_conversations": memory.get("conversation_count", 0),
            "successful_icps": len(memory.get("successful_icps", [])),
            "preferred_icp_types": memory.get("preferred_icp_types", []),
            "common_industries": memory.get("common_industries", []),
            "technical_preferences": memory.get("technical_preferences", []),
            "success_rate": len(memory.get("successful_icps", [])) / max(memory.get("conversation_count", 1), 1)
        }


class SimpleICPWizard:
    """Simplified conversational ICP wizard without complex graph dependencies"""

    def __init__(self, api_key: Optional[str] = None, user_identifier: Optional[str] = None):
        """Initialize the simplified ICP wizard"""
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable.")

        # User identification for memory system
        self.user_identifier = user_identifier or self._generate_user_id()

        # Initialize simplified memory system
        self.memory_system = SimpleConversationMemory()

        # Load user's memory and preferences
        self.user_memory = self.memory_system.load_user_memory(self.user_identifier)

        # Load ICP options
        self.icp_options = self._load_icp_options()

        # Initialize conversation state
        self.conversation_history = []
        self.conversation_turns = 0

    def _generate_user_id(self) -> str:
        """Generate a unique user identifier"""
        import socket
        import getpass
        import hashlib

        system_info = f"{socket.gethostname()}_{getpass.getuser()}_{datetime.now().strftime('%Y%m%d')}"
        return hashlib.md5(system_info.encode()).hexdigest()[:8]

    def _load_icp_options(self) -> List[Dict[str, Any]]:
        """Load available ICP options from config"""
        icp_config_path = Path(__file__).parent / "configs" / "icp" / "options.yaml"
        try:
            import yaml
            with open(icp_config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
                return config.get('icp_options', [])
        except Exception as e:
            beautiful_logger.logger.warning(f"Could not load ICP config: {e}")
            return []

    async def start_conversation(self) -> Dict[str, Any]:
        """Start the conversational ICP discovery"""
        log_header("🎯 Simple Conversational ICP Wizard")
        print("\n🤖 Welcome to the ICP Wizard!")
        print("=" * 40)
        print("Let's discover your ideal customer profile through conversation.")
        print("Type 'quit' or 'exit' at any time to end.\n")

        # Initialize conversation state
        conversation_state = {
            "messages": [],
            "user_profile": self.user_memory,
            "current_icp": None,
            "final_icp_config": None,
            "conversation_stage": "starting"
        }

        # Start with greeting
        greeting_response = await self._generate_greeting()
        print(f"🤖 {greeting_response}")

        # Main conversation loop
        max_turns = 8  # Allow up to 8 exchanges
        icp_selected = False

        while self.conversation_turns < max_turns and not icp_selected:
            # Get user input
            user_input = input("\n👤 You: ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye! Your preferences have been saved for next time.")
                break

            # Record user input
            self.conversation_turns += 1
            conversation_state["messages"].append({
                "role": "user",
                "content": user_input,
                "turn": self.conversation_turns,
                "timestamp": datetime.now().isoformat()
            })

            # Generate response
            response, should_end = await self._generate_response(user_input, conversation_state)

            print(f"\n🤖 {response}")

            if should_end:
                # Attempt ICP selection
                selected_icp = self._select_icp_from_conversation(conversation_state)
                if selected_icp:
                    icp_selected = True
                    conversation_state["current_icp"] = selected_icp
                    conversation_state["final_icp_config"] = self._generate_icp_config(selected_icp)
                    conversation_state["conversation_stage"] = "completed"

                    # Show final configuration
                    self._display_icp_configuration(selected_icp, conversation_state["final_icp_config"])
                else:
                    # Continue conversation
                    follow_up = "I'd like to learn a bit more to make the best ICP recommendation. Could you tell me about the industry or technologies your customers use?"
                    print(f"\n🤖 {follow_up}")

        # Save conversation to memory
        self._save_conversation_to_memory(conversation_state)

        return conversation_state

    async def _generate_greeting(self) -> str:
        """Generate personalized greeting"""
        user_profile = self.user_memory

        if user_profile.get("conversation_count", 0) > 0:
            success_rate = user_profile.get("successful_icps", [])
            success_count = len(success_rate)

            greeting = f"""Welcome back! I see you've had {user_profile['conversation_count']} conversations with me before.

Based on your history, you often work with:
• Preferred ICPs: {', '.join(user_profile.get('preferred_icp_types', [])[:2]) or 'Various'}
• Industries: {', '.join(user_profile.get('common_industries', [])[:2]) or 'Various'}
• Technologies: {', '.join(user_profile.get('technical_preferences', [])[:2]) or 'Mixed'}

What type of customers are you looking for this time? Feel free to describe them in your own words!"""
        else:
            greeting = """Hi there! I'm here to help you discover your ideal customer profile (ICP) through a natural conversation.

An ICP helps you identify the types of customers most likely to buy from you, so you can focus your marketing efforts effectively.

To get started, could you tell me a bit about the customers you're targeting? For example:
• What industry are they in?
• What size companies are you looking for?
• What technologies or tools do they use?
• Any other characteristics you have in mind?

Just describe them naturally - I'll help refine this into an effective ICP!"""

        return greeting

    async def _generate_response(self, user_input: str, conversation_state: Dict[str, Any]) -> tuple[str, bool]:
        """Generate conversational response"""
        messages = conversation_state.get("messages", [])
        user_profile = conversation_state.get("user_profile", {})

        # Simple keyword analysis
        input_lower = user_input.lower()

        # Check if user seems ready to proceed
        ready_phrases = ['yes', 'sure', 'go ahead', 'proceed', 'ready', 'let\'s do it', 'sounds good']
        if any(phrase in input_lower for phrase in ready_phrases):
            return "Great! Let me analyze what you've told me and suggest the most appropriate ICP for your needs.", True

        # Check for specific ICP indicators
        icp_indicators = {
            'python': ['python', 'django', 'flask', 'fastapi', 'pytest'],
            'ml_ai': ['machine learning', 'ml', 'ai', 'tensorflow', 'pytorch', 'data science'],
            'saas': ['saas', 'startup', 'seed', 'series a', 'cloud service'],
            'api': ['api', 'sdk', 'integration', 'client library'],
            'academic': ['university', 'research', 'academic', 'lab', 'professor'],
            'fintech': ['fintech', 'financial', 'banking', 'payment', 'regulatory'],
            'agency': ['agency', 'consulting', 'client work', 'consultant'],
            'testing': ['testing', 'pytest', 'ci', 'github actions', 'test automation']
        }

        detected_categories = []
        for category, keywords in icp_indicators.items():
            if any(keyword in input_lower for keyword in keywords):
                detected_categories.append(category)

        # Generate contextual response
        if detected_categories:
            response = f"Thanks for sharing that! I hear you're interested in customers who work with {', '.join(detected_categories)}."

            if len(detected_categories) >= 2:
                response += " This gives me a great foundation for recommending an ICP."
                return response, True
            else:
                response += " Could you tell me a bit more about their company size or industry to help me make the best recommendation?"
                return response, False
        else:
            # Ask clarifying questions
            if 'industry' not in input_lower and 'company' not in input_lower:
                response = "That's helpful! Could you tell me a bit about what industry these customers are in, or what size companies you're targeting?"
            elif 'technology' not in input_lower and 'tech' not in input_lower:
                response = "Great! And what technologies or tools do these customers typically use?"
            else:
                response = "Perfect! I think I have enough information to suggest an appropriate ICP for you."
                return response, True

            return response, False

    def _select_icp_from_conversation(self, conversation_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select most appropriate ICP based on conversation"""
        messages = conversation_state.get("messages", [])
        conversation_text = " ".join([msg.get("content", "") for msg in messages if msg.get("role") == "user"])
        conversation_lower = conversation_text.lower()

        # ICP matching logic
        icp_scores = {}

        # PyPI Maintainers ICP
        if any(word in conversation_lower for word in ['python', 'django', 'flask', 'fastapi', 'pytest', 'library', 'package']):
            icp_scores['icp01_pypi_maintainers'] = 8

        # ML/Data Science ICP
        if any(word in conversation_lower for word in ['machine learning', 'ml', 'ai', 'tensorflow', 'pytorch', 'data science', 'neural network']):
            icp_scores['icp02_ml_ds_maintainers'] = 9

        # SaaS ICP
        if any(word in conversation_lower for word in ['saas', 'startup', 'seed', 'series a', 'cloud', 'web app', 'platform']):
            icp_scores['icp03_seed_series_a_python_saas'] = 7

        # API/SDK ICP
        if any(word in conversation_lower for word in ['api', 'sdk', 'integration', 'client', 'rest', 'graphql']):
            icp_scores['icp04_api_sdk_tooling'] = 6

        # Academic ICP
        if any(word in conversation_lower for word in ['university', 'research', 'academic', 'lab', 'professor', 'student']):
            icp_scores['icp05_academic_labs'] = 5

        # Fintech ICP
        if any(word in conversation_lower for word in ['fintech', 'financial', 'banking', 'payment', 'regulatory', 'compliance']):
            icp_scores['icp07_regulated_startups'] = 7

        # Agency ICP
        if any(word in conversation_lower for word in ['agency', 'consulting', 'client', 'freelance', 'outsourcing']):
            icp_scores['icp08_agencies_consultancies'] = 4

        # Testing ICP
        if any(word in conversation_lower for word in ['testing', 'pytest', 'ci', 'github actions', 'test automation']):
            icp_scores['icp09_pytest_ci_plugin_authors'] = 6

        # Select highest scoring ICP
        if icp_scores:
            best_icp_id = max(icp_scores, key=icp_scores.get)
            selected_icp = next((icp for icp in self.icp_options if icp['id'] == best_icp_id), None)
            return selected_icp

        return None

    def _generate_icp_config(self, icp: Dict[str, Any]) -> Dict[str, Any]:
        """Generate ICP configuration"""
        return {
            "icp_id": icp['id'],
            "icp_name": icp['name'],
            "technographics": icp.get('technographics', {}),
            "firmographics": icp.get('firmographics', {}),
            "personas": icp.get('personas', []),
            "triggers": icp.get('triggers', []),
            "disqualifiers": icp.get('disqualifiers', []),
            "github_queries": icp.get('github', {}).get('repo_queries', []),
            "generated_at": datetime.now().isoformat(),
            "source": "conversational_wizard"
        }

    def _display_icp_configuration(self, icp: Dict[str, Any], config: Dict[str, Any]):
        """Display the selected ICP configuration"""
        print("\n" + "="*60)
        print("✅ ICP Configuration Generated Successfully!")
        print("="*60)
        print(f"🎯 Selected ICP: {icp['name']}")
        print(f"📊 ICP ID: {icp['id']}")
        print(f"🔧 Generated at: {config['generated_at']}")
        print()

        if config.get('technographics'):
            tech = config['technographics']
            if tech.get('language'):
                print(f"💻 Technology: {', '.join(tech['language'])}")

        if config.get('firmographics'):
            firmo = config['firmographics']
            if firmo.get('size'):
                print(f"🏢 Company Size: {firmo['size']}")

        if config.get('triggers'):
            print(f"🎯 Key Triggers: {len(config['triggers'])} defined")

        print("\n🚀 Ready to run intelligence pipeline with this ICP!")
        print(f"   python run_intelligence.py --icp-config /path/to/config.json")

    def _save_conversation_to_memory(self, conversation_state: Dict[str, Any]):
        """Save conversation results to memory"""
        try:
            updated_memory = self.memory_system.update_memory(
                self.user_identifier,
                {
                    "messages": conversation_state.get("messages", []),
                    "final_icp_config": conversation_state.get("final_icp_config"),
                    "conversation_stage": conversation_state.get("conversation_stage"),
                    "success_score": 1.0 if conversation_state.get("final_icp_config") else 0.0,
                    "conversation_duration": None,
                    "stage_transitions": []
                }
            )

            beautiful_logger.logger.info(f"Conversation saved to memory for user {self.user_identifier}")

        except Exception as e:
            beautiful_logger.logger.error(f"Error saving conversation to memory: {e}")

    def run_wizard(self) -> Optional[Dict[str, Any]]:
        """Run the simplified ICP wizard synchronously"""
        try:
            return asyncio.run(self.start_conversation())
        except KeyboardInterrupt:
            print("\n👋 Conversation interrupted.")
            return None
        except Exception as e:
            beautiful_logger.logger.error(f"Error running ICP wizard: {e}")
            print(f"\n❌ Error: {e}")
            return None


def main():
    """Main entry point"""
    try:
        wizard = SimpleICPWizard()
        result = wizard.run_wizard()

        if result and result.get('final_icp_config'):
            print("\n✅ Conversation completed successfully!")
            return 0
        else:
            print("\n❌ Conversation did not complete")
            return 1

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    main()
