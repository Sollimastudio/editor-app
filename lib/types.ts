export type ClipKind = "hook" | "body" | "cta";

export type MediaClip = {
  id: string;
  kind: ClipKind;
  name: string;
  durationMs?: number;
  sourceUrl?: string;
};

export type GenerationRules = {
  count: number;
  seed?: number;
  avoidConsecutiveHook?: boolean;
  avoidConsecutiveBody?: boolean;
  avoidConsecutiveCta?: boolean;
  maxHookUses?: number;
  maxBodyUses?: number;
  maxCtaUses?: number;
};

export type EditPreset = {
  aspectRatio: "9:16";
  trimSilence: boolean;
  autoCaptions: boolean;
  normalizeAudio: boolean;
  smartCrop: boolean;
  smartZoom: boolean;
  transitions: "none" | "clean" | "dynamic";
  captionStyle: "clean" | "bold" | "karaoke";
};

export type VideoVariation = {
  id: string;
  hook: MediaClip;
  body: MediaClip;
  cta: MediaClip;
  sequenceKey: string;
  diversityScore: number;
};

export const DEFAULT_EDIT_PRESET: EditPreset = {
  aspectRatio: "9:16",
  trimSilence: true,
  autoCaptions: true,
  normalizeAudio: true,
  smartCrop: true,
  smartZoom: true,
  transitions: "clean",
  captionStyle: "bold",
};
