#!/usr/bin/env python3
"""
Interactive ICP Wizard - Conversational AI for Ideal Customer Profile Discovery
"""

import os
import json
import asyncio
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, TypedDict, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .memory_system import ConversationMemory, UserProfile
from ..utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ICPConfiguration:
    """ICP Configuration result from wizard"""
    icp_id: str
    icp_name: str
    description: str
    technographics: Dict[str, Any]
    firmographics: Dict[str, Any]
    personnas: List[Dict[str, Any]]
    triggers: List[str]
    disqualifiers: List[str]
    github_queries: List[str]
    generated_at: str
    source: str = "interactive_wizard"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ICPWizardState(TypedDict):
    """State for the ICP Wizard conversation flow"""
    messages: List[Dict[str, Any]]
    user_profile: Dict[str, Any]
    current_icp: Optional[Dict[str, Any]]
    icp_options: List[Dict[str, Any]]
    conversation_stage: str
    refinement_criteria: Dict[str, Any]
    final_icp_config: Optional[ICPConfiguration]
    conversation_memory: Dict[str, Any]
    user_preferences: Dict[str, Any]
    context_awareness: Dict[str, Any]
    conversation_history: List[Dict[str, Any]]
    learning_data: Dict[str, Any]
    analytics: Dict[str, Any]


