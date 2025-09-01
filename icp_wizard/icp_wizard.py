#!/usr/bin/env python3
"""
Interactive ICP Wizard with LangGraph Integration
Conversational interface for discovering and refining Ideal Customer Profiles
"""

import os
import sys
import json
import asyncio
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, TypedDict, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import pickle

# Add parent directories to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "lead_intelligence"))

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from lead_intelligence.core.beautiful_logger import beautiful_logger, log_header, log_separator


class ConversationMemory:
    """Advanced conversation memory system for ICP Wizard"""

    def __init__(self, memory_dir: Optional[Path] = None):
        self.memory_dir = memory_dir or Path("lead_intelligence/data/conversation_memory")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.user_memories = {}
        self.session_context = {}
        self.learning_patterns = defaultdict(lambda: defaultdict(int))

    def _get_user_hash(self, user_identifier: str) -> str:
        """Generate consistent hash for user identification"""
        return hashlib.md5(user_identifier.encode()).hexdigest()

    def load_user_memory(self, user_identifier: str) -> Dict[str, Any]:
        """Load user's conversation memory and preferences"""
        user_hash = self._get_user_hash(user_identifier)
        memory_file = self.memory_dir / f"{user_hash}_memory.pkl"

        if memory_file.exists():
            try:
                with open(memory_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                beautiful_logger.logger.warning(f"Could not load user memory: {e}")
                return self._create_default_memory()

        return self._create_default_memory()

    def save_user_memory(self, user_identifier: str, memory: Dict[str, Any]):
        """Save user's conversation memory and preferences"""
        user_hash = self._get_user_hash(user_identifier)
        memory_file = self.memory_dir / f"{user_hash}_memory.pkl"

        try:
            with open(memory_file, 'wb') as f:
                pickle.dump(memory, f)
        except Exception as e:
            beautiful_logger.logger.error(f"Could not save user memory: {e}")

    def _create_default_memory(self) -> Dict[str, Any]:
        """Create default memory structure for new users"""
        return {
            "conversation_count": 0,
            "successful_icps": [],
            "preferred_icp_types": [],
            "common_industries": [],
            "technical_preferences": [],
            "conversation_patterns": [],
            "last_conversation": None,
            "learning_data": {
                "preferred_stages": {},
                "successful_refinements": [],
                "rejected_suggestions": []
            }
        }

    def update_memory(self, user_identifier: str, conversation_data: Dict[str, Any]):
        """Update user's memory with new conversation insights"""
        memory = self.load_user_memory(user_identifier)

        # Update conversation count
        memory["conversation_count"] += 1

        # Store successful ICP creation
        if conversation_data.get("final_icp_config"):
            icp_config = conversation_data["final_icp_config"]
            memory["successful_icps"].append({
                "icp_id": icp_config.get("icp_id"),
                "timestamp": datetime.now().isoformat(),
                "success_score": conversation_data.get("success_score", 1.0)
            })

        # Update preferences based on conversation
        self._learn_from_conversation(memory, conversation_data)

        # Keep only recent successful ICPs (last 10)
        memory["successful_icps"] = memory["successful_icps"][-10:]

        self.save_user_memory(user_identifier, memory)
        return memory

    def _learn_from_conversation(self, memory: Dict[str, Any], conversation_data: Dict[str, Any]):
        """Learn patterns from successful conversations"""
        messages = conversation_data.get("messages", [])

        # Extract ICP preferences
        if conversation_data.get("final_icp_config"):
            icp_config = conversation_data["final_icp_config"]
            icp_id = icp_config.get("icp_id", "")

            # Add to preferred ICP types
            if icp_id not in memory["preferred_icp_types"]:
                memory["preferred_icp_types"].append(icp_id)

        # Extract industry preferences from conversation
        conversation_text = " ".join([msg.get("content", "") for msg in messages if msg.get("role") == "user"])
        industries = self._extract_industries(conversation_text)
        for industry in industries:
            if industry not in memory["common_industries"]:
                memory["common_industries"].append(industry)

        # Extract technical preferences
        tech_stack = self._extract_tech_preferences(conversation_text)
        for tech in tech_stack:
            if tech not in memory["technical_preferences"]:
                memory["technical_preferences"].append(tech)

    def _extract_industries(self, text: str) -> List[str]:
        """Extract industry mentions from conversation text"""
        industries = []
        industry_keywords = {
            "saas": ["saas", "software as a service", "cloud service"],
            "fintech": ["fintech", "financial", "banking", "payment"],
            "healthtech": ["healthtech", "healthcare", "medical", "health"],
            "ecommerce": ["ecommerce", "e-commerce", "retail", "shopping"],
            "ai": ["artificial intelligence", "ai", "machine learning", "ml"],
            "blockchain": ["blockchain", "crypto", "cryptocurrency"],
            "gaming": ["gaming", "game", "entertainment"],
            "education": ["education", "learning", "edtech"],
            "enterprise": ["enterprise", "b2b", "business software"]
        }

        text_lower = text.lower()
        for industry, keywords in industry_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                industries.append(industry)

        return industries

    def _extract_tech_preferences(self, text: str) -> List[str]:
        """Extract technical preferences from conversation text"""
        tech_stack = []
        tech_keywords = {
            "python": ["python", "django", "flask", "fastapi"],
            "javascript": ["javascript", "node", "react", "vue", "angular"],
            "java": ["java", "spring", "kotlin"],
            "golang": ["golang", "go"],
            "rust": ["rust"],
            "typescript": ["typescript"],
            "mobile": ["ios", "android", "mobile", "react native"],
            "cloud": ["aws", "azure", "gcp", "cloud"],
            "devops": ["docker", "kubernetes", "ci/cd", "jenkins", "github actions"]
        }

        text_lower = text.lower()
        for tech, keywords in tech_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                tech_stack.append(tech)

        return tech_stack

    def get_personalized_suggestions(self, user_identifier: str, current_context: Dict[str, Any]) -> Dict[str, Any]:
        """Get personalized suggestions based on user's history"""
        memory = self.load_user_memory(user_identifier)

        suggestions = {
            "preferred_icps": memory.get("preferred_icp_types", [])[:3],
            "common_industries": memory.get("common_industries", [])[:3],
            "technical_preferences": memory.get("technical_preferences", [])[:3],
            "conversation_count": memory.get("conversation_count", 0),
            "success_rate": len(memory.get("successful_icps", [])) / max(memory.get("conversation_count", 1), 1)
        }

        return suggestions

    def get_context_aware_prompt(self, user_identifier: str, base_prompt: str) -> str:
        """Enhance prompts with user's historical context"""
        memory = self.load_user_memory(user_identifier)
        suggestions = self.get_personalized_suggestions(user_identifier, {})

        if suggestions["conversation_count"] > 0:
            context_addition = f"""

Based on your previous conversations, I notice you often work with:
- Preferred ICP types: {', '.join(suggestions['preferred_icps']) if suggestions['preferred_icps'] else 'None yet'}
- Common industries: {', '.join(suggestions['common_industries']) if suggestions['common_industries'] else 'Various'}
- Technical preferences: {', '.join(suggestions['technical_preferences']) if suggestions['technical_preferences'] else 'Mixed'}

I can use this context to provide more personalized recommendations."""

            return base_prompt + context_addition

        return base_prompt


class ICPWizardState(TypedDict):
    """Enhanced state for the ICP Wizard conversation with memory and context"""
    messages: List[Dict[str, Any]]
    user_profile: Dict[str, Any]
    current_icp: Optional[Dict[str, Any]]
    icp_options: List[Dict[str, Any]]
    conversation_stage: str
    refinement_criteria: Dict[str, Any]
    final_icp_config: Optional[Dict[str, Any]]
    # Enhanced memory and context features
    conversation_memory: Dict[str, Any]
    user_preferences: Dict[str, Any]
    context_awareness: Dict[str, Any]
    conversation_history: List[Dict[str, Any]]
    learning_data: Dict[str, Any]


class ICPWizard:
    """Enhanced Interactive ICP Wizard with memory and context awareness"""

    def __init__(self, api_key: Optional[str] = None, user_identifier: Optional[str] = None):
        """Initialize the ICP Wizard with LangGraph and memory system"""
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable.")

        # User identification for memory system
        self.user_identifier = user_identifier or self._generate_user_id()

        # Initialize memory system
        self.memory_system = ConversationMemory()

        # Load user's memory and preferences
        self.user_memory = self.memory_system.load_user_memory(self.user_identifier)

        # Initialize LLM with enhanced context
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            api_key=self.api_key
        )

        # Load ICP options
        self.icp_options = self._load_icp_options()

        # Create the enhanced conversation graph
        self.graph = self._create_conversation_graph()

        # Initialize analytics tracking
        self.analytics = {
            "conversation_start_time": None,
            "stage_transitions": [],
            "user_satisfaction_score": None,
            "completion_status": "in_progress"
        }

    def _generate_user_id(self) -> str:
        """Generate a unique user identifier"""
        import socket
        import getpass

        # Create a unique identifier based on system info
        system_info = f"{socket.gethostname()}_{getpass.getuser()}_{datetime.now().strftime('%Y%m%d')}"
        return hashlib.md5(system_info.encode()).hexdigest()[:8]

    def _load_icp_options(self) -> List[Dict[str, Any]]:
        """Load available ICP options from config"""
        icp_config_path = Path(__file__).parent.parent / "configs" / "icp" / "options.yaml"
        try:
            import yaml
            with open(icp_config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
                return config.get('icp_options', [])
        except Exception as e:
            beautiful_logger.logger.warning(f"Could not load ICP config: {e}")
            return []

    def _create_enhanced_initial_state(self) -> ICPWizardState:
        """Create enhanced initial state with memory and context"""
        # Get personalized suggestions from memory
        personalized_suggestions = self.memory_system.get_personalized_suggestions(
            self.user_identifier, {}
        )

        return {
            "messages": [],
            "user_profile": {
                "identifier": self.user_identifier,
                "conversation_count": personalized_suggestions.get("conversation_count", 0),
                "success_rate": personalized_suggestions.get("success_rate", 0.0),
                "preferred_icps": personalized_suggestions.get("preferred_icps", []),
                "common_industries": personalized_suggestions.get("common_industries", []),
                "technical_preferences": personalized_suggestions.get("technical_preferences", [])
            },
            "current_icp": None,
            "icp_options": self.icp_options,
            "conversation_stage": "greeting",
            "refinement_criteria": {},
            "final_icp_config": None,
            # Enhanced memory and context features
            "conversation_memory": self.user_memory,
            "user_preferences": personalized_suggestions,
            "context_awareness": {
                "has_previous_conversations": personalized_suggestions.get("conversation_count", 0) > 0,
                "preferred_stages": self.user_memory.get("learning_data", {}).get("preferred_stages", {}),
                "conversation_context": []
            },
            "conversation_history": [],
            "learning_data": {
                "stage_transitions": [],
                "user_feedback": [],
                "improvement_suggestions": []
            }
        }

    def _create_conversation_graph(self) -> StateGraph:
        """Create the enhanced LangGraph conversation flow with memory"""

        def greeting_node(state: ICPWizardState) -> ICPWizardState:
            """Enhanced greeting with memory and context awareness"""
            messages = state.get('messages', [])
            user_profile = state.get('user_profile', {})
            context_awareness = state.get('context_awareness', {})

            # Check if user has previous conversations
            has_history = context_awareness.get('has_previous_conversations', False)
            conversation_count = user_profile.get('conversation_count', 0)

            if has_history and conversation_count > 0:
                # Personalized greeting for returning users
                greeting_prompt = """
                You are an expert sales intelligence consultant helping a user discover their Ideal Customer Profile (ICP).

                This is a returning user with {conversation_count} previous conversations and a {success_rate:.1f}% success rate.
                Their preferences include:
                - Preferred ICP types: {preferred_icps}
                - Common industries: {common_industries}
                - Technical preferences: {technical_preferences}

                Welcome them back warmly and ask what specific type of customers or ICP they're looking for this time.
                Keep your response conversational and ask open-ended questions to understand their current needs.
                Don't list all available ICPs - focus on having a natural conversation first.
                """

                preferred_icps = ', '.join(user_profile.get('preferred_icps', [])) or 'Various'
                common_industries = ', '.join(user_profile.get('common_industries', [])) or 'Various'
                technical_preferences = ', '.join(user_profile.get('technical_preferences', [])) or 'Mixed'

                formatted_prompt = greeting_prompt.format(
                    conversation_count=conversation_count,
                    success_rate=user_profile.get('success_rate', 0) * 100,
                    preferred_icps=preferred_icps,
                    common_industries=common_industries,
                    technical_preferences=technical_preferences
                )
            else:
                # Standard greeting for new users
                greeting_prompt = """
                You are an expert sales intelligence consultant helping a user discover their Ideal Customer Profile (ICP).

                This appears to be their first conversation with the ICP Wizard.

                Give a warm welcome and briefly explain that you'll help them discover their ideal customer profile through conversation.
                Ask open-ended questions to understand:
                - What type of customers they're targeting
                - What industry or sector they're in
                - What kind of companies they're looking for
                - Any specific characteristics they have in mind

                Keep it conversational and engaging. Don't overwhelm them with technical details.
                """

                formatted_prompt = greeting_prompt

            prompt = ChatPromptTemplate.from_template(formatted_prompt)
            chain = prompt | self.llm

            response = chain.invoke({})

            new_message = {
                "role": "assistant",
                "content": response.content,
                "timestamp": datetime.now().isoformat(),
                "stage": "greeting"
            }

            # Update analytics
            self.analytics["conversation_start_time"] = datetime.now()
            self.analytics["stage_transitions"].append({
                "from_stage": "initial",
                "to_stage": "greeting",
                "timestamp": datetime.now().isoformat()
            })

            return {
                **state,
                "messages": messages + [new_message],
                "conversation_stage": "awaiting_user_input",  # Wait for user response
                "conversation_history": state.get('conversation_history', []) + [{
                    "stage": "greeting",
                    "timestamp": datetime.now().isoformat(),
                    "message": new_message
                }]
            }

        def understand_needs_node(state: ICPWizardState) -> ICPWizardState:
            """Understand user needs and engage in conversation"""
            messages = state.get('messages', [])
            user_input = messages[-1]["content"] if messages else ""

            # Get conversation context
            conversation_history = [msg for msg in messages if msg.get('role') == 'user']
            user_profile = state.get('user_profile', {})

            analysis_prompt = """
            You are having a conversation with a user about discovering their Ideal Customer Profile (ICP).

            Previous user messages in this conversation:
            {conversation_history}

            Latest user input: "{user_input}"

            User profile context:
            - Previous conversations: {conversation_count}
            - Preferred ICPs: {preferred_icps}
            - Common industries: {industries}
            - Technical preferences: {tech_preferences}

            Based on the conversation so far, respond naturally and:
            1. Acknowledge what they've said
            2. Ask relevant follow-up questions to understand their needs better
            3. If you have enough information, suggest 2-3 relevant ICPs with brief explanations
            4. Keep the conversation flowing - don't rush to conclusions
            5. If they're not specific yet, ask about industry, company size, technology, or location

            Be conversational, helpful, and engaging. Don't overwhelm them with technical details.
            """

            conversation_text = "\n".join([f"- {msg['content']}" for msg in conversation_history[-3:]])  # Last 3 messages

            prompt = ChatPromptTemplate.from_template(analysis_prompt)
            chain = prompt | self.llm

            response = chain.invoke({
                "conversation_history": conversation_text,
                "user_input": user_input,
                "conversation_count": user_profile.get('conversation_count', 0),
                "preferred_icps": ', '.join(user_profile.get('preferred_icps', [])) or 'None yet',
                "industries": ', '.join(user_profile.get('common_industries', [])) or 'Various',
                "tech_preferences": ', '.join(user_profile.get('technical_preferences', [])) or 'Mixed'
            })

            new_message = {
                "role": "assistant",
                "content": response.content,
                "timestamp": datetime.now().isoformat(),
                "stage": "understanding_needs"
            }

            return {
                **state,
                "messages": messages + [new_message],
                "conversation_stage": "awaiting_user_input"  # Wait for user response
            }

        def refine_icp_node(state: ICPWizardState) -> ICPWizardState:
            """Refine ICP based on user feedback"""
            messages = state.get('messages', [])
            user_input = messages[-1]["content"] if messages else ""

            refinement_prompt = """
            Help the user refine their ICP selection.

            User input: {user_input}
            Current ICP options: {icp_options}

            Based on their feedback:
            1. Narrow down ICP suggestions
            2. Ask about specific criteria (company size, tech stack, location, etc.)
            3. Explain the characteristics of the suggested ICPs
            4. Help them understand what makes these profiles ideal

            If they're ready to proceed, summarize the selected ICP and ask for confirmation.
            """

            current_icps = [icp for icp in self.icp_options
                          if any(keyword in user_input.lower()
                               for keyword in icp['name'].lower().split())]

            icp_info = "\n".join([
                f"- {icp['id']}: {icp['name']}"
                for icp in current_icps[:3]  # Top 3 matches
            ]) if current_icps else "No specific matches found"

            prompt = ChatPromptTemplate.from_template(refinement_prompt)
            chain = prompt | self.llm

            response = chain.invoke({
                "user_input": user_input,
                "icp_options": icp_info
            })

            new_message = {
                "role": "assistant",
                "content": response.content,
                "timestamp": datetime.now().isoformat(),
                "stage": "refining_icp"
            }

            return {
                **state,
                "messages": messages + [new_message],
                "conversation_stage": "confirming_icp"
            }

        def confirm_icp_node(state: ICPWizardState) -> ICPWizardState:
            """Confirm final ICP selection"""
            messages = state.get('messages', [])
            user_input = messages[-1]["content"] if messages else ""

            confirmation_prompt = """
            Help the user confirm their ICP selection.

            User input: {user_input}

            If they seem ready to proceed:
            1. Summarize the selected ICP
            2. Explain what data will be collected
            3. Ask for final confirmation
            4. If confirmed, prepare to generate the ICP configuration

            If they need more clarification, continue the conversation.
            """

            prompt = ChatPromptTemplate.from_template(confirmation_prompt)
            chain = prompt | self.llm

            response = chain.invoke({"user_input": user_input})

            new_message = {
                "role": "assistant",
                "content": response.content,
                "timestamp": datetime.now().isoformat(),
                "stage": "confirming_icp"
            }

            return {
                **state,
                "messages": messages + [new_message],
                "conversation_stage": "finalizing"
            }

        def finalize_icp_node(state: ICPWizardState) -> ICPWizardState:
            """Finalize ICP configuration"""
            messages = state.get('messages', [])

            # Extract ICP selection from conversation
            selected_icp = self._extract_icp_from_conversation(messages)

            if selected_icp:
                final_config = self._generate_icp_config(selected_icp)

                final_message = {
                    "role": "assistant",
                    "content": f"Perfect! I've configured your ICP: **{selected_icp['name']}**\n\nThe system is now ready to collect data for this profile. Would you like me to start the intelligence pipeline?",
                    "timestamp": datetime.now().isoformat(),
                    "stage": "finalized"
                }

                return {
                    **state,
                    "messages": messages + [final_message],
                    "current_icp": selected_icp,
                    "final_icp_config": final_config,
                    "conversation_stage": "completed"
                }
            else:
                fallback_message = {
                    "role": "assistant",
                    "content": "I need more information to select the right ICP. Could you tell me more about the type of customers you're targeting?",
                    "timestamp": datetime.now().isoformat(),
                    "stage": "fallback"
                }

                return {
                    **state,
                    "messages": messages + [fallback_message],
                    "conversation_stage": "understanding_needs"
                }

        # Create the graph
        workflow = StateGraph(ICPWizardState)

        # Add nodes
        workflow.add_node("greeting", greeting_node)
        workflow.add_node("understand_needs", understand_needs_node)
        workflow.add_node("refine_icp", refine_icp_node)
        workflow.add_node("confirm_icp", confirm_icp_node)
        workflow.add_node("finalize_icp", finalize_icp_node)

        # Define edges
        workflow.set_entry_point("greeting")

        # Add conditional edges based on conversation stage
        workflow.add_conditional_edges(
            "greeting",
            lambda state: state.get("conversation_stage", "understanding_needs"),
            {
                "understanding_needs": "understand_needs",
                "refining_icp": "refine_icp",
                "confirming_icp": "confirm_icp",
                "finalizing": "finalize_icp"
            }
        )

        workflow.add_conditional_edges(
            "understand_needs",
            lambda state: self._determine_next_stage(state),
            {
                "refining_icp": "refine_icp",
                "confirming_icp": "confirm_icp",
                "finalizing": "finalize_icp",
                "understanding_needs": "understand_needs"
            }
        )

        workflow.add_conditional_edges(
            "refine_icp",
            lambda state: self._determine_next_stage(state),
            {
                "confirming_icp": "confirm_icp",
                "finalizing": "finalize_icp",
                "understanding_needs": "understand_needs"
            }
        )

        workflow.add_conditional_edges(
            "confirm_icp",
            lambda state: self._determine_next_stage(state),
            {
                "finalizing": "finalize_icp",
                "understanding_needs": "understand_needs"
            }
        )

        workflow.add_edge("finalize_icp", END)

        return workflow.compile()

    def _determine_next_stage(self, state: ICPWizardState) -> str:
        """Determine the next conversation stage based on current state"""
        messages = state.get('messages', [])
        if not messages:
            return "understanding_needs"

        last_message = messages[-1]
        content = last_message.get('content', '').lower()

        # Simple heuristics to determine next stage
        if any(word in content for word in ['confirm', 'ready', 'proceed', 'start']):
            return "finalizing"
        elif any(word in content for word in ['refine', 'change', 'different']):
            return "refining_icp"
        elif any(word in content for word in ['tell me more', 'explain', 'what']):
            return "confirming_icp"
        else:
            return "understanding_needs"

    def _extract_icp_from_conversation(self, messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Extract ICP selection from conversation messages"""
        conversation_text = " ".join([msg.get('content', '') for msg in messages])

        # Simple keyword matching for ICP selection
        for icp in self.icp_options:
            icp_keywords = icp['name'].lower().split()
            if any(keyword in conversation_text.lower() for keyword in icp_keywords):
                return icp

        return None

    def _generate_icp_config(self, icp: Dict[str, Any]) -> Dict[str, Any]:
        """Generate ICP configuration for the intelligence system"""
        return {
            "icp_id": icp['id'],
            "icp_name": icp['name'],
            "github_queries": icp.get('github', {}).get('repo_queries', []),
            "technographics": icp.get('technographics', {}),
            "firmographics": icp.get('firmographics', {}),
            "personas": icp.get('personas', []),
            "triggers": icp.get('triggers', []),
            "disqualifiers": icp.get('disqualifiers', []),
            "generated_at": datetime.now().isoformat(),
            "source": "interactive_wizard"
        }

    async def start_conversation(self) -> Dict[str, Any]:
        """Start the enhanced interactive ICP wizard conversation with memory"""
        log_header("🎯 Enhanced Interactive ICP Wizard")
        beautiful_logger.logger.info("Starting conversational ICP discovery with memory...")

        # Create enhanced initial state with memory and context
        initial_state = self._create_enhanced_initial_state()

        # Log memory insights for returning users
        if initial_state["context_awareness"]["has_previous_conversations"]:
            beautiful_logger.logger.info(f"Loaded memory for user {self.user_identifier}")
            beautiful_logger.logger.info(f"Previous conversations: {initial_state['user_profile']['conversation_count']}")
            beautiful_logger.logger.info(f"Success rate: {initial_state['user_profile']['success_rate']:.1%}")

        print("\n🤖 Welcome to the Interactive ICP Wizard!")
        print("=" * 50)
        print("I'll help you discover your ideal customer profile through conversation.")
        print("Type 'quit' or 'exit' at any time to end the conversation.\n")

        current_state = initial_state

        while current_state.get('conversation_stage') != 'completed':
            # Get next response from the graph
            result = await self.graph.ainvoke(current_state)

            # Display assistant message
            last_message = result['messages'][-1]
            print(f"\n🤖 {last_message['content']}")

            # Check if conversation is complete
            if result.get('conversation_stage') == 'completed':
                current_state = result
                break

            # Check if we're awaiting user input
            if result.get('conversation_stage') == 'awaiting_user_input':
                # Get user input
                user_input = input("\n👤 You: ").strip()

                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye! Feel free to restart the conversation anytime.")
                    break

                # Add user message to state and move to analysis phase
                user_message = {
                    "role": "user",
                    "content": user_input,
                    "timestamp": datetime.now().isoformat(),
                    "stage": "user_response"
                }

                current_state = {
                    **result,
                    "messages": result['messages'] + [user_message],
                    "conversation_stage": "understanding_needs"  # Now analyze the user input
                }
            else:
                # If not awaiting input, continue with current state
                current_state = result

        # Update memory with conversation results
        self._update_conversation_memory(current_state)

        return current_state

    def _update_conversation_memory(self, final_state: ICPWizardState):
        """Update user's memory with conversation results"""
        try:
            # Calculate conversation metrics
            conversation_data = {
                "messages": final_state.get("messages", []),
                "final_icp_config": final_state.get("final_icp_config"),
                "conversation_stage": final_state.get("conversation_stage"),
                "success_score": self._calculate_success_score(final_state),
                "conversation_duration": self._calculate_conversation_duration(),
                "stage_transitions": self.analytics.get("stage_transitions", [])
            }

            # Update memory system
            updated_memory = self.memory_system.update_memory(
                self.user_identifier,
                conversation_data
            )

            # Log memory update
            beautiful_logger.logger.info(f"Updated memory for user {self.user_identifier}")
            if conversation_data["final_icp_config"]:
                beautiful_logger.logger.info(f"Successful ICP creation: {conversation_data['final_icp_config']['icp_name']}")
            else:
                beautiful_logger.logger.info("Conversation completed without ICP creation")

            # Update analytics
            self.analytics["completion_status"] = "completed" if conversation_data["final_icp_config"] else "incomplete"

        except Exception as e:
            beautiful_logger.logger.error(f"Error updating conversation memory: {e}")

    def _calculate_success_score(self, final_state: ICPWizardState) -> float:
        """Calculate success score for the conversation"""
        if not final_state.get("final_icp_config"):
            return 0.0

        # Base score for ICP creation
        score = 0.5

        # Bonus for quick completion
        duration = self._calculate_conversation_duration()
        if duration and duration < timedelta(minutes=10):
            score += 0.3
        elif duration and duration < timedelta(minutes=20):
            score += 0.2

        # Bonus for user profile completeness
        user_profile = final_state.get("user_profile", {})
        if user_profile.get("conversation_count", 0) > 1:
            score += 0.2  # Returning user bonus

        return min(score, 1.0)

    def _calculate_conversation_duration(self) -> Optional[timedelta]:
        """Calculate total conversation duration"""
        start_time = self.analytics.get("conversation_start_time")
        if start_time:
            return datetime.now() - start_time
        return None

    def get_memory_insights(self) -> Dict[str, Any]:
        """Get insights from user's memory for analytics"""
        memory = self.memory_system.load_user_memory(self.user_identifier)
        return {
            "total_conversations": memory.get("conversation_count", 0),
            "successful_icps": len(memory.get("successful_icps", [])),
            "preferred_icp_types": memory.get("preferred_icp_types", []),
            "common_industries": memory.get("common_industries", []),
            "technical_preferences": memory.get("technical_preferences", []),
            "success_rate": len(memory.get("successful_icps", [])) / max(memory.get("conversation_count", 1), 1)
        }

    def run_wizard(self) -> Optional[Dict[str, Any]]:
        """Run the ICP wizard synchronously"""
        try:
            return asyncio.run(self.start_conversation())
        except KeyboardInterrupt:
            print("\n👋 Conversation interrupted. Your progress has been saved.")
            return None
        except Exception as e:
            beautiful_logger.logger.error(f"Error running ICP wizard: {e}")
            return None


def main():
    """Main entry point for the ICP wizard"""
    try:
        wizard = ICPWizard()
        result = wizard.run_wizard()

        if result and result.get('final_icp_config'):
            print("\n✅ ICP Configuration Generated!")
            config = result['final_icp_config']
            print(f"🎯 Selected ICP: {config['icp_name']}")
            print(f"📊 Configuration ready for intelligence pipeline")

            # Save configuration
            output_path = Path("lead_intelligence/data/icp_config.json")
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump(config, f, indent=2)

            print(f"💾 Configuration saved to: {output_path}")

            return config

    except Exception as e:
        beautiful_logger.logger.error(f"Failed to run ICP wizard: {e}")
        print(f"\n❌ Error: {e}")
        return None


if __name__ == "__main__":
    main()
