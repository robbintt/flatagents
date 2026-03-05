# macOS Screen Agent Example

A screen automation agent with 5 tools — **screenshot**, **mouse_move**, **mouse_click**, **key_type**, **key_press**. The agent takes screenshots to see the screen, then controls the mouse and keyboard to accomplish goals. Includes human-in-the-loop review after each agent run.

## Tools

| Tool | Description |
|------|-------------|
| `screenshot` | Capture the entire screen as a PNG image |
| `mouse_move` | Move the cursor to (x, y) coordinates |
| `mouse_click` | Click at (x, y) — left, right, or double click |
| `key_type` | Type a string of text |
| `key_press` | Press a key or combination (e.g., `command+c`, `Return`) |

## Prerequisites

### 1. Install cliclick

[cliclick](https://github.com/BlueM/cliclick) is a macOS command-line tool for simulating mouse clicks and keyboard events.

```bash
brew install cliclick
```

### 2. Grant macOS Permissions

The agent needs two macOS permissions to function:

#### Screen Recording (for screenshots)

1. Open **System Settings** → **Privacy & Security** → **Screen Recording**
2. Click **+** and add your terminal application (e.g., Terminal, iTerm2, VS Code)
3. Toggle the switch **ON**
4. You may need to restart your terminal for the change to take effect

#### Accessibility (for mouse/keyboard control)

1. Open **System Settings** → **Privacy & Security** → **Accessibility**
2. Click **+** and add your terminal application
3. Also add **cliclick** if prompted (it may appear automatically after first use)
4. Toggle the switches **ON**

> **Note:** If you run the agent and get permission errors, macOS may prompt you to grant access. After granting, restart your terminal.

### 3. Set up an API key

The agent requires an LLM API key. Set one of:

```bash
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
```

Edit `config/profiles.yml` to change the model provider if needed.

## Quick Start

### Step 1: Navigate to the project
```bash
cd sdk/examples/mac_screen_agent/python
```

### Step 2: Run in interactive mode
```bash
./run.sh --local
```

### Step 3: Give the agent a goal
```
> open Safari and navigate to github.com
```

### Step 4: Watch the agent work
- Agent takes a screenshot to see the current screen
- Agent decides what action to take (click, type, etc.)
- Agent takes another screenshot to verify the result
- Repeats until the goal is accomplished

### Step 5: Review and approve
- Agent pauses after completing the task
- You see the results
- Press Enter to accept, or type feedback to refine
- If feedback given, agent loops back and continues

### Step 6: Repeat or exit
- Type a new goal to continue
- Press `^C` twice or `^D` to exit

## Usage Modes

```bash
cd sdk/examples/mac_screen_agent/python

# Interactive REPL (default) — best for exploration
./run.sh --local

# Single-shot mode — run one task and exit
./run.sh --local -p "take a screenshot"

# Standalone mode — no human review, runs to completion
./run.sh --local --standalone "open TextEdit and type hello world"
```

## Flow (machine mode)

```
┌─────────────────┐
│      start      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│      work       │◄──────────┐
│  (tool loop)    │           │
│  screenshot →   │           │
│  act → verify   │           │
└────────┬────────┘           │
         │                    │ feedback
         ▼                    │
┌─────────────────┐           │
│  human_review   │───────────┘
└────────┬────────┘
         │ approved
         ▼
┌─────────────────┐
│      done       │
└─────────────────┘
```

## Architecture

```
config/
  agent.yml       — Agent config with screen tool definitions
  machine.yml     — Machine with work → human_review → done loop
  profiles.yml    — Model profiles

python/src/mac_screen_agent/
  tools.py        — Tool implementations (ScreenToolProvider)
  hooks.py        — ScreenAgentHooks (tool provider, display, human review)
  main.py         — Entry point (REPL, -p single-shot, or --standalone)
```

## Troubleshooting

### "CGDisplayCreateImage returned None"
Grant Screen Recording permission to your terminal app in System Settings.

### "cliclick not found"
Install with `brew install cliclick`.

### "cliclick failed" with no useful error
Grant Accessibility permission to your terminal app and cliclick in System Settings.

### Agent clicks wrong coordinates
Screen coordinates depend on display resolution and scaling. The agent works in pixel coordinates from the top-left corner. If using Retina display, coordinates match the logical resolution (not physical pixels).

### Model doesn't support images
Make sure your model profile in `config/profiles.yml` uses a vision-capable model (e.g., `gpt-4o`, `claude-3-5-sonnet`).
