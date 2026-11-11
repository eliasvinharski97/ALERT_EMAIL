# VagaRadar — vagas remotas compatíveis com seu perfil

MVP em português com **busca diária, ranking de aderência, painel web e alertas opcionais**. Não precisa pagar hospedagem ou manter seu computador ligado **depois de publicar no GitHub e ativar o Actions**. Não publica seu currículo completo nem pede senha de sites de vagas.

## O que já está pronto

- Busca nas APIs públicas **Himalayas** e **Remotive**, respeitando o crédito e os links de candidatura exigidos pelas fontes.
- API brasileira **Adzuna** opcional quando você tiver `ADZUNA_APP_ID` e `ADZUNA_APP_KEY`.
- Filtros de elegibilidade geográfica para Brasil (incluindo vagas globais), nível júnior/inicial, cargo e data da publicação.
- **Pontuação heurística de aderência**, explicando o motivo; não é análise por IA nem garantia de contratação.
- Deduplicação de anúncios já enviados entre execuções.
- E-mail por SMTP e/ou mensagem Telegram, mediante configuração das credenciais.
- Aplicativo web instalável no celular/computador quando publicado por HTTPS (PWA).
- Painel responsivo com busca, filtros, vagas salvas, candidatadas e descartadas. O status das candidaturas fica **apenas neste navegador**, não sincroniza entre dispositivos.

## Executar no seu computador

1. Instale Python 3.11+.
2. Abra o terminal na pasta do projeto e execute:

   ```bash
   python src/jobradar.py
   python -m http.server 8000
   ```

3. Abra `http://localhost:8000` para acessar o painel.

A primeira execução precisa de Internet. Não há chaves obrigatórias para Himalayas ou Remotive. Se a API bloquear ou falhar, o programa preserva o banco anterior.

## Funcionar todos os dias na nuvem (GitHub Actions)

1. Crie um **repositório privado** no GitHub (recomendado, para manter o histórico profissional menos exposto) e envie os arquivos desta pasta. Em repositório privado, o GitHub Pages pode não estar disponível gratuitamente; pode abrir o painel localmente ou optar conscientemente por um repositório público.
2. Vá em **Actions** e habilite os workflows. Abra `VagaRadar - busca diária` e clique em **Run workflow** para testar.
3. O workflow foi programado para cerca de **9h13, horário de São Paulo**, diariamente. O GitHub avisa que agendamentos podem atrasar, e repositórios públicos podem ter o agendamento desabilitado após 60 dias sem atividade.
4. Para ver o painel online: em **Settings → Pages**, selecione **GitHub Actions**. O workflow `VagaRadar - publicar painel` publica apenas o front-end, incluindo o JSON das vagas; também roda após a busca diária para atualizar o site. Confira `GUIA_PUBLICACAO.md` para o passo a passo.

**Sem configurar um canal de alerta**, o sistema apenas atualizará os dados. Para receber notificações do aplicativo, configure e-mail ou Telegram como abaixo.

## Configurar alertas por e-mail

No repositório, abra **Settings → Secrets and variables → Actions → New repository secret** e adicione:

| Secret | O que preencher |
|---|---|
| `SMTP_HOST` | Ex.: `smtp.gmail.com` |
| `SMTP_PORT` | `465` para SSL; `587` para STARTTLS |
| `SMTP_USER` | Seu endereço de e-mail remetente |
| `SMTP_PASSWORD` | Senha de app específica do provedor, **não** sua senha normal |
| `ALERT_EMAIL` | E-mail que receberá as vagas |

Credenciais de e-mail devem ficar somente em Secrets; jamais dentro do `config.json` ou do repositório. Nem todo provedor autoriza SMTP por senha de app.

## Configurar alertas no Telegram (alternativo ao e-mail)

1. Crie um bot com o **@BotFather** no Telegram e copie seu token.
2. Inicie uma conversa com esse bot e obtenha seu `chat_id` pela API oficial do Telegram.
3. Configure os Secrets `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.

## Ajustar seu perfil

Edite `config.json`:
- `minimum_score`: nota de corte entre 0 e 100 (começa em 55).
- `days_old_max`: idade máxima do anúncio (começa em 45 dias).
- `queries`: termos pesquisados.
- `require_brazil_eligibility`: mantenha `true` para evitar vagas explicitamente restritas a outros países.

Os critérios de profissão, senioridade e habilidades estão em `src/jobradar.py`. É possível aperfeiçoar a classificação conforme você dá feedback sobre as vagas.

## Limitações importantes

- **Esta versão não consulta diretamente LinkedIn, Gupy, Indeed ou Sicredi**: cada plataforma precisa de uma integração permitida. Não burla CAPTCHA, login nem limites de uso.
- O escore é baseado em palavras-chave e poderá errar; em vagas globais, visto, idioma e elegibilidade exigem confirmação manual.
- A API Himalayas atualiza resultados por volta de 24 horas, e a Remotive também apresenta atraso nas vagas da API.
- Para aceitar vagas brasileiras adicionais da Adzuna, é preciso obter chaves e testar a cobertura no Brasil.
- Este ZIP contém o código e a interface, mas **não está publicado nem operando automaticamente** até que você o instale/deploye.

## Testes

```bash
python -m unittest discover -s tests -v
```

## Fontes e licença de dados

Consulte <https://himalayas.app/docs/remote-jobs-api> e <https://remotive.com/remote-jobs/api>. O aplicativo sempre exibe a fonte e utiliza o link retornado pelo provedor. Não reenvie listas dessas fontes a agregadores terceiros.