export const SPEC_VERSION = "0.1.0";
export interface MachineWrapper {
    spec: "flatmachine";
    spec_version: string;
    data: MachineData;
    metadata?: Record<string, any>;
}
export interface MachineData {
    name?: string;
    expression_engine?: "simple" | "cel";
    context?: Record<string, any>;
    agents?: Record<string, string | AgentWrapper>;
    states: Record<string, StateDefinition>;
    settings?: MachineSettings;
}
export interface MachineSettings {
    hooks?: string;
    max_steps?: number;
    [key: string]: any;
}
export interface StateDefinition {
    type?: "initial" | "final";
    agent?: string;
    action?: string;
    execution?: ExecutionConfig;
    on_error?: string | Record<string, string>;
    input?: Record<string, any>;
    output_to_context?: Record<string, string>;
    output?: Record<string, any>;
    transitions?: Transition[];
    tool_loop?: boolean;
    sampling?: "single" | "multi";
}
export interface ExecutionConfig {
    type: "default" | "retry" | "parallel" | "mdap_voting";
    backoffs?: number[];
    jitter?: number;
    n_samples?: number;
    k_margin?: number;
    max_candidates?: number;
}
export interface Transition {
    condition?: string;
    to: string;
}
import { AgentWrapper, OutputSchema, ModelConfig } from "./flatagent";
export { AgentWrapper, OutputSchema };
export type FlatmachineConfig = MachineWrapper;
