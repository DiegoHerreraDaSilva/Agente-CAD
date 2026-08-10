# Assistente Engenharia — POC

Prova de conceito de um agente **consultivo** de engenharia CAD/Siemens NX, com:

- **Login e gestão de usuários** com autenticação no PostgreSQL (email/senha, hash bcrypt), papéis (engenheiro/admin) e troca de senha obrigatória no primeiro acesso.
- **Chat com streaming** da API da DeepSeek (backend FastAPI + SSE), com sessões persistidas e sidebar de conversas.
- **Três camadas de memória**: curto prazo (histórico da sessão), pessoal (por usuário, editável no Perfil) e compartilhada (base de conhecimento da equipe).
- **RAG (busca semântica)**: a base de conhecimento não é mais injetada inteira no prompt — as entradas são embeddadas com a **Voyage AI** e guardadas no Postgres (`pgvector`); a cada pergunta, só as top-N entradas mais relevantes são recuperadas por similaridade e injetadas no turno atual.
- **Compactação de sessão** (`/compact`): resume a conversa via DeepSeek, libera contexto e envia o resumo como proposta de conhecimento compartilhado (fila de aprovação).
- **Cache automático de prefixo**: a DeepSeek cacheia sozinha o prefixo repetido entre turnos (system + histórico), reduzindo custo/latência em conversas longas — sem marcação explícita no request.
- **Painel de administração** (TI): gestão de usuários (criar, editar, resetar senha, excluir), aprovação/rejeição/edição/exclusão/criação manual de entradas na base de conhecimento (com busca), visão de economia de cache, e um **dashboard de uso** (cards de resumo, volume de mensagens por dia, heatmap de horário de pico, ranking de usuários e sessões mais ativas — nominal, restrito ao painel admin).
- **Produtividade no chat**: busca global por conteúdo (`Ctrl+K`), templates de prompt pessoais salvos por usuário, favoritar/fixar sessões, exportar a conversa em Markdown, timestamp em cada mensagem, sugestões de follow-up após cada resposta, regenerar a última resposta, editar e reenviar uma pergunta anterior (trunca o que vem depois), anexar um arquivo de texto (botão ou arrastar-e-soltar), atalhos de teclado com um modal de ajuda (`?`), auto-scroll que não interrompe o usuário se ele rolar pra cima durante o streaming, e aviso de "ainda processando" se a resposta demorar.
- **Interface moderna** (React + Tailwind CSS v4 + Framer Motion + lucide-react + `next-themes`): tema claro/escuro com toggle no header, cards em gradiente com contorno de destaque, cantos de 14px, animações de entrada/hover/clique, estados vazios/loading tratados, e botão de copiar em cada resposta do agente.

O agente é **estritamente consultivo** — não executa nada no NX. LLM: **DeepSeek** (`deepseek-v4-flash`), com thinking mode desligado explicitamente. Anexo de imagem no chat não é suportado (visão não confirmada no formato OpenAI-compatible da DeepSeek).

## Stack

Backend em Python (FastAPI + Uvicorn), streaming via SSE, SDK `openai` (a API da DeepSeek é OpenAI-compatible — `base_url="https://api.deepseek.com"`). Embeddings do RAG via **Voyage AI** (`voyageai`). Banco **PostgreSQL 16 com a extensão `pgvector`** (imagem `pgvector/pgvector:pg16`) rodando em Docker — só o banco; o backend roda em venv local. Frontend em **React + TypeScript (Vite)**, com `react-router-dom` para navegação client-side, **Tailwind CSS v4** (`@tailwindcss/vite`, CSS-first — sem `tailwind.config.js`) e **`next-themes`** para o tema claro/escuro. Em produção, o build estático (`frontend/dist`) é servido pelo próprio FastAPI — um único processo. O backend usa o pacote `truststore` para confiar no certificado da rede corporativa ao chamar APIs externas (DeepSeek, Voyage — rede com inspeção TLS) — como `truststore.inject_into_ssl()` patcheia o SSL do processo inteiro, todos os clients herdam essa confiança automaticamente, sem config por client.

> O frontend já foi HTML/CSS/JS puro (sem Node), porque a rede corporativa bloqueava `npm install`. Esse bloqueio foi resolvido depois (certificado corporativo liberado para o npm) e o frontend foi migrado para React visando performance (bundles minificados, code-splitting do painel admin via `React.lazy`) e organização de pastas (componentes/hooks/lib em vez de um `<script>` inline por página). Mais tarde, o CSS puro (paleta fixa, só tema escuro) foi migrado para o design system Schwaben com Tailwind + tokens de tema (ver seção "Interface e design system" abaixo) — os nomes de classe dos componentes (`.btn-primario`, `.card`, `.modal` etc.) foram mantidos; só o CSS por trás deles mudou, para não precisar reescrever o JSX de cada componente.

## Pré-requisitos

