import { NextResponse } from "next/server";
import { z } from "zod";
import { generateVideoVariations } from "@/lib/combinator";

const clipSchema = z.object({
  id: z.string().min(1),
  kind: z.enum(["hook", "body", "cta"]),
  name: z.string().min(1),
  durationMs: z.number().nonnegative().optional(),
  sourceUrl: z.string().optional(),
});

const requestSchema = z.object({
  hooks: z.array(clipSchema),
  bodies: z.array(clipSchema),
  ctas: z.array(clipSchema),
  rules: z.object({
    count: z.number().int().min(1).max(500),
    seed: z.number().int().optional(),
    avoidConsecutiveHook: z.boolean().optional(),
    avoidConsecutiveBody: z.boolean().optional(),
    avoidConsecutiveCta: z.boolean().optional(),
    maxHookUses: z.number().int().min(1).optional(),
    maxBodyUses: z.number().int().min(1).optional(),
    maxCtaUses: z.number().int().min(1).optional(),
  }),
});

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const input = requestSchema.parse(body);
    const variations = generateVideoVariations(input);

    return NextResponse.json({
      ok: true,
      total: variations.length,
      variations,
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { ok: false, error: "Dados inválidos.", details: error.issues },
        { status: 400 },
      );
    }

    const message = error instanceof Error ? error.message : "Não foi possível gerar as combinações.";
    return NextResponse.json({ ok: false, error: message }, { status: 400 });
  }
}
