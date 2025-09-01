"""
CMOAgentAdapter - Wraps existing CMOAgent with unified event emission
Bridges the gap between legacy agent and new event model
"""
import time
import logging
from typing import Dict, Any, Optional, List
from .types import JobSpec, RunSummary, JobEvent
from .events import EventSink

logger = logging.getLogger(__name__)


class CMOAgentAdapter:
    """Adapter that wraps CMOAgent with unified event emission"""
    
    def __init__(self, agent_factory):
        """
        agent_factory: function that creates a CMOAgent instance
        """
        self.agent_factory = agent_factory
        
    async def run(self, spec: JobSpec, sink: EventSink) -> RunSummary:
        """Run job with unified event emission"""
        job_id = f"job-{int(time.time())}"
        start_time = time.time()
        
        try:
            # Emit job started
            sink.emit(JobEvent.job_started(job_id, spec.goal))
            
            # Create agent instance
            agent = self.agent_factory(spec)
            
            # Create event-aware progress callback
            def progress_callback(progress_info):
                """Convert agent progress to unified events"""
                if isinstance(progress_info, dict):
                    stage = progress_info.get('stage', 'unknown')
                    current_item = progress_info.get('current_item', '')
                    sink.emit(JobEvent.progress(job_id, stage, current_item))
            
            # Monkey-patch agent to emit tool events
            original_toolbelt_execute = None
            if hasattr(agent, 'toolbelt') and hasattr(agent.toolbelt, 'execute'):
                original_toolbelt_execute = agent.toolbelt.execute
                
                async def event_aware_execute(tool_name, **kwargs):
                    # Emit tool started
                    sink.emit(JobEvent.tool_started(job_id, tool_name))
                    
                    # Execute tool
                    start = time.time()
                    result = await original_toolbelt_execute(tool_name, **kwargs)
                    duration_ms = (time.time() - start) * 1000
                    
                    # Emit tool completed
                    sink.emit(JobEvent(
                        "tool.completed", 
                        time.time(), 
                        {
                            "tool_name": tool_name, 
                            "duration_ms": duration_ms,
                            "success": getattr(result, 'success', False)
                        }, 
                        job_id
                    ))
                    
                    return result
                
                agent.toolbelt.execute = event_aware_execute
            
            # Run the agent
            result = await agent.run_job(spec.goal, spec.created_by, progress_callback)
            
            # Restore original method
            if original_toolbelt_execute:
                agent.toolbelt.execute = original_toolbelt_execute
            
            # Build summary from result
            duration = time.time() - start_time
            final_state = result.get('final_state', {}) if isinstance(result, dict) else {}
            
            summary = RunSummary(
                ok=result.get('success', False) if isinstance(result, dict) else False,
                job_id=job_id,
                duration_seconds=duration,
                final_state=final_state
            )
            
            # Extract metrics from final state
            if final_state:
                repos = final_state.get('repos', [])
                candidates = final_state.get('candidates', [])
                leads = final_state.get('leads', [])
                to_send = final_state.get('to_send', [])
                
                summary.repos_found = len(repos)
                summary.candidates_found = len(candidates)
                summary.leads_with_emails = len([l for l in leads if l.get('email')])
                summary.emails_prepared = len(to_send)
                
                # Extract counters
                counters = final_state.get('counters', {})
                summary.stats = {
                    'steps': counters.get('steps', 0),
                    'api_calls': counters.get('api_calls', 0),
                    'repos': len(repos),
                    'candidates': len(candidates),
                    'leads': len(leads),
                    'emails_prepared': len(to_send),
                    'duration_s': duration
                }
            
            # Generate beautiful summary text (same as CLI)
            summary_text = self._generate_beautiful_summary(final_state)
            if summary_text:
                summary.stats['summary_text'] = summary_text
            
            # Emit job completed with summary
            sink.emit(JobEvent.job_completed(job_id, summary))
            
            return summary
            
        except Exception as e:
            logger.error(f"CMOAgentAdapter error: {e}")
            
            # Emit error event
            sink.emit(JobEvent(
                "error", 
                time.time(), 
                {"message": str(e)}, 
                job_id
            ))
            
            # Return failed summary
            duration = time.time() - start_time
            return RunSummary(
                ok=False,
                job_id=job_id, 
                duration_seconds=duration,
                errors=[str(e)]
            )
    
    def _generate_beautiful_summary(self, final_state: Dict[str, Any]) -> str:
        """Generate beautiful summary (same as CLI)"""
        try:
            # Extract data
            repos = final_state.get('repos', [])
            candidates = final_state.get('candidates', [])
            leads = final_state.get('leads', [])
            icp = final_state.get('icp', {})
            
            # Collect emails
            all_emails = set()
            contactable_emails = []

            for lead in leads:
                email = lead.get('email')
                if email and '@' in email and 'noreply' not in email.lower():
                    all_emails.add(email.lower())
                    contactable_emails.append({
                        'email': email,
                        'name': lead.get('name', lead.get('login', 'Unknown')),
                        'company': lead.get('company', ''),
                        'followers': lead.get('followers', 0)
                    })

            # Create contactable emails CSV file
            if contactable_emails:
                try:
                    import os
                    from pathlib import Path

                    # Create exports directory if it doesn't exist
                    export_dir = Path('./exports')
                    export_dir.mkdir(exist_ok=True)

                    # Generate job ID from timestamp if not available
                    job_id = f"cmo-{final_state.get('timestamp', 'unknown')}"[:20]

                    csv_path = export_dir / f"{job_id}_leads_contactable.csv"
                    csv_content = '\n'.join([contact['email'] for contact in contactable_emails])

                    with open(csv_path, 'w') as f:
                        f.write(csv_content)

                    print(f"DEBUG: Created contactable emails CSV at {csv_path} with {len(contactable_emails)} emails")

                except Exception as e:
                    print(f"DEBUG: Failed to create contactable emails CSV: {e}")
            
            # Build summary
            lines = []
            lines.append("\n" + "="*60)
            lines.append("📋 CAMPAIGN SUMMARY")
            lines.append("="*60)

            # Goal & ICP overview
            try:
                if icp:
                    goal_text = icp.get('goal')
                    if goal_text:
                        lines.append("\n🎯 GOAL:")
                        lines.append(f"   {goal_text}")
                    lines.append("\n🧭 ICP:")
                    if icp.get('languages'):
                        lines.append(f"   Languages: {', '.join(icp['languages'])}")
                    if icp.get('stars_range'):
                        lines.append(f"   Stars: {icp['stars_range']}")
                    if icp.get('activity_days'):
                        lines.append(f"   Activity: last {icp['activity_days']} days")
                    if icp.get('keywords'):
                        lines.append(f"   Keywords: {', '.join(icp['keywords'])}")
                    if icp.get('topics'):
                        lines.append(f"   Topics: {', '.join(icp['topics'][:5])}")
            except Exception:
                pass
            
            # Repository Summary
            lines.append(f"\n📦 REPOSITORIES ANALYZED:")
            lines.append(f"   Total: {len(repos)}")
            
            # People Summary  
            lines.append(f"\n👥 PEOPLE DISCOVERED:")
            lines.append(f"   Candidates: {len(candidates)}")
            lines.append(f"   Leads (with email): {len([l for l in leads if l.get('email')])}")
            
            # Email Summary
            lines.append(f"\n📧 EMAIL DISCOVERY:")
            lines.append(f"   ✅ Contactable Emails: {len(all_emails)}")
            
            # Top prospects
            if contactable_emails:
                lines.append(f"\n🚀 TOP PROSPECTS FOR OUTREACH:")
                sorted_contacts = sorted(contactable_emails, key=lambda x: x['followers'], reverse=True)[:5]
                for i, contact in enumerate(sorted_contacts, 1):
                    name = contact['name']
                    company = f" @ {contact['company']}" if contact['company'] else ""
                    followers = contact['followers']
                    lines.append(f"    {i}. {name}{company} • {followers} followers")
                    lines.append(f"       📧 {contact['email']}")
            
            # Email list
            if all_emails:
                lines.append(f"\n📧 DISTINCT EMAIL ADDRESSES ({len(all_emails)} total):")
                for i, email in enumerate(sorted(all_emails), 1):
                    lines.append(f"    {i}. {email}")
                
                lines.append(f"\n📋 COPY-PASTE FORMAT:")
                lines.append(f"   {', '.join(sorted(all_emails))}")
            
            lines.append("="*60)
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            return f"Summary generation failed: {e}"


class MemoryEventStore:
    """Stores events in memory for later retrieval"""
    
    def __init__(self):
        self.events: Dict[str, List[JobEvent]] = {}
        
    def emit(self, event: JobEvent) -> None:
        """Store event"""
        if event.job_id not in self.events:
            self.events[event.job_id] = []
        self.events[event.job_id].append(event)
    
    def get_events(self, job_id: str) -> List[JobEvent]:
        """Get all events for a job"""
        return self.events.get(job_id, [])
