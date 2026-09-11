import type { EditPreset, VideoVariation } from "@/lib/types";

export type RenderStage =
  | "ingest"
  | "analyze"
  | "trim"
  | "transcribe"
  | "reframe"
  | "lip-sync"
  | "compose"
  | "render"
  | "publish";

export type RenderStageState = "pending" | "running" | "done" | "skipped" | "failed";

export type LipSyncMode = "off" | "fast" | "premium";

export type LipSyncConsent = {
  subject: "self" | "consenting-adult";
  confirmed: boolean;
};

export type RenderJob = {
  id: string;
  variation: VideoVariation;
  preset: EditPreset;
  lipSync: {
    mode: LipSyncMode;
    consent?: LipSyncConsent;
  };
  stages: Array<{
    name: RenderStage;
    state: RenderStageState;
  }>;
};

const BASE_STAGES: RenderStage[] = [
  "ingest",
  "analyze",
  "trim",
  "transcribe",
  "reframe",
  "lip-sync",
  "compose",
  "render",
  "publish",
];

export function validateLipSync(input: RenderJob["lipSync"]) {
  if (input.mode === "off") return;

  if (!input.consent?.confirmed) {
    throw new Error("Confirme que o rosto é seu ou de um adulto que autorizou a alteração.");
  }

  if (input.consent.subject !== "self" && input.consent.subject !== "consenting-adult") {
    throw new Error("Sincronização labial só está disponível para uso próprio ou com consentimento.");
  }
}

export function createRenderJob(input: {
  variation: VideoVariation;
  preset: EditPreset;
  lipSyncMode?: LipSyncMode;
  consent?: LipSyncConsent;
}): RenderJob {
  const lipSync = {
    mode: input.lipSyncMode ?? "off",
    consent: input.consent,
  } satisfies RenderJob["lipSync"];

  validateLipSync(lipSync);

  return {
    id: crypto.randomUUID(),
    variation: input.variation,
    preset: input.preset,
    lipSync,
    stages: BASE_STAGES.map((name) => ({
      name,
      state:
        (name === "trim" && !input.preset.trimSilence) ||
        (name === "transcribe" && !input.preset.autoCaptions) ||
        (name === "reframe" && !input.preset.smartCrop) ||
        (name === "lip-sync" && lipSync.mode === "off")
          ? "skipped"
          : "pending",
    })),
  };
}

export const RENDER_PIPELINE_NOTES: Record<RenderStage, string> = {
  ingest: "Valida arquivo, codec, duração e resolução.",
  analyze: "Detecta fala, cenas, rosto e trechos úteis.",
  trim: "Remove pausas mortas sem cortar palavras.",
  transcribe: "Gera timestamps de fala para legendas precisas.",
  reframe: "Mantém rosto/assunto dentro do quadro vertical.",
  "lip-sync": "Opcional: sincroniza boca e áudio em worker GPU consentido.",
  compose: "Aplica legendas, zoom, transições, logo e preset visual.",
  render: "Renderiza MP4 H.264/AAC em 1080x1920.",
  publish: "Salva o resultado e disponibiliza download/galeria.",
};
