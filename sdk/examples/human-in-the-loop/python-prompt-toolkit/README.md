# Human-in-the-Loop Example (prompt_toolkit)

A simple example demonstrating human-in-the-loop workflows with flatmachines, using [prompt_toolkit](https://python-prompt-toolkit.readthedocs.io/) for enhanced terminal input.

## Why prompt_toolkit?

This example uses `prompt_toolkit` instead of Python's built-in `input()` for several advantages:

- **Multiline support**: Enter complex feedback spanning multiple lines
- **Control code handling**: Proper support for Ctrl+C, arrow keys, and other control sequences
- **Editing capabilities**: Full line editing with history support
- **Future-proof**: prompt_toolkit powers IPython and has been actively maintained for years
- **Cross-platform**: Works consistently across Windows, macOS, and Linux

## Overview

This example shows how to:
1. Pause machine execution for human input
2. Incorporate human feedback into agent revisions
3. Allow humans to approve or request changes

## Flow

```
┌─────────────────┐
│      start      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  generate_draft │◄──────────┐
└────────┬────────┘           │
         │                    │
         ▼                    │ feedback
┌─────────────────┐           │
│ await_human_    │───────────┘
│    review       │
└────────┬────────┘
         │ approved
         ▼
┌─────────────────┐
│      done       │
└─────────────────┘
```

## Usage

```bash
cd sdk/examples/human-in-the-loop/python-prompt-toolkit

# Run with default topic
./run.sh

# Run with a custom topic
./run.sh --topic "Benefits of remote work"

# With custom max revisions
./run.sh --topic "AI in healthcare" --max-revisions 5

# Use local SDK development version
./run.sh --local --topic "My topic"
```

## Key Concepts

### Hook Actions

The `await_human_review` state uses a hook action:

```yaml
await_human_review:
  action: human_review  # Triggers HumanInLoopHooks.on_action()
  transitions:
    - condition: "context.human_approved == true"
      to: done
```

### The Hook with prompt_toolkit

```python
from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style

class HumanInLoopHooks(MachineHooks):
    def on_action(self, action_name: str, context: Dict) -> Dict:
        if action_name == "human_review":
            # Display draft
            print(context.get("draft", ""))
            
            # Get input with prompt_toolkit
            response = prompt(
                HTML('<prompt>Your response: </prompt>'),
                multiline=False,
            ).strip()
            
            # Process response
            if response.lower() in ("y", "yes", ""):
                context["human_approved"] = True
            else:
                context["human_approved"] = False
                context["human_feedback"] = response
        return context
```

### Input Handling

- **Single line**: Just type and press Enter
- **Multiline**: Use Meta+Enter (Alt+Enter) or Esc followed by Enter to submit
- **Cancel**: Ctrl+C gracefully cancels and auto-approves
- **Edit**: Use arrow keys to navigate, standard editing shortcuts work

## Extending This Example

- **Custom styling**: Modify the `STYLE` dict to change prompt appearance
- **Autocompletion**: Add completers for common feedback patterns
- **History**: Add persistent history across sessions
- **Syntax highlighting**: Highlight markdown or code in drafts
- **Web UI**: Replace prompt_toolkit with a web endpoint
- **Async Approval**: Store pending reviews in a database
