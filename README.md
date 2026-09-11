# Sol Video Factory — v0.2

Editor privado para combinar gravações e exportar MP4s. A V1 foi preservada em `legacy/v1/` e no histórico. A nova implementação usa interface estática, FastAPI, SQLite e FFmpeg no servidor, sem depender de credenciais de IA para a edição básica.

## Situação da entrega

- Workspace Render autorizado pela proprietária: **My Workspace**.
- Esta autorização NÃO aprova gastos de hospedagem.
- Código de renderização, seis templates, upload, autenticação e fila incluídos nesta branch.
- Validar o resultado dos testes desta revisão no GitHub Actions; a presença de arquivos de teste não significa que eles passaram.
- Nenhum serviço Render foi criado. Não há URL pública de produção validada.

## Fluxo implementado

1. Crie um projeto e envie abertura, conteúdo e encerramento.
2. Opcionalmente envie imagens/vídeos de apoio e música autorizada.
3. Escolha fala direta, cima/baixo, lado a lado, reação, fundo verde ou print + apresentador.
4. Configure cortes, título, assinatura, áudio e legendas SRT. Os tempos das legendas são adaptados aos cortes.
5. Exporte um vídeo leve de teste; depois gere um lote com até 50 combinações.
6. Revise os resultados e baixe MP4s individuais ou ZIP. Nada é publicado automaticamente.

O upload usa blocos de até 2 MB e pode ser retomado selecionando o mesmo arquivo. A fila e os arquivos ficam no disco do servidor. A página pode ser fechada depois de concluir o envio e registrar o lote; o servidor precisa continuar ativo. Depois de reiniciado, ele tenta retomar lotes interrompidos.

As regras de distribuição são preferências, não garantias de ausência de repetição consecutiva. A mesma sequência completa não é duplicada. A interface mostra um esboço de layout; a exportação de teste mostra o resultado real.

## Limites explícitos

- Transcrição automática: adaptador opcional faster-whisper; exige instalação e modelo. Desabilitada sem configuração. Ainda requer teste com fala real.
- Lip-sync, face tracking e remoção de fundo sem chroma: NÃO implementados.
- Chroma requer fundo de cor uniforme. Preenchimento usa recorte central, não rastreamento facial.
- Estúdio de um usuário. Sem permissões multiusuário, cobrança ou publicação social.
- Sem validação de produção, iPhone físico, HDR/HEVC ou testes de carga concluída.

## Desenvolvimento local

Python 3.13, FFmpeg/ffprobe com libx264 e libass, e fontes Liberation Sans.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
APP_ENV=local python -m server
```

Abra `http://127.0.0.1:8000`. Não exponha o modo local em rede pública. O modo local recusa clientes não locais.

## Hospedagem

`render.yaml` prepara Docker, autenticação e disco de 10 GB. A configuração é paga e não foi aplicada. O custo deve ser conferido e aprovado antes. Mantenha uma instância e um único worker Uvicorn. O processamento de vídeo ocorre em thread/fila fora da requisição HTTP; esta não é uma arquitetura para renderização distribuída.

Produção exige HTTPS, `APP_PASSWORD` (16+ caracteres), `SESSION_SECRET` (32+) e `/data` persistente. Não coloque segredos no Git. O conector Render disponível não oferece os parâmetros de disco e tem limitações na criação Docker; o Blueprint pelo painel é a rota documentada para esta configuração.

## Verificações

```sh
pip install -r requirements-dev.txt
python -m pytest -q tests
node --check studio/app.js
```

Os testes de integração usam clipes sintéticos. Leia `docs/VERIFICACAO.md` e a execução do CI vinculada à revisão antes de assumir qualquer resultado. Os testes não substituem uma validação pós-deploy.
