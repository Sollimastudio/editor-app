# Verificação V0.2

## Situação antes da execução

Esta revisão contém testes unitários, testes de API e testes de exportação com mídia sintética. A execução precisa ser consultada no GitHub Actions. Nenhuma afirmação de teste local ou visual anterior foi mantida sem evidência recuperável.

## Cobertura prevista

- Planejamento: 75 combinações possíveis, determinismo, limite de duração, distribuição e unicidade.
- Proteção de requisições, cookies de sessão, autenticação e inicialização segura.
- Upload em blocos, offset e finalização de mídia.
- MP4 real, seis layouts e lote de 15 saídas.
- ZIP com arquivos e manifesto.

## Ainda não validado

- Container publicado no Render e permissões reais do disco persistente.
- Interface em navegador, upload de gravação de iPhone, HDR/HEVC.
- Transcrição automática com modelo instalado.
- Carga, recuperação após reinício real e concorrência prolongada.
- Lip-sync e face tracking: não implementados.

Aprovação de custo, publicação, verificação de saúde, login, gravação real e teste de persistência continuam necessários antes de chamar a hospedagem de concluída.
