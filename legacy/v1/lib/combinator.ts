import type { GenerationRules, MediaClip, VideoVariation } from "@/lib/types";

type Candidate = {
  hook: MediaClip;
  body: MediaClip;
  cta: MediaClip;
  sequenceKey: string;
};

type Usage = Record<string, number>;

const getCount = (usage: Usage, id: string) => usage[id] ?? 0;

const inc = (usage: Usage, id: string) => {
  usage[id] = getCount(usage, id) + 1;
};

function mulberry32(seed: number) {
  let t = seed >>> 0;
  return () => {
    t += 0x6d2b79f5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffle<T>(items: T[], random: () => number) {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function buildCandidates(hooks: MediaClip[], bodies: MediaClip[], ctas: MediaClip[]) {
  const candidates: Candidate[] = [];
  for (const hook of hooks) {
    for (const body of bodies) {
      for (const cta of ctas) {
        candidates.push({
          hook,
          body,
          cta,
          sequenceKey: `${hook.id}::${body.id}::${cta.id}`,
        });
      }
    }
  }
  return candidates;
}

function exceedsMax(candidate: Candidate, rules: GenerationRules, usage: {
  hook: Usage;
  body: Usage;
  cta: Usage;
}) {
  if (rules.maxHookUses && getCount(usage.hook, candidate.hook.id) >= rules.maxHookUses) return true;
  if (rules.maxBodyUses && getCount(usage.body, candidate.body.id) >= rules.maxBodyUses) return true;
  if (rules.maxCtaUses && getCount(usage.cta, candidate.cta.id) >= rules.maxCtaUses) return true;
  return false;
}

function scoreCandidate(
  candidate: Candidate,
  previous: Candidate | undefined,
  usage: { hook: Usage; body: Usage; cta: Usage },
  rules: GenerationRules,
  random: () => number,
) {
  let score = 100;

  // Prefer clips that have been used less often.
  score -= getCount(usage.hook, candidate.hook.id) * 14;
  score -= getCount(usage.body, candidate.body.id) * 10;
  score -= getCount(usage.cta, candidate.cta.id) * 14;

  if (previous) {
    if (candidate.hook.id === previous.hook.id) {
      score -= rules.avoidConsecutiveHook ? 1000 : 24;
    }
    if (candidate.body.id === previous.body.id) {
      score -= rules.avoidConsecutiveBody ? 1000 : 18;
    }
    if (candidate.cta.id === previous.cta.id) {
      score -= rules.avoidConsecutiveCta ? 1000 : 24;
    }
  }

  // Tiny deterministic jitter prevents ties from always favoring list order.
  score += random() * 3;
  return score;
}

export function generateVideoVariations(input: {
  hooks: MediaClip[];
  bodies: MediaClip[];
  ctas: MediaClip[];
  rules: GenerationRules;
}): VideoVariation[] {
  const { hooks, bodies, ctas, rules } = input;

  if (!hooks.length || !bodies.length || !ctas.length) {
    throw new Error("Adicione pelo menos 1 gancho, 1 miolo e 1 CTA.");
  }

  const requested = Math.max(1, Math.floor(rules.count));
  const random = mulberry32(rules.seed ?? Date.now());
  const pool = shuffle(buildCandidates(hooks, bodies, ctas), random);
  const target = Math.min(requested, pool.length);

  const usage = {
    hook: {} as Usage,
    body: {} as Usage,
    cta: {} as Usage,
  };

  const selected: VideoVariation[] = [];
  const remaining = [...pool];

  while (selected.length < target && remaining.length) {
    const previous = selected.length
      ? {
          hook: selected[selected.length - 1].hook,
          body: selected[selected.length - 1].body,
          cta: selected[selected.length - 1].cta,
          sequenceKey: selected[selected.length - 1].sequenceKey,
        }
      : undefined;

    const eligible = remaining.filter((candidate) => !exceedsMax(candidate, rules, usage));
    if (!eligible.length) break;

    let best = eligible[0];
    let bestScore = Number.NEGATIVE_INFINITY;

    for (const candidate of eligible) {
      const score = scoreCandidate(candidate, previous, usage, rules, random);
      if (score > bestScore) {
        best = candidate;
        bestScore = score;
      }
    }

    inc(usage.hook, best.hook.id);
    inc(usage.body, best.body.id);
    inc(usage.cta, best.cta.id);

    selected.push({
      id: `variation-${String(selected.length + 1).padStart(3, "0")}`,
      hook: best.hook,
      body: best.body,
      cta: best.cta,
      sequenceKey: best.sequenceKey,
      diversityScore: Math.round(bestScore),
    });

    const index = remaining.findIndex((candidate) => candidate.sequenceKey === best.sequenceKey);
    remaining.splice(index, 1);
  }

  if (selected.length < target) {
    throw new Error(
      `As regras atuais permitem apenas ${selected.length} combinações. Aumente os limites de repetição ou reduza a quantidade.`,
    );
  }

  return selected;
}
