<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary'
    disabled?: boolean
    type?: 'button' | 'submit' | 'reset'
  }>(),
  { variant: 'primary', disabled: false, type: 'button' },
)
</script>

<template>
  <button :type="type" :disabled="disabled" class="base-button" :class="variant">
    <slot />
  </button>
</template>

<style scoped>
.base-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 40px;
  padding: 8px 16px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.primary {
  background: var(--color-primary);
  color: white;
}

.secondary {
  border-color: var(--color-border);
  background: var(--color-surface);
  color: var(--color-text);
}

.base-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.base-button:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 3px;
}
</style>
