#!/usr/bin/env node
import { FlatMachine, MachineHooks } from '@memgrafter/flatagents';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = join(__dirname, '..', '..', '..');
const configDir = join(rootDir, 'config');
const maxAgentCalls = 20;

class HelloWorldHooks implements MachineHooks {
  private agentCalls = 0;

  onStateEnter(state: string, context: Record<string, any>) {
    if (state === 'build_char') {
      this.agentCalls += 1;
      if (this.agentCalls > maxAgentCalls) {
        throw new Error(`Max agent calls exceeded (${maxAgentCalls})`);
      }
    }
    return context;
  }

  onStateExit(state: string, context: Record<string, any>, output: any) {
    if (state === 'build_char' && output !== undefined && output !== null) {
      const nextChar =
        typeof output === 'string' ? output : (output.next_char ?? output.content);
      if (nextChar !== undefined && nextChar !== null) {
        const current = context.current ?? '';
        const expected = context.expected_char;
        const status = expected !== undefined && nextChar === expected ? 'match' : 'mismatch';
        console.log(`${current}${nextChar} (${status})`);
      }
    }
    return output;
  }

  onAction(action: string, context: Record<string, any>) {
    if (action === 'append_char') {
      const lastOutput = context.last_output ?? '';
      context.current = (context.current ?? '') + lastOutput;
    }
    return context;
  }
}

function collectStats(machine: FlatMachine): { totalCost: number; totalApiCalls: number } {
  const internal = machine as any;
  const agents: Map<string, any> | undefined = internal.agents;
  let totalCost = 0;
  let totalApiCalls = 0;
  if (agents instanceof Map) {
    for (const agent of agents.values()) {
      const backend = agent?.llmBackend;
      if (backend) {
        totalCost += backend.totalCost ?? 0;
        totalApiCalls += backend.totalApiCalls ?? 0;
      }
    }
  }
  return { totalCost, totalApiCalls };
}

async function main() {
  console.log('--- Starting FlatMachine HelloWorld Demo ---');

  const machine = new FlatMachine({
    config: join(configDir, 'machine.yml'),
    configDir,
    hooks: new HelloWorldHooks(),
  });

  console.log(`Machine: ${machine.config?.data?.name ?? 'unknown'}`);
  console.log(`States: ${Object.keys(machine.config?.data?.states ?? {})}`);

  const target = 'Hello, World!';
  console.log(`Target: '${target}'`);
  console.log('Building character by character...');

  try {
    const result = await machine.execute({ target });

    console.log('--- Execution Complete ---');
    console.log(`Final: '${result?.result ?? ''}'`);

    if (result?.success) {
      console.log('Success! The machine built the string correctly.');
    } else {
      console.warn('Failure. The machine did not build the string correctly.');
    }

    const stats = collectStats(machine);
    console.log('--- Execution Statistics ---');
    console.log(`Total Cost: $${stats.totalCost.toFixed(4)}`);
    console.log(`Total API Calls: ${stats.totalApiCalls}`);
  } catch (error) {
    console.error('Error:', error);
  }
}

main();
