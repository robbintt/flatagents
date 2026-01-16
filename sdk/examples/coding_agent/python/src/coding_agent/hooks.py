"""
Coding Agent Hooks

Human-in-the-loop hooks for plan and result review.
Preserves history on rejection so agents can learn from feedback.
"""

from typing import Any, Dict, List
from flatagents import MachineHooks


class CodingAgentHooks(MachineHooks):
    """
    Hooks for human-in-the-loop coding workflow.
    
    Provides:
    - explore_codebase: Gather context about the working directory
    - human_review_plan: Display plan and get approval/feedback
    - human_review_result: Display changes and get approval/feedback
    
    On rejection, preserves the rejected work in history so agents
    can learn from human feedback.
    """
    
    def on_action(self, action_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Route actions to their handlers."""
        handlers = {
            "explore_codebase": self._explore_codebase,
            "human_review_plan": self._human_review_plan,
            "human_review_result": self._human_review_result,
            "apply_changes": self._apply_changes,
        }
        handler = handlers.get(action_name)
        if handler:
            return handler(context)
        return context
    
    def _explore_codebase(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gather context about the codebase.
        
        For now, this is a simple tree + README reader.
        TODO: Integrate with codebase_explorer skill or MCP filesystem.
        """
        import subprocess
        from pathlib import Path
        
        working_dir = context.get("working_dir", ".")
        path = Path(working_dir).expanduser().resolve()
        
        context_parts = []
        
        # Get directory structure
        try:
            result = subprocess.run(
                ["tree", "-L", "3", "-I", "__pycache__|node_modules|.git|.venv|*.pyc"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                context_parts.append(f"## Directory Structure\n```\n{result.stdout}\n```")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # tree not available, use ls
            try:
                result = subprocess.run(
                    ["ls", "-la"],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                context_parts.append(f"## Files\n```\n{result.stdout}\n```")
            except Exception:
                context_parts.append(f"## Working Directory\n{path}")
        
        # Look for README
        for readme_name in ["README.md", "README.txt", "README"]:
            readme_path = path / readme_name
            if readme_path.exists():
                try:
                    content = readme_path.read_text()[:2000]  # Limit size
                    context_parts.append(f"## {readme_name}\n{content}")
                    break
                except Exception:
                    pass
        
        context["codebase_context"] = "\n\n".join(context_parts) or f"Working directory: {path}"
        return context
    
    def _human_review_plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Display the plan and get human approval or feedback.
        
        On rejection, saves the plan to history with feedback so
        the planner can learn from it.
        """
        plan_raw = context.get("plan", "")
        
        # FlatAgent wraps text in {'content': ...} - extract it
        if isinstance(plan_raw, dict) and 'content' in plan_raw:
            plan = plan_raw['content']
        else:
            plan = plan_raw
        
        print("\n" + "=" * 70)
        print("📋 PLAN REVIEW")
        print("=" * 70)
        
        print(f"\n📝 Task: {context.get('task', 'Unknown')}\n")
        
        # Display plan as text
        if plan and str(plan).strip():
            print("-" * 70)
            lines = str(plan).split('\n')
            for line in lines[:80]:
                print(line[:120])
            if len(lines) > 80:
                print(f"\n... ({len(lines) - 80} more lines)")
            print("-" * 70)
        else:
            print("[WARNING] No plan content received")
        
        print("\n" + "-" * 70)
        response = input("Approve plan? (y/yes to approve, or enter feedback): ").strip()
        
        if response.lower() in ("y", "yes", ""):
            context["plan_approved"] = True
            context["human_feedback"] = None
            print("✅ Plan approved!")
        else:
            context["plan_approved"] = False
            context["human_feedback"] = response
            
            # Preserve rejected plan in history
            plan_history = context.get("plan_history", [])
            plan_history.append({
                "content": plan,
                "feedback": response
            })
            context["plan_history"] = plan_history
            print(f"🔄 Feedback recorded. Revising plan...")
        
        print("=" * 70 + "\n")
        return context
    
    def _human_review_result(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Display the changes and get human approval or feedback.
        
        On rejection, saves changes to history with feedback so
        the coder can learn from it.
        """
        changes_raw = context.get("changes", "")
        issues_raw = context.get("issues", "")
        review_summary_raw = context.get("review_summary", "")
        
        # FlatAgent wraps text in {'content': ...} - extract it
        if isinstance(changes_raw, dict) and 'content' in changes_raw:
            changes = changes_raw['content']
        else:
            changes = changes_raw
            
        if isinstance(issues_raw, dict) and 'content' in issues_raw:
            issues = issues_raw['content']
        else:
            issues = issues_raw
            
        if isinstance(review_summary_raw, dict) and 'content' in review_summary_raw:
            review_summary = review_summary_raw['content']
        else:
            review_summary = review_summary_raw
        
        print("\n" + "=" * 70)
        print("🔍 RESULT REVIEW")
        print("=" * 70)
        
        print(f"\n📝 Task: {context.get('task', 'Unknown')}")
        print(f"🔄 Iteration: {context.get('iteration', '?')}\n")
        
        # Display changes as text
        if changes and str(changes).strip():
            print("Proposed Changes:")
            print("-" * 70)
            lines = str(changes).split('\n')
            for line in lines[:80]:
                print(line[:120])
            if len(lines) > 80:
                print(f"\n... ({len(lines) - 80} more lines)")
            print("-" * 70)
        else:
            print("[WARNING] No changes content received")
        
        # Display reviewer findings
        if issues and str(issues).strip():
            print(f"\n📊 Reviewer Assessment:")
            lines = str(issues).split('\n')
            for line in lines[:20]:
                print(line[:120])
        
        if review_summary and str(review_summary).strip():
            print(f"\n📊 Review: {review_summary}")
        
        print("\n" + "-" * 70)
        response = input("Approve changes? (y/yes to approve, or enter feedback): ").strip()
        
        if response.lower() in ("y", "yes", ""):
            context["result_approved"] = True
            context["human_feedback"] = None
            print("✅ Changes approved!")
        else:
            context["result_approved"] = False
            context["human_feedback"] = response
            
            # Preserve rejected changes in history
            changes_history = context.get("changes_history", [])
            changes_history.append({
                "content": changes,
                "feedback": response,
                "issues": issues
            })
            context["changes_history"] = changes_history
            print(f"🔄 Feedback recorded. Revising changes...")
        
        print("=" * 70 + "\n")
        return context
    
    def _parse_diffs(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse SEARCH/REPLACE blocks into file operations.
        
        Format:
            ```language
            filepath
            <<<<<<< SEARCH
            content to find (empty for new files)
            =======
            replacement content
            >>>>>>> REPLACE
            ```
        
        Requirements:
        - SEARCH must match file content exactly (character for character)
        - Empty SEARCH section creates a new file
        - Empty REPLACE section deletes the matched content
        - Only first match is replaced per block
        - Multiple blocks can target the same file
        - Duplicate blocks (same file+search): LAST one wins
        - Files containing ``` must use ```` (quad backticks)
        - If SEARCH matches multiple locations, operation is rejected
        - Files that become empty after edits are deleted
        
        Returns:
            List of operation dicts with keys:
            - path: file path
            - action: 'create' or 'modify'
            - content: for create
            - search, replace, is_diff: for modify
        """
        import re
        
        # More flexible pattern - handles empty SEARCH for new files
        # The key fix: (.*?) between SEARCH and ======= without requiring surrounding \n
        # Quad backtick pattern
        quad_pattern = r'````([a-zA-Z]*)\n([^\n]+)\n<<<<<<< SEARCH\n?(.*?)\n?=======\n(.*?)\n>>>>>>> REPLACE\s*````'
        # Triple backtick pattern  
        triple_pattern = r'```([a-zA-Z]*)\n([^\n]+)\n<<<<<<< SEARCH\n?(.*?)\n?=======\n(.*?)\n>>>>>>> REPLACE\s*```'
        
        blocks_by_key = {}
        
        # Try quad backticks first
        for match in re.finditer(quad_pattern, text, re.DOTALL):
            filepath = match.group(2).strip()
            search_content = match.group(3)
            replace_content = match.group(4)
            key = (filepath, search_content)
            
            if not search_content.strip():
                blocks_by_key[key] = {'path': filepath, 'action': 'create', 'content': replace_content}
            else:
                blocks_by_key[key] = {'path': filepath, 'action': 'modify', 'search': search_content, 'replace': replace_content, 'is_diff': True}
        
        # Then triple backticks
        for match in re.finditer(triple_pattern, text, re.DOTALL):
            filepath = match.group(2).strip()
            search_content = match.group(3)
            replace_content = match.group(4)
            key = (filepath, search_content)
            
            if not search_content.strip():
                blocks_by_key[key] = {'path': filepath, 'action': 'create', 'content': replace_content}
            else:
                blocks_by_key[key] = {'path': filepath, 'action': 'modify', 'search': search_content, 'replace': replace_content, 'is_diff': True}
        return list(blocks_by_key.values())
    
    def _apply_search_replace(self, original: str, diff_content: str) -> str:
        """Apply SEARCH/REPLACE blocks to original content."""
        import re
        
        result = original
        
        # Find all SEARCH/REPLACE blocks
        pattern = r'<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE'
        
        for match in re.finditer(pattern, diff_content, re.DOTALL):
            search = match.group(1)
            replace = match.group(2)
            
            if search in result:
                result = result.replace(search, replace, 1)
        
        return result
    
    def _apply_changes(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply approved changes to the filesystem.
        
        Parses aider-style diff output and applies changes.
        """
        from pathlib import Path
        
        changes_raw = context.get("changes", "")
        
        # FlatAgent wraps text in {'content': ...} - extract it
        if isinstance(changes_raw, dict) and 'content' in changes_raw:
            changes = changes_raw['content']
        else:
            changes = changes_raw
            
        working_dir = context.get("working_dir", ".")
        base_path = Path(working_dir).expanduser().resolve()
        
        # Use user's actual cwd for safety check
        user_cwd = context.get("user_cwd")
        safety_base = Path(user_cwd).resolve() if user_cwd else base_path
        
        print("\n" + "=" * 70)
        print("📝 APPLYING CHANGES")
        print("=" * 70 + "\n")
        
        # Parse the raw text output
        if isinstance(changes, str) and changes.strip():
            operations = self._parse_diffs(changes)
        elif isinstance(changes, dict) and 'files' in changes:
            # Legacy JSON format fallback
            operations = changes.get('files', [])
        else:
            operations = []
        
        applied = []
        errors = []
        
        for op in operations:
            if not isinstance(op, dict):
                continue
                
            path = op.get("path", "")
            action = op.get("action", "")
            content = op.get("content", "")
            search = op.get("search", "")
            replace = op.get("replace", "")
            is_diff = op.get("is_diff", False)
            
            if not path:
                continue
            
            # Resolve path relative to working directory
            file_path = (base_path / path).resolve()
            
            # SAFETY CHECK: Ensure file is within user's actual cwd
            try:
                file_path.relative_to(safety_base)
            except ValueError:
                errors.append(f"🚫 BLOCKED: Path outside allowed directory: {path}")
                print(f"  🚫 BLOCKED: {path} (outside {safety_base})")
                continue
            
            try:
                if action == "create":
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content)
                    applied.append(f"➕ Created: {path}")
                    print(f"  ➕ Created: {path}")
                    
                elif action == "modify":
                    if file_path.exists():
                        original = file_path.read_text()
                        if is_diff and search:
                            # Count matches to detect ambiguity
                            match_count = original.count(search)
                            if match_count == 0:
                                errors.append(f"SEARCH not found in: {path}")
                                print(f"  ⚠️  SEARCH not found: {path}")
                            elif match_count > 1:
                                # Find line numbers of all matches
                                lines = original.split('\n')
                                match_lines = []
                                pos = 0
                                for i, line in enumerate(lines, 1):
                                    if search.split('\n')[0] in line:
                                        match_lines.append(i)
                                errors.append(f"Multiple matches ({match_count}) in {path} at lines: {match_lines}")
                                print(f"  ⚠️  AMBIGUOUS: {match_count} matches in {path} at lines {match_lines}")
                            else:
                                # Exactly one match - apply it
                                new_content = original.replace(search, replace, 1)
                                
                                # Delete file if it becomes empty
                                if not new_content.strip():
                                    file_path.unlink()
                                    applied.append(f"🗑️  Deleted (empty): {path}")
                                    print(f"  🗑️  Deleted (empty): {path}")
                                else:
                                    file_path.write_text(new_content)
                                    applied.append(f"✏️  Modified: {path}")
                                    print(f"  ✏️  Modified: {path}")
                        else:
                            # Full content replacement
                            file_path.write_text(content)
                            applied.append(f"✏️  Modified: {path}")
                            print(f"  ✏️  Modified: {path}")
                    else:
                        errors.append(f"File not found for modify: {path}")
                        print(f"  ⚠️  File not found: {path}")
                        
                elif action == "delete":
                    if file_path.exists():
                        file_path.unlink()
                        applied.append(f"🗑️  Deleted: {path}")
                        print(f"  🗑️  Deleted: {path}")
                    else:
                        errors.append(f"File not found for delete: {path}")
                        print(f"  ⚠️  File not found: {path}")
                else:
                    errors.append(f"Unknown action '{action}' for: {path}")
                    print(f"  ⚠️  Unknown action '{action}': {path}")
                    
            except Exception as e:
                errors.append(f"Error with {path}: {str(e)}")
                print(f"  ❌ Error: {path} - {e}")
        
        context["applied_changes"] = applied
        context["apply_errors"] = errors
        
        print(f"\n✅ Applied {len(applied)} changes")
        if errors:
            print(f"⚠️  {len(errors)} errors")
        print("=" * 70 + "\n")
        
        return context

