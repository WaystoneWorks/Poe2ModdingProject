<script lang="ts">
  let { percent, size = 38 }: { percent: number; size?: number } = $props();
  const r = $derived(size / 2 - 3);
  const c = $derived(2 * Math.PI * r);
</script>

<svg width={size} height={size} viewBox="0 0 {size} {size}" aria-hidden="true">
  <circle cx={size / 2} cy={size / 2} {r} fill="none" stroke="var(--surface-3)" stroke-width="3.5" />
  <circle
    cx={size / 2}
    cy={size / 2}
    {r}
    fill="none"
    stroke="var(--gold)"
    stroke-width="3.5"
    stroke-linecap="round"
    stroke-dasharray="{(Math.min(100, percent) / 100) * c} {c}"
    transform="rotate(-90 {size / 2} {size / 2})"
  />
</svg>
