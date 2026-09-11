# Sol Video Factory — v0.2

Editor pessoal de vídeos curtos: envie aberturas, conteúdos e encerramentos, escolha um template e receba MP4s reais. A V1 era um planejador; esta versão inclui API, armazenamento, fila persistente, FFmpeg e exportação.

**Estado:** implementação testada localmente; publicação em nuvem ainda depende de conexão/autorização da hospedagem e confirmação de custos. Não existe URL pública confirmada nesta entrega. Não confundir código validado com serviço publicado.

## Funciona nesta versão

- Projetos persistentes, senha do estúdio em produção e sessão HTTP-only.
- Upload em blocos de 2 MB; retomada ao selecionar novamente o mesmo arquivo; validação de formato, duração, limites e integridade.
- Combinações únicas, seleção determinística e distribuição por uso. As regras anti-repetição são preferências, não garantias quando os arquivos disponíveis não permitem cumpri-las.
- 6 templates reais: fala direta, cima/baixo, lado a lado, sobreposição, chroma key e print + apresentador.
- Imagem ou vídeo de apoio; vídeo de fundo e música em loop.
- Cortes por tempo; remoção opcional de pausas longas; normalização de áudio; música com redução de volume durante a fala.
- Legendas SRT importadas e adaptadas aos cortes; título inicial e assinatura; zoom leve opcional.
- MP4 H.264/AAC em 360×640, 720×1280 e 1080×1920, baixável individualmente e em ZIP.
- Fila SQLite, processamento fora da requisição, cancelamento e retomada após interrupção; cache de clipes para evitar reprocessamento redundante.
- Origens preservadas. Nenhuma publicação automática em redes sociais.

## Ainda NÃO está ativo

- Transcrição automática: adaptador faster-whisper implementado, mas modelo e dependências opcionais não foram instalados/validados nesta entrega. Sem isso, a interface não permite ativar a opção.
- Sincronização labial: não implementada e não anunciada como funcional.
- Remoção de fundo sem chroma, rastreamento de rosto e corte semântico por IA.
- Contas multiusuário, compartilhamento, cobrança e publicação social. Este app é um estúdio privado de um usuário, não um SaaS multiusuário.

## Arquitetura atual

Browser → interface estática em `studio/` → API FastAPI → SQLite/arquivos privados → worker único → FFmpeg → MP4/ZIP.

O motor pesado roda no servidor, não no telefone. Não é necessário manter a página aberta depois de concluir o upload e registrar o lote. Um servidor desligado não continua renderizando; ao reiniciar, a fila retoma os lotes interrompidos.

Para estes templates, FFmpeg compõe diretamente o vídeo. Remotion, Supabase e Next.js não são dependências do fluxo executável V2. A V1 foi preservada em `legacy/v1/` no GitHub e no histórico. Essa mudança evita deixar a entrega dependente de credenciais externas ou de um renderizador ainda não implementado.

## Execução local (desenvolvimento)

Requisitos: Python 3.13, FFmpeg/ffprobe 7.1 e uma fonte sans-serif disponível.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
APP_ENV=local python -m server
```

Abra `http://127.0.0.1:8000`. O modo local não tem senha e recusa clientes não locais. Não exponha esse modo em rede pública.

## Produção

O `Dockerfile` entrega um único serviço com usuário não-root. Configure `APP_PASSWORD` (mínimo 16 caracteres), `SESSION_SECRET` (32+), HTTPS e disco persistente em `/data`. Sem os segredos, o servidor se recusa a iniciar em modo de produção.

`render.yaml` descreve uma implantação paga com disco persistente. **Não aplicar sem conferir e aprovar os custos.** O conector Render foi sugerido; nenhum serviço foi provisionado. A tentativa pelo conector Vercel falhou por divergência de argumentos no próprio conector.

Use apenas uma instância e um worker Uvicorn nesta versão. O worker de vídeos compartilha o processo do serviço, mas não a requisição HTTP. Para escala maior, separar fila/processamento e substituir arquivos locais por armazenamento de objetos.

## Uso

1. Crie um projeto e envie seus arquivos nos três espaços.
2. Para tela dividida/chroma, adicione imagem ou vídeo de apoio.
3. Escolha template e ajustes; use **Editar** em um clipe para cortar ou importar SRT.
4. Exporte um vídeo leve de teste, revise e gere o lote desejado.
5. Baixe cada MP4 ou o ZIP; faça sua revisão antes de publicar.

A interface mostra um esboço de composição, não um preview final. A exportação de teste produz o resultado real. O chroma key requer fundo de cor uniforme e boa iluminação. “Preencher” corta o centro, não acompanha rostos.

## Testes

```bash
pip install -r requirements-dev.txt
python -m pytest -q tests
node --check studio/app.js
# Com o servidor local iniciado:
TEST_OUTPUT=/tmp/vf-smoke python scripts/smoke_test.py
```

Resultados e limitações em `docs/VERIFICACAO.md`. Testes com vídeos sintéticos não substituem validação com gravações reais de iPhone, diferentes codecs e sessões prolongadas.
