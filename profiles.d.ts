/**
 * FlatAgents Model Profiles Schema
 * =================================
 *
 * Model profiles provide reusable model configurations that agents can reference
 * by name. This enables centralized model management and easy switching between
 * configurations (e.g., development vs production, fast vs quality).
 *
 * STRUCTURE:
 * ----------
 * spec           - Fixed string "flatprofiles"
 * spec_version   - Semver string
 * data           - Profile definitions and settings
 * metadata       - Extensibility layer
 *
 * DERIVED SCHEMAS:
 * ----------------
 * This file (/profiles.d.ts) is the SOURCE OF TRUTH for all profile schemas.
 * Other schemas (JSON Schema, etc.) are DERIVED from this file using scripts.
 * See: /scripts/generate-spec-assets.ts
 *
 * PROFILE RESOLUTION ORDER (low to high priority):
 * ------------------------------------------------
 * 1. default profile from profiles.yml (fallback when agent has no model config)
 * 2. Named profile from agent's model: "profile-name"
 * 3. Inline overrides from agent's model: { profile: "name", temperature: 0.5 }
 * 4. override profile from profiles.yml (trumps all agent configs)
 *
 * AGENT USAGE:
 * ------------
 * String shorthand - profile lookup:
 *
 *   data:
 *     model: "fast-cheap"
 *
 * Profile with overrides:
 *
 *   data:
 *     model:
 *       profile: "fast-cheap"
 *       temperature: 0.9
 *
 * Inline config (no profile):
 *
 *   data:
 *     model:
 *       provider: cerebras
 *       name: zai-glm-4.6
 *       temperature: 0.6
 *
 * EXAMPLE CONFIGURATION:
 * ----------------------
 *
 *   spec: flatprofiles
 *   spec_version: "0.1.0"
 *
 *   data:
 *     model_profiles:
 *       fast-cheap:
 *         provider: cerebras
 *         name: zai-glm-4.6
 *         temperature: 0.6
 *         max_tokens: 2048
 *
 *       smart-expensive:
 *         provider: anthropic
 *         name: claude-3-opus-20240229
 *         temperature: 0.3
 *         max_tokens: 4096
 *
 *       local-dev:
 *         provider: ollama
 *         name: llama3
 *         base_url: http://localhost:11434
 *         temperature: 0.7
 *
 *       deterministic:
 *         provider: openai
 *         name: gpt-4-turbo
 *         temperature: 0
 *         seed: 42
 *
 *     default: fast-cheap
 *     # override: smart-expensive
 *
 *   metadata:
 *     description: "Model profiles for the project"
 */

export const SPEC_VERSION = "0.1.0";

export interface ProfilesWrapper {
  spec: "flatprofiles";
  spec_version: string;
  data: ProfilesData;
  metadata?: Record<string, any>;
}

export interface ProfilesData {
  /** Named model profiles, keyed by profile name */
  model_profiles: Record<string, ModelProfileConfig>;

  /** Default profile name - used when agent has no model config */
  default?: string;

  /** Override profile name - trumps all agent model configs */
  override?: string;
}

/**
 * Model profile configuration.
 * Defines all parameters for an LLM model.
 */
export interface ModelProfileConfig {
  /** Model name (e.g., "gpt-4", "zai-glm-4.6", "claude-3-opus-20240229") */
  name: string;

  /** Provider name (e.g., "openai", "anthropic", "cerebras", "ollama") */
  provider?: string;

  /** Sampling temperature (0.0 to 2.0) */
  temperature?: number;

  /** Maximum tokens to generate */
  max_tokens?: number;

  /** Nucleus sampling parameter (0.0 to 1.0) */
  top_p?: number;

  /** Top-k sampling parameter */
  top_k?: number;

  /** Frequency penalty (-2.0 to 2.0) */
  frequency_penalty?: number;

  /** Presence penalty (-2.0 to 2.0) */
  presence_penalty?: number;

  /** Random seed for reproducibility */
  seed?: number;

  /** Custom base URL for the API (e.g., for local models or proxies) */
  base_url?: string;
}

export type FlatprofilesConfig = ProfilesWrapper;
