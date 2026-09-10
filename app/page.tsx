"use client";

import { ChangeEvent, useMemo, useState } from "react";
import type { EditPreset, MediaClip, VideoVariation } from "@/lib/types";
import { DEFAULT_EDIT_PRESET } from "@/lib/types";

type LocalClip = MediaClip & { previewUrl: string };

type BucketProps = {
  title: string;
  subtitle: string;
  kind: MediaClip["kind"];
  clips: LocalClip[];
  onAdd: (kind: MediaClip["kind"], files: FileList | null) => void;
  onRemove: (kind: MediaClip["kind"], id: string) => void;
};

function Bucket({ title, subtitle, kind, clips, onAdd, onRemove }: BucketProps) {
  const inputId = `files-${kind}`;

  return (
    <section className="bucket">
      <div className="bucketHeader">
        <div>
          <p className="eyebrow">{title}</p>
          <p className="muted">{subtitle}</p>
        </div>
        <span className="countBadge">{clips.length}</span>
      </div>

      <label className="dropzone" htmlFor={inputId}>
        <span className="plus">＋</span>
        <strong>Adicionar vídeos</strong>
        <span>Toque aqui e escolha vários de uma vez</span>
      </label>
      <input
        id={inputId}
        className="hiddenInput"
        type="file"
        accept="video/*"
        multiple
        onChange={(event: ChangeEvent<HTMLInputElement>) => {
          onAdd(kind, event.target.files);
          event.currentTarget.value = "";
        }}
      />

      {clips.length > 0 && (
        <div className="clipList">
          {clips.map((clip, index) => (
            <article className="clip" key={clip.id}>
              <video src={clip.previewUrl} muted playsInline preload="metadata" />
              <div className="clipMeta">
                <strong>{String(index + 1).padStart(2, "0")}</strong>
                <span title={clip.name}>{clip.name}</span>
              </div>
              <button
                className="iconButton"
                type="button"
                aria-label={`Remover ${clip.name}`}
                onClick={() => onRemove(kind, clip.id)}
              >
                ×
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function Toggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="toggleRow">
      <span>
        <strong>{label}</strong>
        <small>{description}</small>
      </span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  );
}

export default function Home() {
  const [hooks, setHooks] = useState<LocalClip[]>([]);
  const [bodies, setBodies] = useState<LocalClip[]>([]);
  const [ctas, setCtas] = useState<LocalClip[]>([]);
  const [count, setCount] = useState(15);
  const [seed, setSeed] = useState(20260910);
  const [preset, setPreset] = useState<EditPreset>(DEFAULT_EDIT_PRESET);
  const [variations, setVariations] = useState<VideoVariation[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const possible = useMemo(() => hooks.length * bodies.length * ctas.length, [hooks, bodies, ctas]);

  const setBucket = (kind: MediaClip["kind"], updater: (items: LocalClip[]) => LocalClip[]) => {
    if (kind === "hook") setHooks(updater);
    if (kind === "body") setBodies(updater);
    if (kind === "cta") setCtas(updater);
  };

  const addFiles = (kind: MediaClip["kind"], files: FileList | null) => {
    if (!files?.length) return;
    const additions: LocalClip[] = Array.from(files).map((file) => ({
      id: crypto.randomUUID(),
      kind,
      name: file.name,
      previewUrl: URL.createObjectURL(file),
    }));
    setBucket(kind, (items) => [...items, ...additions]);
    setVariations([]);
    setError(null);
  };

  const removeClip = (kind: MediaClip["kind"], id: string) => {
    setBucket(kind, (items) => {
      const removed = items.find((item) => item.id === id);
      if (removed) URL.revokeObjectURL(removed.previewUrl);
      return items.filter((item) => item.id !== id);
    });
    setVariations([]);
  };

  const serialize = (clip: LocalClip): MediaClip => ({
    id: clip.id,
    kind: clip.kind,
    name: clip.name,
  });

  const generate = async () => {
    setBusy(true);
    setError(null);

    try {
      const response = await fetch("/api/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hooks: hooks.map(serialize),
          bodies: bodies.map(serialize),
          ctas: ctas.map(serialize),
          rules: {
            count,
            seed,
            avoidConsecutiveHook: true,
            avoidConsecutiveBody: bodies.length > 1,
            avoidConsecutiveCta: true,
          },
        }),
      });

      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error ?? "Não consegui montar a fila.");
      setVariations(data.variations);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não consegui montar a fila.");
    } finally {
      setBusy(false);
    }
  };

  const remix = () => {
    setSeed((value) => value + 1);
    setTimeout(generate, 0);
  };

  const updatePreset = <K extends keyof EditPreset>(key: K, value: EditPreset[K]) => {
    setPreset((current) => ({ ...current, [key]: value }));
  };

  return (
    <main>
      <header className="hero">
        <div className="brandMark">VF</div>
        <div>
          <p className="eyebrow">VIDEO FACTORY</p>
          <h1>Grave uma vez. Multiplique sem enlouquecer.</h1>
          <p className="heroText">
            Adicione ganchos, miolos e CTAs. O app monta uma fila de versões diferentes e prepara a edição automática.
          </p>
        </div>
      </header>

      <section className="stats">
        <div><span>Possíveis</span><strong>{possible}</strong></div>
        <div><span>Para gerar</span><strong>{Math.min(count, possible || count)}</strong></div>
        <div><span>Formato</span><strong>9:16</strong></div>
      </section>

      <div className="bucketsGrid">
        <Bucket title="1 · GANCHOS" subtitle="Aberturas de 2–5 segundos" kind="hook" clips={hooks} onAdd={addFiles} onRemove={removeClip} />
        <Bucket title="2 · MIOLOS" subtitle="Conteúdo principal" kind="body" clips={bodies} onAdd={addFiles} onRemove={removeClip} />
        <Bucket title="3 · CTAs" subtitle="Fechamentos e chamadas" kind="cta" clips={ctas} onAdd={addFiles} onRemove={removeClip} />
      </div>

      <section className="controlPanel">
        <div className="controlIntro">
          <p className="eyebrow">MODO SIMPLES</p>
          <h2>Quantos vídeos você quer?</h2>
          <p className="muted">O sistema distribui os clipes para evitar repetições desnecessárias.</p>
        </div>

        <div className="countControl">
          <button type="button" onClick={() => setCount((value) => Math.max(1, value - 5))}>−5</button>
          <input
            aria-label="Quantidade de vídeos"
            type="number"
            min={1}
            max={500}
            value={count}
            onChange={(event) => setCount(Math.max(1, Math.min(500, Number(event.target.value) || 1)))}
          />
          <button type="button" onClick={() => setCount((value) => Math.min(500, value + 5))}>+5</button>
        </div>
      </section>

      <section className="editorPanel">
        <div className="controlIntro">
          <p className="eyebrow">EDIÇÃO AUTOMÁTICA</p>
          <h2>Deixe o trabalho chato para a máquina.</h2>
        </div>

        <div className="togglesGrid">
          <Toggle label="Cortar silêncios" description="Remove pausas mortas" checked={preset.trimSilence} onChange={(v) => updatePreset("trimSilence", v)} />
          <Toggle label="Legendas automáticas" description="Texto pronto para vídeo curto" checked={preset.autoCaptions} onChange={(v) => updatePreset("autoCaptions", v)} />
          <Toggle label="Normalizar áudio" description="Equilibra o volume entre trechos" checked={preset.normalizeAudio} onChange={(v) => updatePreset("normalizeAudio", v)} />
          <Toggle label="Enquadramento inteligente" description="Mantém o rosto no quadro 9:16" checked={preset.smartCrop} onChange={(v) => updatePreset("smartCrop", v)} />
          <Toggle label="Zoom inteligente" description="Movimento leve sem efeito parque de diversões" checked={preset.smartZoom} onChange={(v) => updatePreset("smartZoom", v)} />
        </div>
      </section>

      <section className="actionCard">
        <button className="primaryButton" type="button" disabled={busy} onClick={generate}>
          {busy ? "Montando a fila…" : `✨ Gerar ${count} variações`}
        </button>
        <span>Combinações únicas · distribuição equilibrada · sem sequência repetitiva</span>
        {error && <p className="error">{error}</p>}
      </section>

      {variations.length > 0 && (
        <section className="results">
          <div className="resultsHeader">
            <div>
              <p className="eyebrow">FILA PRONTA</p>
              <h2>{variations.length} vídeos planejados</h2>
            </div>
            <button type="button" className="secondaryButton" onClick={remix}>🎲 Remixar</button>
          </div>

          <div className="variationList">
            {variations.map((variation, index) => (
              <article className="variation" key={variation.id}>
                <span className="variationNumber">{String(index + 1).padStart(2, "0")}</span>
                <div><small>GANCHO</small><strong>{variation.hook.name}</strong></div>
                <span className="arrow">→</span>
                <div><small>MIOLO</small><strong>{variation.body.name}</strong></div>
                <span className="arrow">→</span>
                <div><small>CTA</small><strong>{variation.cta.name}</strong></div>
              </article>
            ))}
          </div>

          <div className="renderNotice">
            <strong>Próxima camada: render real.</strong>
            <span>Essa fila será enviada ao worker Remotion + FFmpeg para cortar, legendar, enquadrar e exportar os MP4.</span>
          </div>
        </section>
      )}

      <footer>
        <strong>Video Factory · V1</strong>
        <span>Interface simples por fora. Engenharia séria por dentro.</span>
      </footer>
    </main>
  );
}