- Python 3.10+
- Node.js 18+ e npm (para o build do frontend)
- Docker Desktop (para o Postgres com pgvector)
- Uma chave da API DeepSeek (conta pré-paga em https://platform.deepseek.com; ver seção "LLM: DeepSeek")
- Uma chave da API Voyage AI (embeddings do RAG — https://dash.voyageai.com)
- Um navegador (a interface é servida pelo próprio backend)

## Passo a passo

git clone https://github.com/DiegoHerreraDaSilva/Agente-CAD.git

### 1. Postgres (Docker)

```bash
cd backend
cp .env.example .env          # no Windows PowerShell: copy .env.example .env
# edite o .env: DEEPSEEK_API_KEY, VOYAGE_API_KEY, POSTGRES_PASSWORD, SESSION_SECRET e ADMIN_EMAILS
docker compose up -d          # sobe o Postgres (imagem pgvector/pgvector:pg16) e roda init.sql
```

> Se você já tinha um volume do Postgres criado na imagem antiga `postgres:16`, rode `docker compose down && docker compose up -d` (sem `-v`, para não perder os dados) uma vez para o container subir na imagem `pgvector/pgvector:pg16`. A extensão `vector` e a coluna de embedding são criadas no startup do backend (`garantir_schema()`), então o volume existente é migrado sem recriar.

Gere um `SESSION_SECRET` aleatório:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

`ADMIN_EMAILS` é uma lista de emails (separados por vírgula) que viram admin automaticamente. Se a conta ainda não existir, o backend a cria no startup com uma senha temporária impressa no log.

### 2. Backend (venv local)

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate    # Linux/macOS
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

O backend garante o schema do banco no startup (idempotente — não precisa recriar o volume Docker ao atualizar o código), incluindo a extensão `vector` e a coluna de embedding.

**Indexar a base para o RAG** (uma vez, com o `.env` preenchido): as entradas de conhecimento só são recuperáveis depois de embeddadas. Rode, a partir de `backend/`:

```bash
python scripts/reindex_knowledge.py       # gera embedding de toda entrada aprovada sem embedding
# opcional, para testar localmente com dados fictícios:
python scripts/seed_fake_knowledge.py     # insere ~40 entradas fictícias NX/CAD e já as embedda
```

Aprovar/criar/editar uma entrada pelo painel `/admin` gera o embedding automaticamente; o `reindex` é só para o backfill inicial (ou depois de trocar o modelo de embedding).

### 3. Frontend (React + Vite)

**Produção / uso normal** — gera o build estático e deixa o próprio FastAPI servir tudo:

```bash
cd frontend
npm install
npm run build            # gera frontend/dist — o FastAPI passa a servir a partir daqui
```

Depois disso, abra **http://localhost:8001/** — é a única porta usada, front e back juntos.

**Desenvolvimento** — com o backend já rodando em `:8001` (passo 2), roda o Vite em paralelo com hot-reload:

```bash
cd frontend
npm run dev               # abre em http://localhost:5173, com proxy de /auth,/chat,/sessions,/snippets,/admin,/knowledge para :8001
```

Sem sessão válida, você é redirecionado para `/login`. **Não há autocadastro** — contas são criadas pela TI no painel `/admin` (ou nascem via `ADMIN_EMAILS` no bootstrap). Toda conta nova exige troca de senha no primeiro login.

## Arquitetura

### Organização de pastas

```
nx-agent-poc/
├── public/logo.png              # logo original (fonte); frontend/public/logo.png é uma cópia p/ o Vite
├── backend/
│   ├── main.py                  # composition root: cria o app, inclui os routers, SPA fallback
│   ├── init.sql                 # schema para instalação nova (volume Docker do zero)
│   ├── docker-compose.yml       # só o serviço Postgres (imagem pgvector/pgvector:pg16)
│   ├── requirements.txt
│   ├── .env / .env.example
│   ├── scripts/                 # reindex_knowledge.py (backfill RAG), seed_fake_knowledge.py
│   └── app/
│       ├── config.py            # constantes, client DeepSeek e Voyage, RAG_*, ADMIN_EMAILS, truststore
│       ├── llm.py               # chamadas ao LLM (DeepSeek): streaming, thinking mode, usage
│       ├── db.py                # conexão Postgres + garantir_schema() (inclui extensão vector)
│       ├── schemas.py            # modelos Pydantic de request
│       ├── security.py            # hash/verificação de senha (bcrypt)
│       ├── deps.py                 # dependências de auth do FastAPI (usuario_atual, admin_atual...)
│       ├── prompt.py                # system prompt + bloco de conhecimento recuperado por RAG
│       ├── embeddings.py             # geração de embeddings via Voyage (RAG)
│       ├── repositories/              # acesso a dados: users.py, sessions.py, knowledge.py (RAG + indexação), snippets.py
│       └── routers/                    # rotas por área: pages, auth, admin, sessions, snippets, knowledge, chat
└── frontend/
    ├── vite.config.ts           # proxy de dev para o FastAPI (:8001)
    ├── public/logo.png
    ├── dist/                    # build de produção (gerado, servido pelo FastAPI)
    └── src/
        ├── main.tsx, App.tsx    # entry point (envolve em ThemeProvider) + rotas (react-router)
        ├── styles/global.css    # @import "tailwindcss" + tokens Schwaben (:root claro / .dark escuro)
        ├── lib/                 # api.ts (wrappers tipados de cada endpoint), types.ts, markdown.tsx, utils.ts (cn()),
        │                        # exportSession.ts (export Markdown), formatarData.ts (data/hora pt-BR com timezone)
        ├── hooks/                # useChatStream, use401Redirect
        ├── context/AuthContext.tsx
        ├── components/
        │   ├── auth/            # RequireAuth, RequireSenhaAtualizada, RequireAdmin (guards de rota)
        │   ├── layout/           # Header, ThemeToggle
        │   ├── chat/             # Sidebar, MessageBubble, ChatInput, ResumoBox, SearchModal, HelpModal,
        │   │                     # SnippetsMenu, FollowUpChips
        │   ├── modal/            # PerfilModal
        │   └── admin/            # UsersTab, CacheTab, KnowledgeTab, DashboardTab, modais de usuário
        └── pages/                # LoginPage, ChangePasswordPage, ChatPage, AdminPage
```

Backend: separado em `app/config.py` → `db.py`/`schemas.py` → `security.py`/`deps.py`/`prompt.py` → `repositories/` (acesso a dados) → `routers/` (rotas), sem framework de camadas nem ORM (`repositories/*.py` são só funções com SQL cru via `psycopg`). `main.py` fica fino: cria o `FastAPI()`, registra os middlewares, inclui cada router e cuida do fallback de SPA — que **precisa** continuar definido ali, depois de todo `include_router(...)`, senão "engoliria" as rotas de API. Frontend: organizado por responsabilidade (components/hooks/lib/pages), com Tailwind CSS v4 + tokens de tema (claro/escuro) — ver "Interface e design system".

### Modelo de dados (Postgres)

```
users                    chat_sessions              chat_messages
├─ id (PK)                ├─ id (PK)                  ├─ id (PK)
├─ email (unique)         ├─ user_id (FK→users)       ├─ session_id (FK→chat_sessions)
├─ senha_hash (bcrypt)    ├─ titulo                    ├─ papel ('user'|'assistant')
├─ nivel (enum)           ├─ resumo (texto, /compact)  ├─ conteudo
├─ role ('engineer'|      ├─ rag_injetadas (jsonb)     └─ criado_em
│         'admin')        ├─ pinned (favoritar)
├─ memoria (texto livre)  ├─ criado_em
├─ must_change_senha      └─ atualizado_em
└─ criado_em

knowledge_entries          cache_usage_log             prompt_snippets
├─ id (PK)                 ├─ id (PK)                   ├─ id (PK)
├─ titulo                  ├─ session_id (FK)           ├─ user_id (FK→users)
├─ conteudo                ├─ user_id (FK)              ├─ titulo
├─ categoria                ├─ input_tokens             ├─ conteudo
├─ criado_por                ├─ cache_creation_input_tokens └─ criado_em
├─ status                    ├─ cache_read_input_tokens
├─ embedding (vector 1024)   ├─ output_tokens
├─ resumo_rag (nullable)     └─ criado_em
└─ criado_em
```

FKs de `chat_sessions`, `chat_messages`, `cache_usage_log` e `prompt_snippets` são `ON DELETE CASCADE`. O schema é criado tanto em `init.sql` (volume novo) quanto em `garantir_schema()` no startup do app (`CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ADD COLUMN IF NOT EXISTS`), então atualizações de código nunca exigem recriar o volume Docker. A busca por conteúdo (`GET /sessions/search`) usa `ILIKE` acelerado por um índice trigram (`pg_trgm`) em `chat_messages.conteudo`.

### As três camadas de memória

1. **Curto prazo** (por sessão): `chat_messages` — histórico multi-turn da conversa atual.
2. **Pessoal** (por usuário): `users.memoria` — texto livre editável no Perfil, sempre injetado no prompt.
3. **Compartilhada** (da equipe): `knowledge_entries` — base técnica de NX/CAD. Só entradas `status = 'aprovado'` **e com embedding** entram no prompt, e não a base inteira: a cada mensagem, o RAG recupera por similaridade só as top-N entradas relevantes à pergunta (ver seção RAG abaixo).

**`/compact`** resume as `chat_messages` da sessão (chamada separada à DeepSeek), grava em `chat_sessions.resumo` e **apaga** as mensagens antigas — o resumo substitui o detalhe, não convive com ele. Esse resumo também é enviado automaticamente como uma nova linha em `knowledge_entries` com `status = 'pendente'` (categoria `resumo_sessao`) — vira conhecimento compartilhado de fato só depois que um admin aprova na aba **Base de conhecimento** do painel `/admin` (`GET/POST /admin/knowledge...`). Rejeitar **exclui a linha de `knowledge_entries`** (não é uma mudança de status) — o resumo de origem em `chat_sessions.resumo` é uma tabela totalmente separada e nunca é afetado: rejeitar na base de conhecimento não apaga nada do histórico/chat do usuário.

Na aba **Base de conhecimento**, o admin também pode: ver o conteúdo completo de qualquer entrada (pendente ou aprovada) e editá-lo antes de decidir, excluir uma entrada já aprovada (some do prompt na próxima mensagem), buscar por título/conteúdo/categoria/autor, e **criar uma entrada manualmente** (`POST /admin/knowledge`) — que entra direto como `aprovada`, sem passar pela fila de revisão, já que o próprio admin a redigiu.

### Autenticação e autorização

Cadeia de dependências do FastAPI, cada uma envolvendo a anterior:

```
usuario_atual(request)          → lê o cookie de sessão, 401 se inválido
  → requer_senha_atualizada()   → 403 se must_change_senha=True
    → admin_atual()             → 403 se role != 'admin'
```

Cadastro público está **desabilitado** (`POST /auth/register` sempre 403). Contas só nascem via bootstrap (`ADMIN_EMAILS` no `.env`) ou pelo painel `/admin`, e sempre com `must_change_senha=True` — forçando a troca de senha antes de liberar qualquer outra rota. Excluir um usuário (`DELETE /admin/users/{id}`) apaga a conta e, via `ON DELETE CASCADE`, suas sessões/mensagens/log de cache; um admin não pode excluir a própria conta (mesma trava usada para impedir o auto-rebaixamento de papel).

Não há `CORSMiddleware` no backend — front e back sempre são a mesma origem do ponto de vista do navegador (proxy do Vite em dev, mesmo processo FastAPI em produção), então nunca houve necessidade de CORS; adicionar `allow_origins=["*"]` só abriria a API (autenticada por cookie de sessão) para leitura por qualquer site.

`POST /auth/login`, `POST /chat` e `POST /sessions/{id}/compact` têm rate limiting via `slowapi` (`Limiter` em `app/config.py`, registrado em `main.py`) — 5/min, 20/min e 10/min respectivamente. Limite excedido devolve `429`. Armazenamento em memória (adequado para um único processo `uvicorn`; se o app ganhar múltiplas réplicas, precisa migrar para um backend compartilhado, ex. Redis).

A **chave** do limite muda por rota, não só o valor: `/auth/login` é por IP (`get_remote_address` — nesse ponto ainda não há usuário autenticado, então não existe outra opção de chave sem introduzir sinal extra). Já `/chat` e `/compact` são **por usuário logado** (`get_user_or_ip` em `app/config.py`, lê `request.session["user_id"]` — o `SessionMiddleware` roda como middleware ASGI, então a sessão já está disponível antes mesmo do `Depends(...)` da rota resolver). Isso corrige um problema real de rede corporativa com NAT: se fosse por IP, todo mundo atrás do mesmo IP externo da empresa compartilharia o mesmo teto — um punhado de engenheiros conversando ao mesmo tempo esgotaria o limite pra todo mundo. Por usuário, cada engenheiro tem seu próprio teto de 20 mensagens/min e 10 compactações/min, independente de quantas outras pessoas estão atrás do mesmo IP.

### Headers de segurança HTTP

Um middleware em `main.py` (`security_headers`) anexa três headers em toda resposta do backend:

- `X-Content-Type-Options: nosniff` — impede o navegador de tentar reinterpretar o tipo de um arquivo diferente do `Content-Type` declarado.
- `X-Frame-Options: DENY` — impede que o app seja carregado dentro de um `<iframe>` em outro site (proteção contra clickjacking).
- `Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'` — bloqueia por padrão qualquer script/estilo/imagem/conexão de origem diferente da própria. `img-src data:` é necessário pelos anexos de imagem colados/anexados no chat (Markdown com `data:` URI); `style-src 'unsafe-inline'` é uma concessão pragmática porque vários componentes React usam `style={{...}}` inline (ex.: `KnowledgeTab`, `UsersTab`) — CSP puro bloquearia isso. Isso funciona como segunda camada de defesa contra XSS: o chat e o resumo de sessão renderizam Markdown → HTML via `dangerouslySetInnerHTML` (`MessageBubble.tsx`, `ResumoBox.tsx`); mesmo que um bug no parser ou uma resposta manipulada do agente injetasse um `<script src="...">`, o CSP bloqueia o carregamento.

Esse header só se aplica quando o **FastAPI** serve a resposta — ou seja, produção (`npm run build` + backend) e as chamadas de API mesmo em dev. Rodando `npm run dev`, o HTML vem direto do Vite em `:5173`, sem passar pelo backend; por isso `frontend/index.html` já tem a mesma política numa tag `<meta http-equiv="Content-Security-Policy">`, que cobre esse caso e é servida também dentro do build de produção (as duas coexistem, sem conflito).

Fora de escopo por enquanto: `Strict-Transport-Security` (HSTS) — só faz sentido quando o app rodar atrás de TLS de verdade (hoje é HTTP local, `https_only=False` no `SessionMiddleware`); ver roadmap.

### RAG (recuperação semântica da base de conhecimento)

Em vez de mandar a base inteira no prompt, as entradas aprovadas são embeddadas com a **Voyage AI** e guardadas na coluna `knowledge_entries.embedding` (`vector(1024)`, `pgvector`), com índice HNSW de cosseno. O embedding é gerado automaticamente quando uma entrada é **aprovada**, **criada** (pelo admin, já aprovada) ou **editada** (se aprovada) — os hooks vivem em `app/repositories/knowledge.py`. A Voyage distingue `input_type` `"document"` (ao indexar) de `"query"` (ao buscar), o que melhora a recuperação. Backfill inicial: `scripts/reindex_knowledge.py`.

A cada `/chat`, `recuperar_conhecimento(pergunta, rag_injetadas, turno_atual)` embedda a pergunta, busca o dobro de candidatas (top-2N por `ORDER BY embedding <=> %s`) e descarta as abaixo do limiar de score (`RAG_LIMIAR`, default 0.4). Se a Voyage cair, retorna `([], rag_injetadas inalterado)` e o chat segue **sem** conhecimento recuperado (degradação graciosa — não cai de volta na base inteira). Parâmetros e modelo (`VOYAGE_MODEL`, `EMBEDDING_DIM`, `RAG_TOP_N`) ficam em `app/config.py`.

**Dedup por sessão.** `chat_sessions.rag_injetadas` guarda um mapa `{entry_id: turno_injetado}` das entradas já mandadas nesta conversa. Ao montar o top-N (default 4) a partir das candidatas, uma entrada já injetada há **menos** de `RAG_JANELA_REINJECAO` turnos (default 10) é pulada — mas a lista é **completada** com a próxima melhor candidata, nunca simplesmente encolhida, para não perder contexto útil em conversas longas. Se ninguém a substituir nesta rodada, ela permanece disponível e pode ser selecionada de novo depois. Ao rodar `/compact`, `rag_injetadas` é zerado **na mesma transação** que apaga `chat_messages` (`apagar_mensagens` em `app/repositories/sessions.py`) — senão uma entrada injetada só antes da compactação ficaria marcada como "já mandada" para sempre, mesmo sem o detalhe ter sobrevivido no resumo.

**`resumo_rag` (versão condensada para injeção).** Recuperação e injeção têm objetivos opostos de tamanho: o embedding sempre usa `conteudo` completo (mais texto ajuda a busca), mas o texto **injetado** no turno atual usa `COALESCE(resumo_rag, conteudo)` — a coluna `resumo_rag` é gerada automaticamente (mesmo hook do embedding) só para entradas com mais de `RESUMO_RAG_MIN_CHARS` (default 3200, ~800 tokens); entradas curtas já são o caso ótimo e ficam com `resumo_rag = NULL`, caindo de volta no conteúdo completo. Falha ao gerar o resumo não quebra a aprovação/criação (mesmo padrão de degradação graciosa do embedding). Backfill/reprocessamento: `scripts/backfill_resumo_rag.py`.

### Concisão no tom (economia de tokens de saída)

O bloco de tom (`TOM_POR_NIVEL` em `app/prompt.py`) inclui regras de forma comuns aos quatro níveis: não recapitular a pergunta, não anunciar o que vai fazer, não terminar com um resumo do que já foi dito, e referenciar informação já dada na conversa em vez de repeti-la. Essas regras cortam só a **forma** — a explicação didática do "porquê" (definir termos, passo a passo) continua intacta para estagiário/júnior, que é o objetivo original desses níveis (reduzir a carga dos engenheiros sênior como professores).

Há também uma regra contra um tipo específico de alucinação, detectado ao vivo: numa sessão nova (sem histórico nem resumo), o modelo afirmou algo como "conceitos que você já viu" sobre um assunto nunca mencionado na conversa. O prompt agora proíbe explicitamente afirmar que o engenheiro já viu/sabe/praticou algo a menos que isso tenha aparecido literalmente no histórico de mensagens ou no resumo injetado.

### Fluxo de uma mensagem de chat

```
POST /chat {session_id, pergunta}
  → valida sessão e login; rejeita (400) se vier imagem anexada (não suportado)
  → grava a pergunta em chat_messages
  → monta o histórico completo (multi-turn) da sessão
  → RAG: embedda a pergunta (Voyage) e recupera top-N entradas por similaridade (pgvector),
    deduplicando contra o que já foi injetado nesta sessão
  → system prompt: [tom por nível] + [memória pessoal] + [resumo]  (string única)
  → turno atual: [conhecimento recuperado (se houver)] + [pergunta]
  → app.llm.resposta_stream(...) — streaming SSE token a token, thinking mode desligado
  → ao final: captura uso de tokens (incl. cache automático) e grava a resposta + o log de custo
```

Erros de sobrecarga/limite da API (mesmo no meio do streaming) são traduzidos por `app/llm.py` em 4 exceptions genéricas (`LLMSobrecarregado`, `LLMLimiteRequisicoes`, `LLMConexaoFalhou`, `LLMErro`) e viram uma mensagem amigável no chat, sem derrubar a conexão. `/compact` usa `max_tokens=4096` na chamada não-streaming que gera o resumo — ambos os limites foram calibrados para não cortar respostas longas no meio.

### LLM: DeepSeek (padrão) / OpenRouter (teste)

O backend chama a DeepSeek (API OpenAI-compatible, `pip install openai`, `base_url="https://api.deepseek.com"`) através de uma seam única, **`app/llm.py`** — nenhum outro módulo importa o SDK `openai` ou toca em `llm_client`/`LLM_MODEL` (`app/config.py`) diretamente. Os 3 pontos que precisam de LLM (`/chat` streaming, `/compact` resumo de sessão, `gerar_resumo_rag` em `knowledge.py`) chamam só `resposta_stream()`/`resposta_simples()`.

**Testar com o OpenRouter.** `LLM_PROVIDER=openrouter` no `.env` (junto de `OPENROUTER_API_KEY` e opcionalmente `OPENROUTER_MODEL`, ver `.env.example`) troca o LLM do app inteiro pro OpenRouter — mesmo formato OpenAI-compatible, só muda `base_url`/`api_key`/`model` em `app/config.py`. É só pra teste/comparação; o padrão sem essa variável continua sendo a DeepSeek direto. Duas diferenças tratadas automaticamente por provider:

- **`thinking` (extra_body) só é enviado pra DeepSeek** — é uma extensão proprietária dela; mandar isso pra outro modelo via OpenRouter não faria sentido (o modelo de teste padrão, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`, é inclusive um modelo de reasoning por si só).
- **Usage sem detalhe de cache**: `_normalizar_usage()` em `llm.py` usa `getattr` com fallback pros campos padrão da OpenAI (`prompt_tokens`/`completion_tokens`) quando os campos específicos da DeepSeek (`prompt_cache_miss_tokens`/`prompt_cache_hit_tokens`) não vêm na resposta — evita `AttributeError` com qualquer provider.
- **Preço zerado no modo OpenRouter** (`PRECO_MISS`/`PRECO_HIT`/`PRECO_OUTPUT` = 0 em `config.py`): não há tabela de preço por modelo do OpenRouter integrada ainda, então `/admin/cache-stats` mostraria custo incorreto — zerado de propósito enquanto for só teste (o modelo padrão sugerido, aliás, é `:free`).

**Thinking mode.** A DeepSeek roda em modo "thinking" (reasoning) por padrão — se ficar ligado sem perceber, cada resposta gasta muito mais tokens de saída (e dinheiro) do que parece. O request explicita `extra_body={"thinking": {"type": "disabled"}}` pra desligar de vez (`thinking` é extensão específica da DeepSeek, fora do schema padrão OpenAI — o SDK só aceita esse tipo de parâmetro via `extra_body`). Teste empírico de sanidade: pergunta de uma linha → `completion_tokens` deve ficar em dezenas, não centenas (se vier alto, o thinking ainda está ligado). Validado com a API real: 8 tokens de output numa resposta de uma linha.

**Cache automático.** Diferente de APIs que exigem marcação explícita de breakpoint, a DeepSeek cacheia sozinha o prefixo repetido entre chamadas (sem nenhum parâmetro no request) — o `system` (tom + memória + resumo) e o histórico da conversa tendem a se repetir turno a turno, então o prefixo comum é lido do cache automaticamente. Validado com a API real: um 2º turno com o mesmo prefixo do 1º leu 768 tokens do cache (`prompt_cache_hit_tokens`), com `input_tokens` (miss) caindo de 857 para 89.

**Usage normalizado.** `UsoNormalizado` (dataclass em `llm.py`) é o shape que `registrar_uso_cache` grava em `cache_usage_log`:

| `UsoNormalizado` | Campo da DeepSeek |
|---|---|
| `input_tokens` | `prompt_cache_miss_tokens` |
| `cache_creation_input_tokens` | sempre `0` (a DeepSeek não tem conceito de "cache write" pago à parte) |
| `cache_read_input_tokens` | `prompt_cache_hit_tokens` |
| `output_tokens` | `completion_tokens` |

No formato OpenAI-compatible, receber `usage` num response em streaming exige `stream_options: {"include_usage": True}` — sem isso, o último chunk não traz os tokens.

**Imagens não suportadas.** Suporte a visão no formato OpenAI-compatible da DeepSeek não está confirmado — por isso o botão de anexar/colar imagem não existe no chat (`ChatInput.tsx`, prop `imagensHabilitadas={false}`) e `POST /chat` com `imagens` não-vazio retorna 400 mesmo que a requisição chegue de outra forma (defesa em profundidade, ver `chat.py`).

**Preços** (USD/1M tokens, `app/config.py`): `PRECO_MISS` $0,14 · `PRECO_HIT` $0,0028 · `PRECO_OUTPUT` $0,28. `/admin/cache-stats` usa esses valores pra estimar `custo_real_usd` (com cache) vs. `custo_sem_cache_usd` (hipotético, tudo miss) e expõe a economia — com filtro por usuário no painel `/admin`.

**Custo estimado**: ~$0,007/usuário/dia → ~$3/mês para 20 engenheiros.

### Frontend

SPA em React + TypeScript, roteada por `react-router-dom`. A autenticação é resolvida uma vez em `RequireAuth` (busca `/auth/me` e guarda o usuário em `AuthContext`), com guards aninhados que espelham as dependências do backend:

```
RequireAuth            (401 → /login)
  └─ RequireSenhaAtualizada  (must_change_senha → /change-password)
       ├─ ChatPage (rota "/")
       └─ RequireAdmin        (role != admin → /)
            └─ AdminPage (rota "/admin")
```

`ChatPage` usa o hook `useChatStream` para consumir o SSE de `/chat` token a token e `lib/markdown.tsx` para renderizar a resposta (parser leve próprio, sem dependência externa — suporta negrito/itálico/código/listas/tabelas GFM e a extensão de imagem `![](data:...)`, usada hoje só para exibir imagens de mensagens antigas do histórico, já que anexar imagem nova não é mais suportado — ver seção "LLM: DeepSeek"). `AdminPage` carrega `ChatPage`/`AdminPage` via `React.lazy` — o bundle do painel admin só é baixado por quem realmente abre `/admin`.

Build (`npm run build`) gera `frontend/dist`, servido pelo FastAPI: os arquivos JS/CSS ficam em `/assets` (via `StaticFiles`) e qualquer rota que não seja de API cai num fallback que devolve `index.html` — o roteamento de fato acontece no navegador (react-router).

### Interface e design system

O CSS (`frontend/src/styles/global.css`) segue o design system Schwaben: **Tailwind CSS v4** via `@import "tailwindcss";` (sem `tailwind.config.js`/`postcss.config.js` — o plugin `@tailwindcss/vite` cuida de tudo), tokens de cor em `:root` (tema claro) e `.dark` (tema escuro, aplicado por padrão), cantos de **14px** em card/modal/cartão de login (8px em botão/input, pill em badge/chip), e a assinatura visual `.card`: superfície em gradiente sutil, brilho (`hairline`) no topo, sombra, e um contorno luminoso na base que acende no hover.

- **Tema**: `next-themes` (`ThemeProvider attribute="class" defaultTheme="dark"` em `main.tsx`) alterna a classe `dark` no `<html>`. O botão de troca (`components/layout/ThemeToggle.tsx`, ícone Sun/Moon) fica embutido no `Header` — visível no chat e no admin.
- **`cn()`** (`lib/utils.ts`, `clsx` + `tailwind-merge`) — helper padrão para montar className condicional em componentes novos.
- Os componentes existentes **mantiveram os mesmos nomes de classe** de antes da migração (`.btn-primario`, `.sessao-item`, `.modal`, `.badge`, `.stat-card` etc.) — só o CSS por trás de cada um foi reescrito para os tokens novos (`var(--accent)`, `var(--surface)`, `var(--text-muted)` etc. em vez de `var(--brand-600)`/`var(--slate-900)` fixos). Isso evitou reescrever o JSX de cada tela só para trocar de sistema visual; um componente novo, porém, deve usar classes utilitárias Tailwind diretamente (não os nomes de classe antigos).
- `select option { color: #000; background: #fff; }` é proposital: o menu nativo do `<select>` não herda os tokens de tema, e forçar só a cor do texto (sem fundo) deixava a lista ilegível quando o navegador desenha o popup com fundo escuro por padrão (SO em dark mode).

### Produtividade no chat

- **Atalhos de teclado**: `Ctrl+K` abre a busca, `n` cria uma sessão nova (fora de um campo de texto — `Ctrl+N` não dá pra usar aqui: é um atalho reservado do navegador para abrir nova janela, que nenhuma página consegue interceptar), `/` foca o campo de pergunta, `?` abre o modal de ajuda (`HelpModal.tsx`, lista todos os atalhos e o comando `/compact`), `Esc` fecha busca/ajuda, `Enter` envia e `Shift+Enter`/`Ctrl+Enter` quebra linha ou força o envio.
- **Busca global** (`Ctrl+K`, `SearchModal.tsx`): consulta `GET /sessions/search?q=` com debounce de 250ms, retornando sessões cujo título bate e mensagens cujo conteúdo bate (com um trecho de contexto ao redor do termo) — resultado de mensagem abre a sessão correspondente.
- **Templates de prompt** (`SnippetsMenu.tsx`): salvos por usuário em `prompt_snippets`, acessíveis pelo ícone de template no `ChatInput`; escolher um insere o texto no campo (concatenando se já houver algo digitado).
- **Favoritar/fixar sessão**: ícone de estrela em cada item da sidebar (`PATCH /sessions/{id}/pin`); sessões fixadas aparecem primeiro, numa seção separada ("Fixadas"). Excluir uma sessão fixada mostra um aviso de confirmação diferente, avisando que ela está fixada.
- **Exportar conversa** (`lib/exportSession.ts`): baixa a sessão atual como um arquivo `.md`, com autor e timestamp de cada mensagem.
- **Sugestões de follow-up** (`FollowUpChips.tsx`): depois de cada resposta do agente, três chips fixos ("Pode detalhar mais esse ponto?", "Tem um exemplo prático disso?", "Resume isso em tópicos.") que reenviam o texto ao serem clicados.
- **Regenerar / editar mensagem**: o botão de regenerar (só na última resposta) chama `POST /sessions/{id}/regenerate`, que apaga a última pergunta+resposta no backend e devolve a pergunta para o front reenviar via `/chat` (fluxo normal de envio, sem duplicar lógica). Editar uma mensagem do usuário chama `DELETE /sessions/{id}/messages/{message_id}/rest` (apaga a mensagem e tudo depois dela) e reenvia o texto editado do mesmo jeito.
- **Anexar arquivo de texto**: botão de clipe (`ChatInput.tsx`) ou arrastar-e-soltar direto na barra de input — lê `.txt/.log/.md/.csv/.json/.xml` via `FileReader` e injeta o conteúdo num bloco de código no campo de pergunta (puramente client-side; não sobe pro backend como arquivo, vira só texto na mensagem).
- **Auto-scroll inteligente**: o chat só acompanha o fim da conversa enquanto o usuário estiver lá (`ChatPage.tsx`, `seguindoRef` com margem de 80px); rolar pra cima durante o streaming não é interrompido pelos chunks seguintes, e um botão flutuante ("↓ Novas mensagens") volta ao fim e reativa o auto-scroll.
- **Aviso de "ainda processando"**: se a resposta do agente demorar mais de 6s pra começar a chegar, um texto aparece abaixo dos pontinhos de "digitando" (`MessageBubble.tsx`), pra diferenciar "vai responder já" de "travou".
- **Sincronização sem "recarregar" a tela**: depois que o streaming termina, o front busca os ids/timestamps reais do backend e só os "cola" nas mensagens já renderizadas por posição — nunca substitui o array por objetos com uma nova `key` do React, senão a lista inteira desmontaria/remontaria e a animação de entrada replayaria em tudo, dando a falsa impressão de que o chat recarregou.

### Dashboard de uso (admin)

Aba **Dashboard** no painel `/admin` (`DashboardTab.tsx` + `GET /admin/dashboard?dias=`), com seletor de período (7/30/90 dias): cards de resumo (total de mensagens, usuários ativos, média de mensagens/dia, tokens de saída), gráfico de volume de mensagens por dia (com eixos X/Y), heatmap de dia da semana × hora, ranking de usuários (nominal — visão sensível, por isso restrita ao admin) e as sessões mais ativas do período.

As agregações de "mensagens" e "tokens" em `ranking`/`sessoes_ativas` usam subconsultas separadas por `session_id`/`user_id` antes de juntar — fazer os dois `JOIN` (em `chat_messages` e `cache_usage_log`) direto pela sessão causa produto cartesiano (cada mensagem multiplicada por cada linha de uso de tokens da mesma sessão), inflando as duas contagens. As duas visões contam só mensagens do usuário (`papel = 'user'`, i.e. perguntas), pra serem comparáveis entre si.

## Como validar

0. `cd frontend && npm run build` antes de subir o backend — sem `frontend/dist`, qualquer rota que não seja de API devolve 404 (`main.py` avisa isso explicitamente).
1. Login sem sessão redireciona para `/login`; cadastro está desabilitado.
2. Primeiro acesso de uma conta nova força a troca de senha em `/change-password`.
3. Streaming de chat funciona; nível e memória pessoal influenciam o tom das respostas.
4. Sessões: criar, renomear, excluir, e o histórico persiste ao recarregar.
5. `/compact` resume e limpa mensagens antigas; a sessão volta a responder a partir do resumo.
6. Painel `/admin`: aba de usuários (criar, editar, resetar senha, excluir — exceto a própria conta), aba de base de conhecimento (aprovar/rejeitar pendências de `/compact`) e aba de economia de cache (com filtro por usuário).
7. `GET /knowledge` (autenticado) lista só a base compartilhada aprovada; `curl -i` sem sessão retorna 401 em qualquer rota protegida.
8. Após `/compact`, a entrada some do prompt do chat até um admin aprová-la em `/admin`; rejeitar exclui a linha de `knowledge_entries` mas não altera `chat_sessions.resumo` — a sessão do usuário continua exibindo o resumo normalmente.
9. Base de conhecimento: editar uma entrada pendente/aprovada, excluir uma aprovada, buscar por texto, e criar uma entrada manualmente (deve aparecer já como "Aprovada").
10. Botão de copiar em mensagens do agente copia o texto para a área de transferência.
11. `curl -i http://localhost:8001/` (rodando o build de produção, não `npm run dev`) mostra `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` e `Content-Security-Policy` na resposta; console do navegador sem erros de CSP ao usar o app normalmente (chat, painel admin).
12. Rate limiting: 6 tentativas seguidas de `POST /auth/login` com senha errada → a 6ª retorna `429`; 21 chamadas seguidas a `POST /chat` → a 21ª retorna `429`; 11 chamadas seguidas a `POST /sessions/{id}/compact` → a 11ª retorna `429`.
13. Respostas do chat começam direto no conteúdo (sem recapitular a pergunta) e não terminam com um resumo do que foi dito; estagiário/júnior continuam recebendo explicação didática do "porquê".
14. Numa mesma sessão, injetar uma entrada no turno 1 e perguntar de novo sobre o mesmo tema no turno 2 **não** reinjeta (a entrada não aparece nas `entradas` retornadas). No turno 15 (>`RAG_JANELA_REINJECAO`=10 turnos depois), a mesma pergunta reinjeta e grava `{"<id>": 15}` em `chat_sessions.rag_injetadas` (o valor antigo é sobrescrito, não mantido) — a partir daí, ela só volta a ser candidata a partir do turno 25. Rodar `/compact` zera `rag_injetadas` para `{}`.
15. Aprovar/criar uma entrada de conhecimento longa (>`RESUMO_RAG_MIN_CHARS`) gera `resumo_rag`; uma entrada curta fica com `resumo_rag = NULL` e a injeção usa o conteúdo completo (fallback via `COALESCE`).
16. Subir o app sem `DEEPSEEK_API_KEY` falha rápido no startup com mensagem clara (`app/config.py`), em vez de erro obscuro na primeira mensagem de chat.
17. Pergunta de uma linha no chat → `completion_tokens` (mapeado em `cache_usage_log.output_tokens`) fica em dezenas, não centenas (thinking mode desligado); 2º turno da mesma sessão com prefixo repetido registra `cache_read_input_tokens > 0`; o botão de anexar imagem não aparece e `POST /chat` com `imagens` retorna 400.
18. `/admin/cache-stats` calcula `custo_real_usd`/`economia_usd` com os preços da DeepSeek (`PRECO_MISS`/`PRECO_HIT`/`PRECO_OUTPUT`) e reflete a economia real do cache automático.
19. `Ctrl+K` abre a busca e encontra sessões/mensagens por conteúdo; `n` (fora de um campo de texto) cria sessão nova; `/` foca o input; `?` abre o modal de ajuda.
20. Fixar uma sessão (estrela na sidebar) a move para a seção "Fixadas"; excluí-la mostra um aviso de confirmação diferente do de uma sessão comum.
21. Editar uma mensagem antiga do usuário e reenviar trunca as mensagens seguintes (backend e tela) e gera uma nova resposta; regenerar a última resposta refaz só ela, sem duplicar a pergunta.
22. Soltar um arquivo `.txt` na barra de input (ou usar o botão de clipe) injeta o conteúdo no campo de pergunta.
23. Rolar para cima durante o streaming de uma resposta não puxa o scroll de volta ao fim; o botão "↓ Novas mensagens" aparece e, ao clicar, volta pro fim.
24. `GET /admin/dashboard?dias=30` retorna números consistentes entre `ranking` (por usuário) e `sessoes_ativas` (por sessão) — a soma das sessões de um usuário no ranking bate com o total dele, sem inflar por causa de JOIN cruzado com `cache_usage_log`.

## Testes de segurança realizados

Bateria de testes manuais executada pelo DevTools do navegador (Chrome) contra a POC rodando localmente, cobrindo a superfície client-side do app. Todos os testes abaixo passaram. 

### 1. Cookie de sessão (roubo de sessão)

O que testa: se o cookie de sessão pode ser lido por JavaScript malicioso.

Como foi feito: `Application → Cookies → localhost:8001`; conferido o flag `HttpOnly` e o `SameSite` do cookie. Também rodado `document.cookie` no console.

Resultado esperado (obtido): `HttpOnly` marcado e `SameSite` definido; `document.cookie` não retorna o cookie de sessão. Isso garante que, mesmo se houver um XSS na página, o cookie não pode ser exfiltrado via JS.

### 2. Cadeia de autorização por rota (401 / 403)

O que testa: se as rotas protegidas respeitam a cadeia `usuario_atual → requer_senha_atualizada → admin_atual`.

Como foi feito: no console, `fetch('/admin/users').then(r => console.log(r.status))` em três estados de sessão distintos.

Resultado esperado (obtido):

- Sem sessão → `401`.
- Logado como `engineer` (não admin) → `403` (barrado em `admin_atual`).
- Logado com `must_change_senha = true` → `403` em qualquer rota fora de `/change-password` (barrado em `requer_senha_atualizada`).

### 3. Isolamento entre usuários — IDOR (o teste crítico)

O que testa: se o backend confia no `session_id` da requisição sem verificar se ele pertence ao usuário logado (Insecure Direct Object Reference).

Como foi feito: logado como usuário A, capturado o `session_id` de uma conversa dele (via `/sessions` ou URL); logado como usuário B e tentado acessar essa sessão:

```js
fetch('/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ session_id: 'ID_DA_SESSAO_DO_A', pergunta: 'teste' })
})
```

Resultado esperado (obtido): o backend não devolve dados da sessão do usuário A — a checagem `WHERE user_id = usuario_atual.id` está presente. Uma falha aqui seria grave (vazamento de conversa entre usuários), por isso é o ponto mais importante da bateria.

### 4. XSS armazenado em campos livres

O que testa: se conteúdo controlado pelo usuário é renderizado como HTML executável (o parser de Markdown é próprio, em `lib/markdown.tsx`, sem lib de sanitização externa).

Como foi feito: inserido o payload `<img src=x onerror=alert(1)>` (e variações com `<script>`) em três campos livres distintos — título de sessão, memória pessoal (Perfil) e conteúdo de entrada da base de conhecimento (via `/admin`) — e recarregada a tela que exibe cada um.

Resultado esperado (obtido): o payload aparece como texto literal (escapado), sem disparar `alert` nem virar um elemento real no DOM. Confirmado inspecionando o HTML resultante no painel Elements. Testados os três campos separadamente, pois cada um passa por caminho de renderização diferente.

### 5. Exposição da chave de API

O que testa: se a `DEEPSEEK_API_KEY` vaza para o cliente (só o backend pode chamar a API da DeepSeek).

Como foi feito: aba `Network` filtrada por `Fetch/XHR`, uso normal do chat, inspeção dos payloads de request/response; e busca global (Ctrl+Shift+F) pelo prefixo da chave na aba `Sources` (todo o JS servido ao navegador).

Resultado esperado (obtido): nenhuma ocorrência da chave em requests, respostas ou no bundle do frontend. A chave permanece apenas no backend.

### 6. Vazamento de stack trace em erros

O que testa: se um erro de servidor devolve detalhes internos (caminho de arquivo Python, traceback) para o cliente.

Como foi feito: provocado erro proposital com payload inválido para `/chat` (`pergunta` vazia / `session_id` inexistente) e inspecionada a resposta na aba `Network`.

Resultado esperado (obtido): a resposta não expõe stack trace nem caminhos internos — apenas erro tratado.

### 7. Cabeçalhos de resposta HTTP

O que testa: presença dos headers de segurança e ausência de CORS indevido.

Como foi feito: `Network → (request principal) → Headers → Response Headers`, e `curl -i http://localhost:8001/` no build de produção.

Resultado / ações tomadas:

- Detectado `Access-Control-Allow-Origin: *` (CORS aberto) — removido, já que front e back são sempre a mesma origem (proxy do Vite em dev, mesmo processo FastAPI em produção).
- Adicionados via middleware `security_headers` em `main.py`: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` e uma `Content-Security-Policy` restritiva. Confirmados na resposta com `curl -i` e sem erros de CSP no console durante o uso normal (imagens no chat, painel admin).

### 8. Auditoria de cobertura de auth nas rotas

O que testa: se alguma rota em `routers/` (auth, admin, sessions, knowledge, chat, pages) ficou sem a dependência de auth por esquecimento.

Como foi feito: leitura de todas as rotas registradas nos 7 routers (`pages, auth, admin, sessions, snippets, knowledge, chat`) + a cadeia de dependências em `app/deps.py` (`usuario_atual → requer_senha_atualizada → admin_atual`), conferindo se cada uma usa a dependência correta para o que faz.

Resultado: nenhuma rota está desprotegida por esquecimento.

- Toda rota admin usa `admin_atual` (que já embute `requer_senha_atualizada` → `usuario_atual` por dependência encadeada).
- Chat, sessões, `/snippets`, `/knowledge` e `/auth/me/memoria` usam `requer_senha_atualizada`.
- `usuario_atual` (mais fraco) só aparece em `/auth/me` e `/auth/change-password` — intencional: precisam funcionar mesmo com `must_change_senha=True`, senão o usuário ficaria travado num loop de 403 sem conseguir trocar a própria senha.
- Rotas realmente públicas (`/auth/register` sempre-403, `/auth/login`, `/auth/logout`, `/logo.png`, `/health`, fallback de SPA) não expõem dado nenhum.
- `sessions.py`/`chat.py` também conferem *ownership* (`sessao_do_usuario` com `WHERE user_id = ...`), não só autenticação — reforça o teste 3 (IDOR).
- Ordem de registro em `main.py` confirmada correta: o fallback de SPA é registrado por último, depois de todos os routers, então não pode "engolir" nenhuma rota de API.

Único ponto estilístico (não é falha): `POST /auth/logout` não tem dependência — chamá-lo deslogado só limpa uma sessão já vazia. Inofensivo, deixado como está.

### 9. Rate limiting

O que testa: se rotas sensíveis a força bruta (`/auth/login`) ou a custo de API (`/chat`, `/compact`) tinham algum limite de requisições.

Como foi feito: adicionada a lib `slowapi` (rate limiter padrão para FastAPI, em memória — adequado aqui pois a POC roda um único processo `uvicorn`, sem réplicas): `POST /auth/login` (5/min, por IP — `get_remote_address`), `POST /chat` (20/min, por usuário logado — `get_user_or_ip`), `POST /sessions/{id}/compact` (10/min, por usuário logado). Testado disparando N+1 requisições seguidas de cada rota via `curl`, e também o cenário de dois usuários diferentes atrás do mesmo IP (simulando NAT corporativo).

Resultado (obtido):

- 6ª tentativa de login seguida → `429` (`{"error": "Rate limit exceeded: 5 per 1 minute"}`) em vez de `401`.
- 21ª chamada seguida a `/chat` (usuário A) → `429`.
- 11ª chamada seguida a `/compact` (usuário A) → `429`.
- **Teste do NAT**: logado como usuário B (mesmo IP/`localhost` do teste de A), imediatamente após A esgotar seus limites de `/chat` e `/compact` — B recebe `200` normalmente em ambas as rotas, confirmando que o limite é por usuário, não por IP compartilhado. `/auth/login` continua por IP (usuário ainda não autenticado nesse ponto) — ver limitação conhecida no roadmap.
- Uso normal do app (poucas mensagens por minuto) não é afetado pelos limites.

### 10. SQL injection

O que testa: se algum ponto do backend monta uma query SQL grudando (concatenação/f-string/`.format()`) valor de input externo direto na string, em vez de usar placeholder (`%s`) com o valor passado à parte para o driver. Diferente dos itens anteriores, **isso não dá pra testar pelo DevTools do navegador** — é uma falha server-side, no código Python; a verificação foi por leitura de código, não por interação em runtime.

Como foi feito: auditadas as chamadas `cur.execute(...)` em `app/repositories/*.py` e `app/routers/admin.py` (todo o SQL cru do backend vive majoritariamente ali, via `psycopg`, sem ORM), conferindo se cada uma usa placeholder `%s` com valores passados à parte, ou se algum trecho interpola valor dinâmico direto na string antes do `execute()`. Como placeholder `%s` protege **valores** mas não protege **identificadores** (nome de tabela/coluna) nem palavras-chave SQL (ex.: direção `ASC`/`DESC` de um `ORDER BY`) — esse tipo de coisa exigiria lista branca, não dá pra parametrizar —, foi feita uma segunda passada específica: busca por todas as ocorrências de `ORDER BY` no backend inteiro para confirmar que nenhuma coluna nem direção vem de input do cliente.

Resultado: **nenhuma vulnerabilidade encontrada.**

- Toda query com valor dinâmico usa `%s` com os valores passados como tupla separada para `execute()` — nunca concatenados/formatados na própria string SQL. Isso vale também para a busca por conteúdo (`GET /sessions/search`, `buscar_mensagens`/`buscar_sessoes_por_titulo` em `repositories/sessions.py`): o termo do usuário vira `f"%{termo}%"` **em Python**, mas esse valor pronto é passado como parâmetro `%s` do `ILIKE %s` — nunca colado na string SQL. É a forma segura de fazer wildcard com `LIKE`/`ILIKE`.
- Duas queries (`atualizar_usuario` em `users.py` e `editar_conhecimento` em `knowledge.py`) montam a cláusula `SET` dinamicamente via f-string, mas só com fragmentos literais fixos do próprio código (`"email = %s"`, `"titulo = %s"` etc.), escolhidos por `if campo is not None` — nunca a partir de nome de coluna vindo de input externo. Os valores em si sempre passam por `%s`/tupla. É o padrão comum e seguro de "atualizar só os campos informados". Mesmo padrão em `GET /admin/cache-stats` e `GET /admin/dashboard` (`admin.py`, fora de `repositories/`): a f-string ali só escolhe entre strings literais fixas (ex.: `"WHERE user_id = %s"` ou `""`) conforme um filtro foi passado ou não — nunca monta nome de coluna a partir de input.
- **A busca da base de conhecimento** (por título/conteúdo/categoria/autor, na aba Base de Conhecimento) continua sendo feita inteiramente no cliente (`.filter()`/`.includes()` em JS) — só a busca de **conversas** (`Ctrl+K`, `/sessions/search`) e o dashboard viraram consultas SQL server-side desde a introdução dessas features.
- **Nenhuma ocorrência de `ORDER BY` no backend é dinâmica** — toda coluna e toda direção (`ASC`/`DESC`) usada é um literal fixo escrito no código; não existe endpoint que aceite algo como `?order_by=` ou `?dir=` do cliente.

## Fora de escopo (roadmap)

Escrita/execução real no NX (NXOpen), log de auditoria de acesso administrativo, `Strict-Transport-Security` (HSTS) quando o app rodar atrás de TLS de verdade.

**Limitação conhecida — `/auth/login` por IP em rede com NAT.** Diferente de `/chat`/`/compact`, o rate limit de login (5/min) é por IP porque o usuário ainda não está autenticado nesse ponto — não há `user_id` disponível como chave. Numa rede corporativa onde todo mundo sai pelo mesmo IP externo, isso significa que o teto de 5 tentativas/min é compartilhado pela empresa toda: numa manhã de pico com vários engenheiros logando ao mesmo tempo, alguém pode levar `429` mesmo digitando a senha certa. Mitigações possíveis quando isso incomodar na prática: teto mais folgado, um limite combinado por email tentado (em vez de só por IP), ou CAPTCHA — nenhuma foi implementada agora para não aumentar o escopo da POC além do necessário.

**Medição das otimizações de tokens (concisão de tom, dedup de RAG por sessão, `resumo_rag`).** As três otimizações acima foram implementadas e commitadas juntas; o ideal para atribuir o ganho de cada uma isoladamente seria medir `AVG(input_tokens)`, `AVG(output_tokens)` e `AVG(cache_read_input_tokens)` em `cache_usage_log` antes/depois de cada uma, espaçadas por alguns dias de uso real — não foi feito aqui por decisão explícita de entregar tudo de uma vez. Fica como próximo passo, se for necessário justificar o ganho de cada otimização separadamente para a diretoria.

**Tarifa de pico da DeepSeek não é fixa.** A DeepSeek anunciou que vai adotar tarifa dobrada (2x) em horário de pico (fuso de Pequim), sem data efetiva definida no momento em que este provider foi integrado. Horário comercial em Piracicaba cai no fora-de-pico de Pequim, então tende a favorecer — mas o preço não está travado; vale conferir a documentação oficial periodicamente e não assumir `PRECO_MISS`/`PRECO_HIT`/`PRECO_OUTPUT` (`app/config.py`) como permanentes.

**Suporte a imagem não verificado.** O anexo/paste de imagem no chat foi removido por precaução (não confirmamos se `deepseek-v4-flash` aceita input de visão no formato OpenAI-compatible). Se a DeepSeek confirmar suporte no futuro, dá pra reativar: reintroduzir a conversão de imagem pra `{"type":"image_url",...}` em `app/llm.py`, remover o bloqueio em `chat.py` e a prop `imagensHabilitadas={false}` fixa em `ChatPage.tsx`.
