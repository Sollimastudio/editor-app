# Verificação da entrega V0.2

## Executado no ambiente de desenvolvimento

- Python 3.13, FastAPI 0.128.2, Uvicorn 0.48.0, Pydantic 2.13.4, FFmpeg/ffprobe 7.1.5.
- 18 testes automatizados passaram: planejamento, limites, determinismo, distribuição, legendas/cortes, dimensões, validação de paths, persistência, autenticação, cookies e proteção de requisições.
- Teste HTTP real: 5 aberturas + 3 conteúdos + 5 encerramentos; 75 possibilidades; lote de 15 sequências únicas exportado para 15 MP4s e ZIP.
- Seis templates exportados, com teste Full HD 1080×1920 e demais amostras em 360×640.
- Chroma real: fundo verde de uma gravação de teste substituído por vídeo azul; pixel verificado como RGB (0,0,254).
- Fontes em resoluções/proporções diferentes e 24 fps foram normalizadas; fontes sem áudio receberam trilha silenciosa; música e vídeo de fundo foram repetidos até a duração do resultado.
- Arquivo playlist malicioso disfarçado de MP4 foi rejeitado na validação.
- Node verificou a sintaxe do JavaScript.
- Interface renderizada e testada em Chromium, em 1440 px e 390 px: seis templates, navegação e zero erros de JavaScript/overflow horizontal.

## Limite do teste de navegador

A política do Chromium deste ambiente bloqueia navegação por URL, inclusive localhost. Não foi alterada. A checagem visual usou a interface real em modo offline com respostas locais de teste. O fluxo real da API foi exercitado separadamente por HTTP. Portanto, não foi feito E2E de navegador contra serviço publicado, nem teste em iPhone físico.

## Não verificado / não entregue como ativo

- Publicação em hospedagem: bloqueada por conexão/capacidade de deploy. Não há URL de produção validada.
- Build do container e comportamento no plano de hospedagem escolhido.
- Transcrição faster-whisper com modelo instalado, latência/custo e acurácia de fala real.
- Sincronização labial, recorte de fundo sem chroma, face tracking.
- Gravações longas, HDR/HEVC reais de iPhone, carga prolongada e múltiplos usuários.

## Critério para chamar produção de concluída

Conectar e autorizar a hospedagem, aprovar os custos, provisionar disco e segredos, publicar, validar login pelo iPhone, enviar uma gravação real, exportar uma prévia e um lote, reiniciar o serviço e comprovar persistência. Nenhum teste local substitui essas verificações.
