# Upgrade Examples to 0.7.0

All examples need to be updated to spec_version 0.7.0 and use model profiles for DRY configuration.

## Pattern

For each example directory:

1. **Create `config/profiles.yml`** with:
```yaml
spec: flatprofiles
spec_version: "0.7.0"

data:
  model_profiles:
    default:
      provider: cerebras
      name: zai-glm-4.6
      temperature: 0.6

  default: default
```

2. **Update all flatagent YAML files**:
   - Change `spec_version: "0.6.0"` → `spec_version: "0.7.0"`
   - Replace the entire `model:` block with just `model: default`

3. **Update all flatmachine YAML files**:
   - Change `spec_version: "0.3.0"` → `spec_version: "0.7.0"`
   - Add `profiles: ./profiles.yml` under `data:`

## Files to Update

### writer_critic/config/
- [ ] Create `profiles.yml`
- [ ] `machine.yml`: 0.3.0 → 0.7.0, add `profiles: ./profiles.yml`
- [ ] `writer.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `critic.yml`: 0.6.0 → 0.7.0, model block → `model: default`

### error_handling/config/
- [ ] Create `profiles.yml`
- [ ] `machine.yml`: 0.3.0 → 0.7.0, add `profiles: ./profiles.yml`
- [ ] `worker.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `cleanup.yml`: 0.6.0 → 0.7.0, model block → `model: default`

### mdap/config/
- [ ] Create `profiles.yml`
- [ ] `machine.yml`: 0.3.0 → 0.7.0, add `profiles: ./profiles.yml`
- [ ] `hanoi.yml`: 0.6.0 → 0.7.0, model block → `model: default`

### character_card/config/
- [ ] Create `profiles.yml`
- [ ] `machine.yml`: 0.3.0 → 0.7.0, add `profiles: ./profiles.yml`
- [ ] `responder.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `user_agent.yml`: 0.6.0 → 0.7.0, model block → `model: default`

### story_writer/config/
- [ ] Create `profiles.yml`
- [ ] `machine.yml`: 0.3.0 → 0.7.0, add `profiles: ./profiles.yml`
- [ ] `chapter_machine.yml`: 0.3.0 → 0.7.0, add `profiles: ./profiles.yml`
- [ ] `critic.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `drafter.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `outliner.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `reviser.yml`: 0.6.0 → 0.7.0, model block → `model: default`

### dynamic_agent/config/
- [ ] Create `profiles.yml`
- [ ] `machine.yml`: 0.3.0 → 0.7.0, add `profiles: ./profiles.yml`
- [ ] `generator.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `supervisor.yml`: 0.6.0 → 0.7.0, model block → `model: default`

### research_paper_analysis/config/
- [ ] Create `profiles.yml`
- [ ] `machine.yml`: 0.3.0 → 0.7.0, add `profiles: ./profiles.yml`
- [ ] `analyzer_machine.yml`: 0.3.0 → 0.7.0, add `profiles: ./profiles.yml`
- [ ] `refiner_machine.yml`: 0.3.0 → 0.7.0, add `profiles: ./profiles.yml`
- [ ] `abstract_analyzer.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `critic.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `formatter.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `section_analyzer.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `synthesizer.yml`: 0.6.0 → 0.7.0, model block → `model: default`

### multi_paper_synthesizer/config/
- [ ] Create `profiles.yml`
- [ ] `machine.yml`: 0.3.0 → 0.7.0, add `profiles: ./profiles.yml`
- [ ] `comparator.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `critic.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `formatter.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `gap_finder.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `synthesizer.yml`: 0.6.0 → 0.7.0, model block → `model: default`

### multi_paper_synthesizer/paper_analyzer/config/
- [ ] Create `profiles.yml`
- [ ] `machine.yml`: 0.3.0 → 0.7.0, add `profiles: ./profiles.yml`
- [ ] `analyzer_machine.yml`: 0.3.0 → 0.7.0, add `profiles: ./profiles.yml`
- [ ] `refiner_machine.yml`: 0.3.0 → 0.7.0, add `profiles: ./profiles.yml`
- [ ] `abstract_analyzer.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `critic.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `formatter.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `section_analyzer.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `synthesizer.yml`: 0.6.0 → 0.7.0, model block → `model: default`

### gepa_self_optimizer/config/agents/
- [ ] Create `../profiles.yml` (in config/)
- [ ] `reflective_updater.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `judge.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `summary_generator.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `task_generator.yml`: 0.6.0 → 0.7.0, model block → `model: default`
- [ ] `response_generator.yml`: 0.6.0 → 0.7.0, model block → `model: default`

Note: `gepa_self_optimizer/output/optimized_judge.yml` is generated output - may not need updating.

## Example Transformations

### Flatagent before:
```yaml
spec: flatagent
spec_version: "0.6.0"

data:
  name: writer
  model:
    provider: cerebras
    name: zai-glm-4.6
    temperature: 0.6
  system: You write short, punchy marketing copy.
  ...
```

### Flatagent after:
```yaml
spec: flatagent
spec_version: "0.7.0"

data:
  name: writer
  model: default
  system: You write short, punchy marketing copy.
  ...
```

### Flatmachine before:
```yaml
spec: flatmachine
spec_version: "0.3.0"

data:
  name: writer-critic-loop
  context:
    ...
  agents:
    writer: ./writer.yml
    ...
```

### Flatmachine after:
```yaml
spec: flatmachine
spec_version: "0.7.0"

data:
  name: writer-critic-loop
  profiles: ./profiles.yml
  context:
    ...
  agents:
    writer: ./writer.yml
    ...
```
