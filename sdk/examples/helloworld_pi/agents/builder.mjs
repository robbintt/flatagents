/**
 * Pi-agent factory for the helloworld character builder.
 *
 * This module is loaded by the pi_agent_runner.mjs bridge when the
 * Python FlatMachine executes a state that references a "pi-agent" adapter.
 *
 * The factory receives a config object from the machine YAML and must
 * return a pi-mono Agent instance (with .prompt() and .state.messages).
 */

import { Agent } from "@mariozechner/pi-agent-core";
import { getModel } from "@mariozechner/pi-ai";

/**
 * Build a pi-mono agent configured to return the next character for the
 * hello-world string-building demo.
 *
 * @param {object} config - Config from machine.yml agents.builder.config
 * @param {string} [config.provider] - LLM provider (default: "cerebras")
 * @param {string} [config.model] - Model id (default: "zai-glm-4.7")
 * @returns {Agent} Configured pi-mono Agent
 */
export async function buildAgent(config = {}) {
  const provider = config.provider || "cerebras";
  const modelId = config.model || "zai-glm-4.7";
  const model = getModel(provider, modelId);

  const agent = new Agent();
  agent.setModel(model);
  agent.setSystemPrompt(
    "You are an agent in a test-time sequential scaling. " +
    "Reply with exactly one output character in text format. " +
    "No explanation. No wrapper."
  );

  return agent;
}
