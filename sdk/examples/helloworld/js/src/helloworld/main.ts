#!/usr/bin/env node
import { FlatMachine, MachineHooks } from '@memgrafter/flatagents';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { readFileSync } from 'fs';
import { parse } from 'yaml';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = join(__dirname, '..', '..', '..');
const configDir = join(rootDir, 'config');

// Load profiles to show which provider is being used
function getDefaultProfile(): { provider: string; name: string } {
  try {
    const profilesPath = join(configDir, 'profiles.yml');
    const profilesYaml = readFileSync(profilesPath, 'utf-8');
    const profiles = parse(profilesYaml);
    const defaultName = profiles.data.default;
    const profile = profiles.data.model_profiles[defaultName];
    return { provider: profile.provider, name: profile.name };
  } catch {
    return { provider: 'unknown', name: 'unknown' };
  }
}

// Progress hooks for incremental output
class ProgressHooks implements MachineHooks {
  private stepCount = 0;
  private startTime = Date.now();
  private previousCurrent = '';

  onStateEnter(state: string, context: Record<string, any>) {
    if (state === 'build_char') {
      this.stepCount++;
      this.previousCurrent = context.current || '';
      const target = context.target || '';
      const elapsed = ((Date.now() - this.startTime) / 1000).toFixed(1);
      process.stdout.write(`\r[${elapsed}s] Step ${this.stepCount}: "${this.previousCurrent}" → "${this.previousCurrent}_" (${this.previousCurrent.length}/${target.length})`);
    }
    return context;
  }

  onStateExit(state: string, context: Record<string, any>, output: any) {
    if (state === 'build_char' && output?.next_char) {
      const newCurrent = this.previousCurrent + output.next_char;
      const target = context.target || '';
      const elapsed = ((Date.now() - this.startTime) / 1000).toFixed(1);
      process.stdout.write(`\r[${elapsed}s] Step ${this.stepCount}: "${this.previousCurrent}" → "${newCurrent}" (${newCurrent.length}/${target.length})\n`);
    }
    return output;
  }
}

async function main() {
  const profile = getDefaultProfile();
  console.log(`Provider: ${profile.provider} (${profile.name})`);

  const hooks = new ProgressHooks();
  const machine = new FlatMachine({
    config: join(configDir, 'machine.yml'),
    configDir,
    hooks,
  });

  try {
    const target = "Hello, World!";
    console.log(`Target: '${target}'`);
    console.log('Building character by character...\n');

    const result = await machine.execute({ target });

    console.log('\nResult:', JSON.stringify(result, null, 2));

    if (result?.success) {
      console.log('✅ Success! The machine built the string correctly.');
    } else {
      console.log('❌ Failure. The machine did not build the string correctly.');
    }
  } catch (error) {
    console.error('\nError:', error);
  }
}

main();
