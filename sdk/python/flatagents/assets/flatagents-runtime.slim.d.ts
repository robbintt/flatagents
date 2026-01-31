export interface ExecutionLock {
    acquire(key: string): Promise<boolean>;
    release(key: string): Promise<void>;
}
export interface PersistenceBackend {
    save(key: string, snapshot: MachineSnapshot): Promise<void>;
    load(key: string): Promise<MachineSnapshot | null>;
    delete(key: string): Promise<void>;
    list(prefix: string): Promise<string[]>;
}
export interface ResultBackend {
    write(uri: string, data: any): Promise<void>;
    read(uri: string, options?: {
        block?: boolean;
        timeout?: number;
    }): Promise<any>;
    exists(uri: string): Promise<boolean>;
    delete(uri: string): Promise<void>;
}
export interface ExecutionType {
    execute<T>(fn: () => Promise<T>): Promise<T>;
}
export interface ExecutionConfig {
    type: "default" | "retry" | "parallel" | "mdap_voting";
    backoffs?: number[];
    jitter?: number;
    n_samples?: number;
    k_margin?: number;
    max_candidates?: number;
}
export interface MachineHooks {
    onMachineStart?(context: Record<string, any>): Record<string, any> | Promise<Record<string, any>>;
    onMachineEnd?(context: Record<string, any>, output: any): any | Promise<any>;
    onStateEnter?(state: string, context: Record<string, any>): Record<string, any> | Promise<Record<string, any>>;
    onStateExit?(state: string, context: Record<string, any>, output: any): any | Promise<any>;
    onTransition?(from: string, to: string, context: Record<string, any>): string | Promise<string>;
    onError?(state: string, error: Error, context: Record<string, any>): string | null | Promise<string | null>;
    onAction?(action: string, context: Record<string, any>): Record<string, any> | Promise<Record<string, any>>;
}
export interface LLMBackend {
    totalCost: number;
    totalApiCalls: number;
    call(messages: Message[], options?: LLMOptions): Promise<string>;
    callRaw(messages: Message[], options?: LLMOptions): Promise<any>;
}
export interface Message {
    role: "system" | "user" | "assistant" | "tool";
    content: string;
    tool_call_id?: string;
    tool_calls?: ToolCall[];
}
export interface ToolCall {
    id: string;
    type: "function";
    function: {
        name: string;
        arguments: string;
    };
}
export interface LLMOptions {
    temperature?: number;
    max_tokens?: number;
    tools?: ToolDefinition[];
    response_format?: {
        type: "json_object";
    } | {
        type: "text";
    };
}
export interface ToolDefinition {
    type: "function";
    function: {
        name: string;
        description?: string;
        parameters?: Record<string, any>;
    };
}
export interface MachineInvoker {
    invoke(machineName: string, input: Record<string, any>, options?: {
        timeout?: number;
    }): Promise<Record<string, any>>;
    launch(machineName: string, input: Record<string, any>): Promise<string>;
}
export interface MachineSnapshot {
    execution_id: string;
    machine_name: string;
    spec_version: string;
    current_state: string;
    context: Record<string, any>;
    step: number;
    created_at: string;
    event?: string;
    output?: Record<string, any>;
    total_api_calls?: number;
    total_cost?: number;
    parent_execution_id?: string;
    pending_launches?: LaunchIntent[];
}
export interface LaunchIntent {
    execution_id: string;
    machine: string;
    input: Record<string, any>;
    launched: boolean;
}
export interface RegistrationBackend {
    register(worker: WorkerRegistration): Promise<WorkerRecord>;
    heartbeat(worker_id: string, metadata?: Record<string, any>): Promise<void>;
    updateStatus(worker_id: string, status: string): Promise<void>;
    get(worker_id: string): Promise<WorkerRecord | null>;
    list(filter?: WorkerFilter): Promise<WorkerRecord[]>;
}
export interface WorkerRegistration {
    worker_id: string;
    host?: string;
    pid?: number;
    capabilities?: string[];
    pool_id?: string;
    started_at: string;
}
export interface WorkerRecord extends WorkerRegistration {
    status: string;
    last_heartbeat: string;
    current_task_id?: string;
}
export interface WorkerFilter {
    status?: string | string[];
    capability?: string;
    pool_id?: string;
    stale_threshold_seconds?: number;
}
export interface WorkBackend {
    pool(name: string): WorkPool;
}
export interface WorkPool {
    push(item: any, options?: {
        max_retries?: number;
    }): Promise<string>;
    claim(worker_id: string): Promise<WorkItem | null>;
    complete(item_id: string, result?: any): Promise<void>;
    fail(item_id: string, error?: string): Promise<void>;
    size(): Promise<number>;
    releaseByWorker(worker_id: string): Promise<number>;
}
export interface WorkItem {
    id: string;
    data: any;
    claimed_by?: string;
    claimed_at?: string;
    attempts: number;
    max_retries: number;
}
export interface BackendConfig {
    persistence?: "memory" | "local" | "redis" | "postgres" | "s3";
    locking?: "none" | "local" | "redis" | "consul";
    results?: "memory" | "redis";
    registration?: "memory" | "sqlite" | "redis";
    work?: "memory" | "sqlite" | "redis";
    sqlite_path?: string;
}
export const SPEC_VERSION = "0.9.0";
export interface SDKRuntimeWrapper {
    spec: "flatagents-runtime";
    spec_version: typeof SPEC_VERSION;
    execution_lock?: ExecutionLock;
    persistence_backend?: PersistenceBackend;
    result_backend?: ResultBackend;
    execution_config?: ExecutionConfig;
    machine_hooks?: MachineHooks;
    llm_backend?: LLMBackend;
    machine_invoker?: MachineInvoker;
    backend_config?: BackendConfig;
    machine_snapshot?: MachineSnapshot;
    registration_backend?: RegistrationBackend;
    work_backend?: WorkBackend;
}
