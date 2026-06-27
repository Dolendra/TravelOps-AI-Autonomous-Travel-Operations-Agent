import uuid
import logging
from typing import List, Dict, Any, Optional
from backend.services.prompt_loader import PromptLoader
from backend.services.guardrails import GuardrailsProcessor
from agents.memory.memory_agent import MemoryAgent

from backend.runtime.context.models import ContextFragment, ContextBundle
from backend.runtime.context.providers.system import SystemProvider
from backend.runtime.context.providers.workflow import WorkflowProvider
from backend.runtime.context.providers.conversation import ConversationProvider
from backend.runtime.context.providers.memory import MemoryProvider
from backend.runtime.context.providers.policy import PolicyProvider
from backend.runtime.context.providers.rag import RAGProvider
from backend.runtime.context.budget import TokenBudgetManager
from backend.runtime.context.cache import ContextCache

logger = logging.getLogger("travelops.runtime.context.builder")

class AIRuntime:
    def __init__(self, model_router: Any, prompt_loader: PromptLoader):
        self.model_router = model_router
        self.prompt_loader = prompt_loader
        self.memory_agent = MemoryAgent(model_router, prompt_loader)
        
        # Context Providers
        self.system_provider = SystemProvider(prompt_loader)
        self.workflow_provider = WorkflowProvider()
        self.conversation_provider = ConversationProvider()
        self.memory_provider = MemoryProvider(self.memory_agent)
        self.policy_provider = PolicyProvider()
        self.rag_provider = RAGProvider()
        
        self.cache = ContextCache()

    def build_context(
        self,
        agent: str,
        session_id: str,
        user_query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        limit: Optional[int] = None
    ) -> ContextBundle:
        """
        Main entry point that coordinates context fragment compilation, dynamic token budgeting,
        PII/injection guardrails, cache lease checks, and returns a fully versioned ContextBundle.
        """
        # 1. Cache lease lookup check
        cached_bundle = self.cache.get(agent, session_id, user_query, chat_history)
        if cached_bundle:
            logger.info(f"ContextCache HIT for session: {session_id}, agent: {agent}")
            return cached_bundle

        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        
        # 2. Gather context fragments based on target agent type
        fragments: List[ContextFragment] = []
        
        # System directive instructions and user query are required core blocks
        system_frag = self.system_provider.get_fragment(agent)
        fragments.append(system_frag)
        
        query_frag = self.conversation_provider.get_query_fragment(user_query)
        fragments.append(query_frag)
        
        if agent.lower() == "support":
            # Support includes full orchestration timelines, preferences, policies, and history logs
            workflow_frag = self.workflow_provider.get_fragment(session_id)
            fragments.append(workflow_frag)
            
            memory_frag = self.memory_provider.get_fragment(session_id)
            fragments.append(memory_frag)
            
            policy_frag = self.policy_provider.get_fragment()
            fragments.append(policy_frag)
            
            rag_frag = self.rag_provider.get_fragment(user_query)
            fragments.append(rag_frag)
            
            history_frag = self.conversation_provider.get_history_fragment(chat_history or [])
            fragments.append(history_frag)
            
        elif agent.lower() == "planner":
            # Planner needs preferences profiles in short-term context
            memory_frag = self.memory_provider.get_fragment(session_id)
            fragments.append(memory_frag)

        # 3. Dynamic Token Budgeting
        budget_manager = TokenBudgetManager(limit=limit or 8000, agent=agent)
        accepted_fragments, removed_sections = budget_manager.fit_fragments(fragments)
        
        accepted_by_name = {f.name: f for f in accepted_fragments}
        sources = [f.name for f in accepted_fragments]
        
        # 4. Explainability mapping
        explainability_map = {}
        for frag in accepted_fragments:
            explainability_map[frag.name] = frag.explainability
        for removed in removed_sections:
            clean_name = removed.replace(" (truncated)", "")
            explainability_map[clean_name] = f"Pruned/Clipped due to token budget bounds (Limit: {budget_manager.limit} tokens)."

        # 5. Formulate compiled system block
        system_blocks = []
        if "system" in accepted_by_name:
            system_blocks.append(accepted_by_name["system"].content)
            
        if "policy" in accepted_by_name:
            system_blocks.append(accepted_by_name["policy"].content)
            
        if "rag" in accepted_by_name:
            system_blocks.append(f"--- FAQ POLICY RULES ---\n{accepted_by_name['rag'].content}\n----------------------")
            
        if "workflow" in accepted_by_name:
            system_blocks.append(accepted_by_name["workflow"].content)
            
        if "memory" in accepted_by_name:
            system_blocks.append(accepted_by_name["memory"].content)
            
        compiled_system_instruction = "\n\n".join(system_blocks)
        
        # Guardrail masking
        compiled_system_instruction = GuardrailsProcessor.sanitize_input(compiled_system_instruction)
        
        # Assemble message turns list
        messages = [{"role": "system", "content": compiled_system_instruction}]
        
        # Dialogue history logs
        if "history" in accepted_by_name:
            history_content = accepted_by_name["history"].content
            if history_content != "No previous dialog history.":
                for line in history_content.splitlines():
                    if ":" in line:
                        parts = line.split(":", 1)
                        sender = parts[0].strip().lower()
                        text = parts[1].strip()
                        role = "user" if sender == "user" else "assistant"
                        messages.append({
                            "role": role,
                            "content": GuardrailsProcessor.sanitize_input(text)
                        })
                        
        # Current user query
        if "query" in accepted_by_name:
            messages.append({
                "role": "user",
                "content": GuardrailsProcessor.sanitize_input(user_query)
            })
            
        # 6. Estimate token count
        total_chars = sum(len(m["content"]) for m in messages)
        token_usage = max(1, total_chars // 4)
        
        bundle = ContextBundle(
            messages=messages,
            token_usage=token_usage,
            sources=sources,
            removed_sections=removed_sections,
            trace_id=trace_id,
            version="2.0.0",
            explainability=explainability_map
        )
        
        # 7. Cache set
        self.cache.set(agent, session_id, user_query, chat_history, bundle)
        
        return bundle

    # Compatibility signatures
    def build_intent_context(self, user_query: str) -> List[Dict[str, str]]:
        bundle = self.build_context(
            agent="intent",
            session_id="none",
            user_query=user_query,
            chat_history=None
        )
        return bundle.messages

    def build_planner_context(
        self,
        session_id: str,
        origin: str,
        destination: str,
        travel_date: str
    ) -> List[Dict[str, str]]:
        user_query = f"Create a task graph for travel from {origin} to {destination} on {travel_date}."
        bundle = self.build_context(
            agent="planner",
            session_id=session_id,
            user_query=user_query,
            chat_history=None
        )
        return bundle.messages

    def build_support_context(
        self,
        session_id: str,
        user_query: str,
        chat_history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        bundle = self.build_context(
            agent="support",
            session_id=session_id,
            user_query=user_query,
            chat_history=chat_history
        )
        return bundle.messages

# Alias pointing to AIRuntime for backward compatibility
PromptContextBuilder = AIRuntime
