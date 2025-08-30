#!/usr/bin/env python3
"""
Interactive ICP Wizard with LangGraph Integration
Conversational interface for discovering and refining Ideal Customer Profiles
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, TypedDict
from datetime import datetime

# Add parent directories to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "lead_intelligence"))

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from lead_intelligence.core.beautiful_logger import beautiful_logger, log_header, log_separator


class ICPWizardState(TypedDict):
    """State for the ICP Wizard conversation"""
    messages: List[Dict[str, Any]]
    user_profile: Dict[str, Any]
    current_icp: Optional[Dict[str, Any]]
    icp_options: List[Dict[str, Any]]
    conversation_stage: str
    refinement_criteria: Dict[str, Any]
    final_icp_config: Optional[Dict[str, Any]]


class ICPWizard:
    """Interactive ICP Wizard using LangGraph for conversational ICP discovery"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the ICP Wizard with LangGraph"""
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable.")

        # Initialize LLM
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            api_key=self.api_key
        )

        # Load ICP options
        self.icp_options = self._load_icp_options()

        # Create the conversation graph
        self.graph = self._create_conversation_graph()

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

    def _create_conversation_graph(self) -> StateGraph:
        """Create the LangGraph conversation flow"""

        def greeting_node(state: ICPWizardState) -> ICPWizardState:
            """Initial greeting and ICP overview"""
            messages = state.get('messages', [])

            greeting_prompt = """
            You are an expert sales intelligence consultant helping a user discover their Ideal Customer Profile (ICP).

            Available ICPs:
            {icp_list}

            Start by greeting the user and asking what type of customers they're looking for.
            Be conversational and ask open-ended questions to understand their needs.
            """

            icp_list = "\n".join([
                f"- {icp['id']}: {icp['name']}"
                for icp in self.icp_options
            ])

            prompt = ChatPromptTemplate.from_template(greeting_prompt)
            chain = prompt | self.llm

            response = chain.invoke({"icp_list": icp_list})

            new_message = {
                "role": "assistant",
                "content": response.content,
                "timestamp": datetime.now().isoformat(),
                "stage": "greeting"
            }

            return {
                **state,
                "messages": messages + [new_message],
                "conversation_stage": "understanding_needs"
            }

        def understand_needs_node(state: ICPWizardState) -> ICPWizardState:
            """Understand user needs and suggest ICPs"""
            messages = state.get('messages', [])
            user_input = messages[-1]["content"] if messages else ""

            analysis_prompt = """
            Analyze the user's input and suggest relevant ICPs from the available options.

            User input: {user_input}

            Available ICPs:
            {icp_details}

            Based on their response:
            1. Identify which ICPs might be relevant
            2. Ask clarifying questions if needed
            3. Explain why certain ICPs match their needs
            4. Ask for confirmation or more details

            Be conversational and help them refine their understanding.
            """

            icp_details = "\n".join([
                f"• {icp['id']}: {icp['name']}\n  {icp.get('description', 'No description available')}"
                for icp in self.icp_options
            ])

            prompt = ChatPromptTemplate.from_template(analysis_prompt)
            chain = prompt | self.llm

            response = chain.invoke({
                "user_input": user_input,
                "icp_details": icp_details
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
        """Start the interactive ICP wizard conversation"""
        log_header("🎯 Interactive ICP Wizard")
        beautiful_logger.logger.info("Starting conversational ICP discovery...")

        initial_state: ICPWizardState = {
            "messages": [],
            "user_profile": {},
            "current_icp": None,
            "icp_options": self.icp_options,
            "conversation_stage": "greeting",
            "refinement_criteria": {},
            "final_icp_config": None
        }

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

        return current_state

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
