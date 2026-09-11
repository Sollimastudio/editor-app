# Video Factory

Aplicativo mobile-first para multiplicar vídeos curtos a partir de blocos gravados e aplicar edição automática em lote.

## Objetivo

A pessoa grava poucos blocos uma única vez:

- **Ganchos**: aberturas curtas.
- **Miolos**: conteúdo principal.
- **CTAs**: fechamentos.

O sistema cria combinações únicas e equilibradas, evita repetições seguidas e prepara uma fila para edição/renderização automática.

Exemplo: `5 ganchos × 3 miolos × 5 CTAs = 75 combinações possíveis`.

## Estado atual — V1 em construção

Já implementado:

- Interface responsiva e simples para celular.
- Upload local de vários vídeos por categoria.
- Preview dos clipes.
- Cálculo instantâneo do número de combinações possíveis.
- Motor determinístico de combinação com diversidade.
- Regras para evitar repetição consecutiva de gancho, miolo e CTA.
- Quantidade desejada de vídeos (1–500).
- Botão **Remixar** para gerar outra distribuição.
- Preset de edição com opções para silêncios, legendas, áudio, enquadramento e zoom.
- Contrato modular do pipeline de renderização.
- Camada opcional de lip-sync com confirmação de consentimento.

Ainda não conectado nesta etapa:

- Upload persistente em nuvem.
- Transcrição real.
- Processamento FFmpeg.
- Render MP4 via worker Remotion.
- Galeria persistente de resultados.
- Worker GPU para lip-sync.

## Arquitetura planejada

```text
Celular / navegador
       │
       ▼
Next.js — interface simples
       │
       ├── Motor de combinações
       │
       ├── Upload → Storage
       │
       └── Criação de jobs
                │
                ▼
            Fila de jobs
                │
                ▼
      Worker de processamento
       ├── FFmpeg / ffprobe
       ├── detecção de fala/silêncio
       ├── transcrição com timestamps
       ├── enquadramento de rosto
       ├── lip-sync GPU (opcional)
       └── Remotion
                │
                ▼
       MP4 vertical 1080×1920
                │
                ▼
        Galeria / download
```

### Stack

- **Next.js + React + TypeScript** — aplicativo web/mobile-first.
- **Remotion 4** — composição programática, overlays, legendas e render.
- **FFmpeg** — codecs, concatenação, áudio e pré-processamento.
- **Supabase (fase de integração)** — autenticação, banco, Storage e fila/estado dos jobs.
- **Worker CPU/GPU separado** — evita processar vídeo pesado no telefone ou na função web.

## Estratégia de edição automática

O pipeline está modelado em `lib/render-pipeline.ts`:

1. `ingest` — valida arquivo, codec, duração e resolução.
2. `analyze` — detecta fala, cenas, rosto e trechos úteis.
3. `trim` — remove pausas mortas.
4. `transcribe` — cria timestamps para legendas.
5. `reframe` — mantém o assunto no quadro 9:16.
6. `lip-sync` — opcional, executado apenas em worker GPU.
7. `compose` — legendas, zoom, transições e identidade visual.
8. `render` — MP4 H.264/AAC, 1080×1920.
9. `publish` — salva e entrega o arquivo na galeria.

## Lip-sync

A arquitetura não acopla o app a um único modelo. Um adaptador poderá selecionar, por exemplo:

- **Fast** — modelo otimizado para velocidade.
- **Premium** — modelo priorizando qualidade.

Lip-sync deve rodar fora do frontend, em infraestrutura com GPU. A camada de domínio exige confirmação de que o rosto é da própria pessoa ou de um adulto que autorizou a alteração.

## Rodar localmente

Requer Node.js 22+.

```bash
npm install
npm run dev
```

Abra `http://localhost:3000`.

Verificações:

```bash
npm run typecheck
npm run lint
npm run build
```

## Próximas entregas

### Fase 2 — Render de verdade

- Storage de uploads.
- Banco de projetos/clipes/jobs.
- Fila de processamento.
- Worker FFmpeg + Remotion.
- Download de vídeos renderizados.

### Fase 3 — Editor inteligente

- Transcrição palavra por palavra.
- Remoção de silêncio orientada por fala.
- Legenda dinâmica.
- Face tracking e auto-reframe.
- Presets salvos de edição.
- Música e ducking automático.

### Fase 4 — IA de vídeo

- Lip-sync Fast/Premium.
- Controle de qualidade automático.
- Comparação A/B das variações.
- Metadados de conteúdo sintético/alterado quando aplicável.

## Princípio de produto

**Poucos botões para a pessoa. Muitas decisões automáticas por baixo.**

A interface deve continuar fácil mesmo que o motor fique mais sofisticado.