class ICPWizard:
    """
    Interactive ICP Wizard with LangGraph Integration

    Provides conversational AI for discovering and refining Ideal Customer Profiles
    with persistent memory, learning capabilities, and seamless pipeline integration.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        user_identifier: Optional[str] = None,
        memory_dir: Optional[Path] = None,
        config_dir: Optional[Path] = None
    ):
        """Initialize the ICP Wizard with all components"""
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable.")

        # User identification
        self.user_identifier = user_identifier or self._generate_user_id()

        # Initialize components
        self.memory_system = ConversationMemory(memory_dir)
        self.user_memory = self.memory_system.load_user_memory(self.user_identifier)

        # Initialize OpenAI client
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            api_key=self.api_key
        )

        # Load ICP options
        self.config_dir = config_dir or Path("configs/icp")
        self.icp_options = self._load_icp_options()

        # Create conversation graph
        self.graph = self._create_conversation_graph()

        # Analytics tracking
        self.analytics = {
            "conversation_start_time": None,
            "stage_transitions": [],
            "messages_sent": 0,
            "conversation_duration": 0,
            "success": False
        }

        logger.info(f"Initialized ICP Wizard for user {self.user_identifier}")
        logger.info(f"Loaded {len(self.icp_options)} ICP options")

    def _generate_user_id(self) -> str:
        """Generate unique user identifier"""
        import socket
        import getpass

        system_info = f"{socket.gethostname()}_{getpass.getuser()}_{datetime.now().strftime('%Y%m%d')}"
        return hashlib.md5(system_info.encode()).hexdigest()[:8]

    def _load_icp_options(self) -> List[Dict[str, Any]]:
        """Load available ICP options from configuration"""
        try:
            import yaml
            options_file = self.config_dir / "options.yaml"

            if not options_file.exists():
                logger.warning(f"ICP options file not found: {options_file}")
                return []

            with open(options_file, 'r') as f:
                config = yaml.safe_load(f) or {}
                return config.get('icp_options', [])

        except Exception as e:
            logger.error(f"Failed to load ICP options: {e}")
            return []

    def _create_initial_state(self) -> ICPWizardState:
        """Create enhanced initial state with memory and context"""
        # Get personalized suggestions from memory
        personalized_suggestions = self.memory_system.get_personalized_suggestions(self.user_identifier)

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
            },
            "analytics": self.analytics.copy()
        }

    def _create_conversation_graph(self) -> StateGraph:
        """Create the LangGraph conversation flow"""

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
                greeting_prompt = f"""
                You are an expert sales intelligence consultant helping a user discover their Ideal Customer Profile (ICP).

                This is a returning user with {conversation_count} previous conversations and a {user_profile.get('success_rate', 0)*100:.1f}% success rate.
                Their preferences include:
                - Preferred ICP types: {', '.join(user_profile.get('preferred_icps', [])) or 'Various'}
                - Common industries: {', '.join(user_profile.get('common_industries', [])) or 'Various'}
                - Technical preferences: {', '.join(user_profile.get('technical_preferences', [])) or 'Mixed'}

                Available ICPs:
                {self._format_icp_list()}

                Welcome them back warmly, acknowledge their history, and ask what they're looking for this time.
                Reference their past preferences to make them feel understood.
                """
            else:
                # Standard greeting for new users
                greeting_prompt = f"""
                You are an expert sales intelligence consultant helping a user discover their Ideal Customer Profile (ICP).

                This appears to be their first conversation with the ICP Wizard.

                Available ICPs:
                {self._format_icp_list()}

                Give a warm welcome, explain briefly what ICP discovery is about, and ask what type of customers they're looking for.
                Be conversational and ask open-ended questions to understand their needs.
                """

            prompt = ChatPromptTemplate.from_template(greeting_prompt)
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
                "conversation_stage": "understanding_needs",
                "conversation_history": state.get('conversation_history', []) + [{
                    "stage": "greeting",
                    "timestamp": datetime.now().isoformat(),
                    "message": new_message
                }]
            }

        def understand_needs_node(state: ICPWizardState) -> ICPWizardState:
            """Understand user needs and suggest ICPs"""
            messages = state.get('messages', [])
            user_input = messages[-1]["content"] if messages else ""

            analysis_prompt = f"""
            Analyze the user's input and suggest relevant ICPs from the available options.

            User input: {user_input}

            Available ICPs:
            {self._format_icp_details()}

            Based on their response:
            1. Identify which ICPs might be relevant
            2. Ask clarifying questions if needed
            3. Explain why certain ICPs match their needs
            4. Ask for confirmation or more details

            Be conversational and help them refine their understanding.
            """

            prompt = ChatPromptTemplate.from_template(analysis_prompt)
            chain = prompt | self.llm

            response = chain.invoke({
                "user_input": user_input,
                "icp_details": self._format_icp_details()
            })

            new_message = {
                "role": "assistant",
                "content": response.content,
                "timestamp": datetime.now().isoformat(),
                "stage": "analyzing_needs"
            }

            return {
                **state,
                "messages": messages + [new_message],
                "conversation_stage": "refining_icp"
            }

        def refine_icp_node(state: ICPWizardState) -> ICPWizardState:
            """Refine ICP based on user feedback"""
            messages = state.get('messages', [])
            user_input = messages[-1]["content"] if messages else ""

            refinement_prompt = f"""
            Help the user refine their ICP selection.

            User input: {user_input}
            Current ICP options: {self._format_icp_list()}

            Based on their feedback:
            1. Narrow down ICP suggestions
            2. Ask about specific criteria (company size, tech stack, location, etc.)
            3. Explain the characteristics of the suggested ICPs
            4. Help them understand what makes these profiles ideal

            If they're ready to proceed, summarize the selected ICP and ask for confirmation.
            """

            current_icps = self._find_matching_icps(user_input)

            prompt = ChatPromptTemplate.from_template(refinement_prompt)
            chain = prompt | self.llm

            response = chain.invoke({
                "user_input": user_input,
                "icp_options": self._format_icp_list(current_icps)
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
                "understanding_needs": "understanding_needs"
            }
        )

        workflow.add_conditional_edges(
            "confirm_icp",
            lambda state: self._determine_next_stage(state),
            {
                "finalizing": "finalize_icp",
                "understanding_needs": "understanding_needs"
            }
        )

        workflow.add_edge("finalize_icp", END)

        return workflow.compile()

    def _format_icp_list(self, icps: Optional[List[Dict[str, Any]]] = None) -> str:
        """Format ICP list for prompts"""
        icps = icps or self.icp_options
        return "\n".join([
            f"- {icp['id']}: {icp['name']}"
            for icp in icps
        ])

    def _format_icp_details(self) -> str:
        """Format detailed ICP information for prompts"""
        return "\n".join([
            f"• {icp['id']}: {icp['name']}\n  {icp.get('description', 'No description available')}"
            for icp in self.icp_options
        ])

    def _find_matching_icps(self, user_input: str) -> List[Dict[str, Any]]:
        """Find ICPs that match user input"""
        user_input_lower = user_input.lower()

        matches = []
        for icp in self.icp_options:
            # Check name and description for matches
            icp_text = f"{icp['name']} {icp.get('description', '')}".lower()
            if any(keyword in icp_text for keyword in user_input_lower.split()):
                matches.append(icp)

        return matches[:5]  # Return top 5 matches

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

    def _generate_icp_config(self, icp: Dict[str, Any]) -> ICPConfiguration:
        """Generate ICP configuration for the intelligence system"""
        return ICPConfiguration(
            icp_id=icp['id'],
            icp_name=icp['name'],
            description=icp.get('description', ''),
            technographics=icp.get('technographics', {}),
            firmographics=icp.get('firmographics', {}),
            personnas=icp.get('personas', []),
            triggers=icp.get('triggers', []),
            disqualifiers=icp.get('disqualifiers', []),
            github_queries=icp.get('github', {}).get('repo_queries', []),
            generated_at=datetime.now().isoformat(),
            source="interactive_wizard"
        )

    async def start_conversation(self) -> Dict[str, Any]:
        """Start the enhanced interactive ICP wizard conversation with memory"""
        logger.info("Starting conversational ICP discovery with memory...")

        # Create enhanced initial state with memory and context
        initial_state = self._create_initial_state()

        # Log memory insights for returning users
        if initial_state["context_awareness"]["has_previous_conversations"]:
            logger.info(f"Loaded memory for user {self.user_identifier}")
            logger.info(f"Previous conversations: {initial_state['user_profile']['conversation_count']}")

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

            # Get user input
            user_input = input("\n👤 You: ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye! Feel free to restart the conversation anytime.")
                break

            # Add user message to state
            user_message = {
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now().isoformat(),
                "stage": result.get('conversation_stage', 'user_input')
            }

            current_state = {
                **result,
                "messages": result['messages'] + [user_message]
            }

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
                "duration_seconds": self._calculate_conversation_duration(),
                "stage_transitions": self.analytics.get("stage_transitions", [])
            }

            # Update memory system
            updated_memory = self.memory_system.update_memory_from_conversation(
                self.user_identifier,
                conversation_data
            )

            # Log memory update
            logger.info(f"Updated memory for user {self.user_identifier}")
            if conversation_data["final_icp_config"]:
                logger.info(f"Successful ICP creation: {conversation_data['final_icp_config'].icp_name}")

            # Update analytics
            self.analytics["success"] = bool(conversation_data["final_icp_config"])

        except Exception as e:
            logger.error(f"Error updating conversation memory: {e}")

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
        return self.memory_system.get_personalized_suggestions(self.user_identifier)

    def run_wizard(self) -> Optional[ICPConfiguration]:
        """Run the ICP wizard synchronously"""
        try:
            result = asyncio.run(self.start_conversation())

            if result and result.get('final_icp_config'):
                config = result['final_icp_config']
                logger.info(f"ICP Wizard completed successfully: {config.icp_name}")
                return config
            else:
                logger.info("ICP wizard did not complete successfully")
                return None

        except KeyboardInterrupt:
            print("\n👋 Conversation interrupted. Your progress has been saved.")
            return None
        except Exception as e:
            logger.error(f"Error running ICP wizard: {e}")
            return None

    def export_configuration(self, config: ICPConfiguration, output_path: Path) -> bool:
        """Export ICP configuration to file"""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(f"Exported ICP configuration to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting configuration: {e}")
            return False
