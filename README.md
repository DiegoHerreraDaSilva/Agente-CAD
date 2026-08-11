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

O agente é **estritamente consultivo** — não executa nada no NX. LLM: **DeepSeek** (`deepseek-v4-flash`), com thinking mode desligado explicitamente. Sem suporte a anexo/paste de imagem no chat (a DeepSeek não suporta visão).

## Stack

Backend em Python (FastAPI + Uvicorn), streaming via SSE, SDK `openai` (a API da DeepSeek é OpenAI-compatible — `base_url="https://api.deepseek.com"`). Embeddings do RAG via **Voyage AI** (`voyageai`). Banco **PostgreSQL 16 com a extensão `pgvector`** (imagem `pgvector/pgvector:pg16`) rodando em Docker — só o banco; o backend roda em venv local. Frontend em **React + TypeScript (Vite)**, com `react-router-dom` para navegação client-side, **Tailwind CSS v4** (`@tailwindcss/vite`, CSS-first — sem `tailwind.config.js`) e **`next-themes`** para o tema claro/escuro. Em produção, o build estático (`frontend/dist`) é servido pelo próprio FastAPI — um único processo. O backend usa o pacote `truststore` para confiar no certificado da rede corporativa ao chamar APIs externas (DeepSeek, Voyage — rede com inspeção TLS) — como `truststore.inject_into_ssl()` patcheia o SSL do processo inteiro, todos os clients herdam essa confiança automaticamente, sem config por client.

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
├─ role ('engineer'|      ├─ resumo (texto, /compact)  ├─ conteudo
│         'admin')        ├─ rag_injetadas (jsonb)     └─ criado_em
├─ memoria (texto livre)  ├─ pinned (favoritar)
├─ must_change_senha      ├─ criado_em
└─ criado_em              └─ atualizado_em

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

Ver seção "Postura de segurança" para CORS, headers HTTP e rate limiting.

### RAG (recuperação semântica da base de conhecimento)

Em vez de mandar a base inteira no prompt, as entradas aprovadas são embeddadas com a **Voyage AI** e guardadas na coluna `knowledge_entries.embedding` (`vector(1024)`, `pgvector`), com índice HNSW de cosseno. O embedding é gerado automaticamente quando uma entrada é **aprovada**, **criada** (pelo admin, já aprovada) ou **editada** (se aprovada) — os hooks vivem em `app/repositories/knowledge.py`. A Voyage distingue `input_type` `"document"` (ao indexar) de `"query"` (ao buscar), o que melhora a recuperação. Backfill inicial: `scripts/reindex_knowledge.py`.

A cada `/chat`, `recuperar_conhecimento(pergunta, rag_injetadas, turno_atual)` embedda a pergunta, busca o dobro de candidatas (top-2N por `ORDER BY embedding <=> %s`) e descarta as abaixo do limiar de score (`RAG_LIMIAR`, default 0.4). Se a Voyage cair, retorna `([], rag_injetadas inalterado)` e o chat segue **sem** conhecimento recuperado (degradação graciosa — não cai de volta na base inteira). Parâmetros e modelo (`VOYAGE_MODEL`, `EMBEDDING_DIM`, `RAG_TOP_N`) ficam em `app/config.py`.

**Dedup por sessão.** `chat_sessions.rag_injetadas` guarda um mapa `{entry_id: turno_injetado}` das entradas já mandadas nesta conversa. Ao montar o top-N (default 4) a partir das candidatas, uma entrada já injetada há **menos** de `RAG_JANELA_REINJECAO` turnos (default 10) é pulada — mas a lista é **completada** com a próxima melhor candidata, nunca simplesmente encolhida, para não perder contexto útil em conversas longas. Se ninguém a substituir nesta rodada, ela permanece disponível e pode ser selecionada de novo depois. Ao rodar `/compact`, `rag_injetadas` é zerado **na mesma transação** que apaga `chat_messages` (`apagar_mensagens` em `app/repositories/sessions.py`) — senão uma entrada injetada só antes da compactação ficaria marcada como "já mandada" para sempre, mesmo sem o detalhe ter sobrevivido no resumo.

**`resumo_rag` (versão condensada para injeção).** Recuperação e injeção têm objetivos opostos de tamanho: o embedding sempre usa `conteudo` completo (mais texto ajuda a busca), mas o texto **injetado** no turno atual usa `COALESCE(resumo_rag, conteudo)` — a coluna `resumo_rag` é gerada automaticamente (mesmo hook do embedding) só para entradas com mais de `RESUMO_RAG_MIN_CHARS` (default 3200, ~800 tokens); entradas curtas já são o caso ótimo e ficam com `resumo_rag = NULL`, caindo de volta no conteúdo completo. Falha ao gerar o resumo não quebra a aprovação/criação (mesmo padrão de degradação graciosa do embedding). Backfill/reprocessamento: `scripts/backfill_resumo_rag.py`.

### Tom e regras de forma do agente

O bloco de tom (`montar_system_prompt` em `app/prompt.py`) é único para todos os usuários — direto e prático, mas justificando recomendações não óbvias. Junto dele, um conjunto fixo de regras de forma: não recapitular a pergunta, não anunciar o que vai fazer, não terminar com um resumo do que já foi dito, referenciar informação já dada na conversa em vez de repeti-la, nunca afirmar que o engenheiro já viu/sabe/praticou algo a menos que isso tenha aparecido literalmente no histórico de mensagens ou no resumo injetado, e não ser proativo (sem propor exercícios ou próximos passos que não foram pedidos). Essas regras cortam só a **forma** da resposta — a explicação técnica em si não é afetada.

### Fluxo de uma mensagem de chat

```
POST /chat {session_id, pergunta}
  → valida sessão e login
  → grava a pergunta em chat_messages
  → monta o histórico completo (multi-turn) da sessão, saneado de imagens antigas (ver sanitizar_historico_para_llm)
  → RAG: embedda a pergunta (Voyage) e recupera top-N entradas por similaridade (pgvector),
    deduplicando contra o que já foi injetado nesta sessão
  → system prompt: [tom fixo] + [memória pessoal] + [resumo]  (string única)
  → turno atual: [conhecimento recuperado (se houver)] + [pergunta]
  → app.llm.resposta_stream(...) — streaming SSE token a token, thinking mode desligado
  → ao final: captura uso de tokens (incl. cache automático) e grava a resposta + o log de custo
```

Erros de sobrecarga/limite da API (mesmo no meio do streaming) são traduzidos por `app/llm.py` em 4 exceptions genéricas (`LLMSobrecarregado`, `LLMLimiteRequisicoes`, `LLMConexaoFalhou`, `LLMErro`) e viram uma mensagem amigável no chat, sem derrubar a conexão. `/compact` usa `max_tokens=4096` na chamada não-streaming que gera o resumo — ambos os limites foram calibrados para não cortar respostas longas no meio.

### LLM: DeepSeek

O backend chama a DeepSeek (API OpenAI-compatible, `pip install openai`, `base_url="https://api.deepseek.com"`) através de uma seam única, **`app/llm.py`** — nenhum outro módulo importa o SDK `openai` ou toca em `llm_client`/`LLM_MODEL` (`app/config.py`) diretamente. Os 3 pontos que precisam de LLM (`/chat` streaming, `/compact` resumo de sessão, `gerar_resumo_rag` em `knowledge.py`) chamam só `resposta_stream()`/`resposta_simples()`. Sem suporte a imagem no chat — a DeepSeek não tem visão.

**Usage normalizado.** `UsoNormalizado` (dataclass em `llm.py`) é o shape que `registrar_uso_cache` grava em `cache_usage_log`:

| `UsoNormalizado` | Campo da DeepSeek |
|---|---|
| `input_tokens` | `prompt_cache_miss_tokens` |
| `cache_creation_input_tokens` | sempre `0` (a DeepSeek não tem conceito de "cache write" pago à parte) |
| `cache_read_input_tokens` | `prompt_cache_hit_tokens` |
| `output_tokens` | `completion_tokens` |

No formato OpenAI-compatible, receber `usage` num response em streaming exige `stream_options: {"include_usage": True}` — sem isso, o último chunk não traz os tokens.

**Thinking mode.** A DeepSeek roda em modo "thinking" (reasoning) por padrão — se ficar ligado, cada resposta gasta muito mais tokens de saída (e dinheiro) do que parece. O request explicita `extra_body={"thinking": {"type": "disabled"}}` pra desligar de vez (`thinking` é extensão específica da DeepSeek, fora do schema padrão OpenAI — o SDK só aceita esse tipo de parâmetro via `extra_body`). Sinal de sanidade: numa pergunta de uma linha, `completion_tokens` deve ficar em dezenas, não centenas — se vier alto, o thinking está ligado.

**Cache automático.** Diferente de APIs que exigem marcação explícita de breakpoint, a DeepSeek cacheia sozinha o prefixo repetido entre chamadas (sem nenhum parâmetro no request) — o `system` (tom + memória + resumo) e o histórico da conversa tendem a se repetir turno a turno, então o prefixo comum é lido do cache automaticamente.

**Histórico com imagem legada.** O chat não aceita anexo/paste de imagem hoje (a DeepSeek não tem visão). Mensagens de sessões antigas podem conter uma marcação Markdown com a data URL inteira de uma imagem (`![imagem colada](data:...)`, potencialmente megabytes). `app/prompt.py:sanitizar_historico_para_llm` substitui esse conteúdo por um placeholder curto antes de montar o histórico pro LLM (`chat.py`), pra não estourar a janela de contexto da DeepSeek nem gastar tokens à toa.

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

`ChatPage` usa o hook `useChatStream` para consumir o SSE de `/chat` token a token e `lib/markdown.tsx` para renderizar a resposta (parser leve próprio, sem dependência externa — suporta negrito/itálico/código/listas/tabelas GFM e a extensão de imagem `![](data:...)`, usada só para exibir imagens de mensagens antigas do histórico — ver seção "LLM: DeepSeek"). `AdminPage` carrega `ChatPage`/`AdminPage` via `React.lazy` — o bundle do painel admin só é baixado por quem realmente abre `/admin`.

Build (`npm run build`) gera `frontend/dist`, servido pelo FastAPI: os arquivos JS/CSS ficam em `/assets` (via `StaticFiles`) e qualquer rota que não seja de API cai num fallback que devolve `index.html` — o roteamento de fato acontece no navegador (react-router).

### Interface e design system

O CSS (`frontend/src/styles/global.css`) segue o design system Schwaben: **Tailwind CSS v4** via `@import "tailwindcss";` (sem `tailwind.config.js`/`postcss.config.js` — o plugin `@tailwindcss/vite` cuida de tudo), tokens de cor em `:root` (tema claro) e `.dark` (tema escuro, aplicado por padrão), cantos de **14px** em card/modal/cartão de login (8px em botão/input, pill em badge/chip), e a assinatura visual `.card`: superfície em gradiente sutil, brilho (`hairline`) no topo, sombra, e um contorno luminoso na base que acende no hover.

- **Tema**: `next-themes` (`ThemeProvider attribute="class" defaultTheme="dark"` em `main.tsx`) alterna a classe `dark` no `<html>`. O botão de troca (`components/layout/ThemeToggle.tsx`, ícone Sun/Moon) fica embutido no `Header` — visível no chat e no admin.
- **`cn()`** (`lib/utils.ts`, `clsx` + `tailwind-merge`) — helper padrão para montar className condicional em componentes novos.
- Componentes existentes usam classes semânticas próprias (`.btn-primario`, `.sessao-item`, `.modal`, `.badge`, `.stat-card` etc.), estilizadas com os tokens de tema (`var(--accent)`, `var(--surface)`, `var(--text-muted)` etc.) em `global.css`. Um componente novo deve usar classes utilitárias Tailwind diretamente, em vez de criar mais classes semânticas.
- `select option { color: #000; background: #fff; }` é proposital: o menu nativo do `<select>` não herda os tokens de tema, e forçar só a cor do texto (sem fundo) deixava a lista ilegível quando o navegador desenha o popup com fundo escuro por padrão (SO em dark mode).

### Produtividade no chat

- **Atalhos de teclado**: `Ctrl+K` abre a busca, `n` cria uma sessão nova (fora de um campo de texto — `Ctrl+N` não dá pra usar aqui: é um atalho reservado do navegador para abrir nova janela, que nenhuma página consegue interceptar), `/` foca o campo de pergunta, `?` abre o modal de ajuda (`HelpModal.tsx`, lista todos os atalhos e o comando `/compact`), `Esc` fecha busca/ajuda, `Enter` envia e `Shift+Enter`/`Ctrl+Enter` quebra linha ou força o envio.
- **Busca global** (`Ctrl+K`, `SearchModal.tsx`): consulta `GET /sessions/search?q=` com debounce de 250ms, retornando sessões cujo título bate e mensagens cujo conteúdo bate (com um trecho de contexto ao redor do termo) — resultado de mensagem abre a sessão correspondente.
- **Templates de prompt** (`SnippetsMenu.tsx`): salvos por usuário em `prompt_snippets`, acessíveis pelo ícone de template no `ChatInput`; escolher um insere o texto no campo (concatenando se já houver algo digitado).
- **Favoritar/fixar sessão**: ícone de estrela em cada item da sidebar (`PATCH /sessions/{id}/pin`); sessões fixadas aparecem primeiro, numa seção separada ("Fixadas"). Excluir uma sessão fixada mostra um aviso de confirmação diferente, avisando que ela está fixada.
- **Exportar conversa** (`lib/exportSession.ts`): baixa a sessão atual como um arquivo `.md`, com autor e timestamp de cada mensagem.
- **Sugestões de follow-up** (`FollowUpChips.tsx`): depois de cada resposta do agente, três chips fixos ("Pode detalhar mais esse ponto?", "Tem um exemplo prático disso?", "Resume isso em tópicos.") que reenviam o texto ao serem clicados.
- **Regenerar / editar mensagem**: o botão de regenerar (só na última resposta) chama `POST /sessions/{id}/regenerate`, que apaga a última pergunta+resposta no backend e devolve a pergunta para o front reenviar via `/chat` (fluxo normal de envio, sem duplicar lógica). Editar uma mensagem do usuário chama `DELETE /sessions/{id}/messages/{message_id}/rest` (apaga a mensagem e tudo depois dela) e reenvia o texto editado do mesmo jeito.
- **Anexar arquivo de texto**: botão de anexo (`ChatInput.tsx`) ou arrastar-e-soltar direto na barra de input — lê `.txt/.log/.md/.csv/.json/.xml` via `FileReader` e injeta o conteúdo num bloco de código no campo de pergunta (puramente client-side; não sobe pro backend como arquivo, vira só texto na mensagem).
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
3. Streaming de chat funciona; memória pessoal influencia o tom das respostas.
4. Sessões: criar, renomear, excluir, e o histórico persiste ao recarregar.
5. `/compact` resume e limpa mensagens antigas; a sessão volta a responder a partir do resumo.
6. Painel `/admin`: aba de usuários (criar, editar, resetar senha, excluir — exceto a própria conta), aba de base de conhecimento (aprovar/rejeitar pendências de `/compact`) e aba de economia de cache (com filtro por usuário).
7. `GET /knowledge` (autenticado) lista só a base compartilhada aprovada; `curl -i` sem sessão retorna 401 em qualquer rota protegida.
8. Após `/compact`, a entrada some do prompt do chat até um admin aprová-la em `/admin`; rejeitar exclui a linha de `knowledge_entries` mas não altera `chat_sessions.resumo` — a sessão do usuário continua exibindo o resumo normalmente.
9. Base de conhecimento: editar uma entrada pendente/aprovada, excluir uma aprovada, buscar por texto, e criar uma entrada manualmente (deve aparecer já como "Aprovada").
10. Botão de copiar em mensagens do agente copia o texto para a área de transferência.
11. `curl -i http://localhost:8001/` (rodando o build de produção, não `npm run dev`) mostra `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` e `Content-Security-Policy` na resposta; console do navegador sem erros de CSP ao usar o app normalmente (chat, painel admin).
12. Rate limiting: 6 tentativas seguidas de `POST /auth/login` com senha errada → a 6ª retorna `429`; 21 chamadas seguidas a `POST /chat` → a 21ª retorna `429`; 11 chamadas seguidas a `POST /sessions/{id}/compact` → a 11ª retorna `429`.
13. Respostas do chat começam direto no conteúdo (sem recapitular a pergunta) e não terminam com um resumo do que foi dito.
14. Numa mesma sessão, injetar uma entrada no turno 1 e perguntar de novo sobre o mesmo tema no turno 2 **não** reinjeta (a entrada não aparece nas `entradas` retornadas). No turno 15 (>`RAG_JANELA_REINJECAO`=10 turnos depois), a mesma pergunta reinjeta e grava `{"<id>": 15}` em `chat_sessions.rag_injetadas` (o valor antigo é sobrescrito, não mantido) — a partir daí, ela só volta a ser candidata a partir do turno 25. Rodar `/compact` zera `rag_injetadas` para `{}`.
15. Aprovar/criar uma entrada de conhecimento longa (>`RESUMO_RAG_MIN_CHARS`) gera `resumo_rag`; uma entrada curta fica com `resumo_rag = NULL` e a injeção usa o conteúdo completo (fallback via `COALESCE`).
16. Subir o app sem `DEEPSEEK_API_KEY` falha rápido no startup com mensagem clara (`app/config.py`), em vez de erro obscuro na primeira mensagem de chat.
17. Pergunta de uma linha no chat → `completion_tokens` (mapeado em `cache_usage_log.output_tokens`) fica em dezenas, não centenas (thinking mode desligado); 2º turno da mesma sessão com prefixo repetido registra `cache_read_input_tokens > 0`; não há botão de anexar imagem no chat.
18. `/admin/cache-stats` calcula `custo_real_usd`/`economia_usd` com os preços da DeepSeek (`PRECO_MISS`/`PRECO_HIT`/`PRECO_OUTPUT`) e reflete a economia real do cache automático.
19. `Ctrl+K` abre a busca e encontra sessões/mensagens por conteúdo; `n` (fora de um campo de texto) cria sessão nova; `/` foca o input; `?` abre o modal de ajuda.
20. Fixar uma sessão (estrela na sidebar) a move para a seção "Fixadas"; excluí-la mostra um aviso de confirmação diferente do de uma sessão comum.
21. Editar uma mensagem antiga do usuário e reenviar trunca as mensagens seguintes (backend e tela) e gera uma nova resposta; regenerar a última resposta refaz só ela, sem duplicar a pergunta.
22. Soltar um arquivo `.txt` na barra de input (ou usar o botão de anexo) injeta o conteúdo no campo de pergunta.
23. Rolar para cima durante o streaming de uma resposta não puxa o scroll de volta ao fim; o botão "↓ Novas mensagens" aparece e, ao clicar, volta pro fim.
24. `GET /admin/dashboard?dias=30` retorna números consistentes entre `ranking` (por usuário) e `sessoes_ativas` (por sessão) — a soma das sessões de um usuário no ranking bate com o total dele, sem inflar por causa de JOIN cruzado com `cache_usage_log`.

## Postura de segurança

### Cookie de sessão

O cookie de sessão tem os flags `HttpOnly` e `SameSite` definidos — não é legível via `document.cookie`/JavaScript, então mesmo um XSS na página não conseguiria exfiltrá-lo.

### Cadeia de autorização por rota

Toda rota protegida passa pela cadeia de dependências do FastAPI `usuario_atual → requer_senha_atualizada → admin_atual` (`app/deps.py`): sem sessão → `401`; logado mas com `must_change_senha=True` → `403` em qualquer rota fora de `/change-password`; logado como `engineer` tentando acessar rota de `admin_atual` → `403`.

- Toda rota do painel admin usa `admin_atual` (que já embute as duas dependências anteriores).
- Chat, sessões, `/snippets`, `/knowledge` e `/auth/me/memoria` usam `requer_senha_atualizada`.
- `usuario_atual` (mais fraco) só aparece em `/auth/me` e `/auth/change-password` — precisam funcionar mesmo com `must_change_senha=True`, senão o usuário ficaria travado num loop de 403 sem conseguir trocar a própria senha.
- Rotas públicas de fato: `/auth/register` (sempre `403`, cadastro desabilitado), `/auth/login`, `/auth/logout`, `/logo.png`, `/health`, fallback de SPA — nenhuma expõe dado.
- `POST /auth/logout` não tem dependência de auth — chamá-lo deslogado só limpa uma sessão já vazia, sem risco.

### Isolamento entre usuários (IDOR)

Toda rota que recebe um `session_id`/recurso por parâmetro confere posse antes de agir (`sessao_do_usuario`/consultas equivalentes com `WHERE user_id = usuario_atual.id`) — um usuário não consegue acessar sessão, mensagem ou recurso de outro usuário só por adivinhar/capturar o ID.

### XSS em campos livres

O chat e o resumo de sessão renderizam Markdown → HTML via `dangerouslySetInnerHTML` (`MessageBubble.tsx`, `ResumoBox.tsx`, parser próprio em `lib/markdown.tsx`, sem lib de sanitização externa). Conteúdo controlado pelo usuário (título de sessão, memória pessoal, entrada de base de conhecimento) é sempre escapado antes de renderizar — não vira HTML/JS executável. A `Content-Security-Policy` (abaixo) é a segunda camada de defesa caso um bug no parser deixe passar algo.

### Exposição da chave de API

`DEEPSEEK_API_KEY` só existe no processo do backend — nunca aparece em request/response para o cliente nem no bundle do frontend.

### Erros sem vazamento de detalhe interno

Respostas de erro não expõem stack trace nem caminho de arquivo Python — só a mensagem tratada (`LLMErro`/`HTTPException` com `detail`).

### Headers de resposta HTTP e CORS

Não há `CORSMiddleware` no backend — front e back são sempre a mesma origem do ponto de vista do navegador (proxy do Vite em dev, mesmo processo FastAPI em produção), então nunca há necessidade de CORS; `allow_origins=["*"]` abriria a API (autenticada por cookie de sessão) para leitura por qualquer site.

Um middleware em `main.py` (`security_headers`) anexa três headers em toda resposta:

- `X-Content-Type-Options: nosniff` — impede o navegador de reinterpretar o tipo de um arquivo diferente do `Content-Type` declarado.
- `X-Frame-Options: DENY` — impede que o app seja carregado dentro de um `<iframe>` em outro site (clickjacking).
- `Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'` — bloqueia por padrão script/estilo/imagem/conexão de origem diferente da própria. `img-src data:` cobre `data:` URIs em Markdown de mensagens antigas; `style-src 'unsafe-inline'` é necessário porque vários componentes React usam `style={{...}}` inline (`KnowledgeTab`, `UsersTab`).

Esse header só se aplica quando o **FastAPI** serve a resposta — produção (`npm run build` + backend) e chamadas de API mesmo em dev. Rodando `npm run dev`, o HTML vem direto do Vite em `:5173`, sem passar pelo backend; por isso `frontend/index.html` já tem a mesma política numa tag `<meta http-equiv="Content-Security-Policy">`, que cobre esse caso e também é servida dentro do build de produção (as duas coexistem, sem conflito).

Fora de escopo por enquanto: `Strict-Transport-Security` (HSTS) — só faz sentido quando o app rodar atrás de TLS de verdade (hoje é HTTP local, `https_only=False` no `SessionMiddleware`).

### Rate limiting

`slowapi` (`Limiter` em `app/config.py`, registrado em `main.py`), em memória (adequado para um único processo `uvicorn`; múltiplas réplicas exigiriam um backend compartilhado, ex. Redis):

- `POST /auth/login` — 5/min, por IP (`get_remote_address` — ainda não há usuário autenticado nesse ponto).
- `POST /chat` — 20/min, por usuário logado (`get_user_or_ip`, lê `request.session["user_id"]`).
- `POST /sessions/{id}/compact` — 10/min, por usuário logado.

Limite excedido devolve `429`. A chave por usuário (em vez de por IP) em `/chat`/`/compact` importa em rede corporativa com NAT: se fosse por IP, todo mundo atrás do mesmo IP externo compartilharia o mesmo teto — um punhado de engenheiros conversando ao mesmo tempo esgotaria o limite pra todo mundo. Por usuário, cada engenheiro tem seu próprio teto, independente de quantas outras pessoas estão atrás do mesmo IP. `/auth/login` continua por IP porque, nesse ponto, ainda não há `user_id` disponível como chave — ver limitação conhecida no roadmap.

### SQL injection

Todo o SQL cru do backend (`app/repositories/*.py`, `app/routers/admin.py`, via `psycopg`, sem ORM) usa placeholder `%s` com os valores passados como tupla separada para `execute()` — nunca concatenados/formatados direto na string SQL. Isso vale inclusive para busca com wildcard (`GET /sessions/search`): o termo vira `f"%{termo}%"` em Python, mas esse valor pronto é passado como parâmetro `%s` do `ILIKE %s`, nunca colado na string.

Duas queries (`atualizar_usuario` em `users.py`, `editar_conhecimento` em `knowledge.py`) montam a cláusula `SET` dinamicamente via f-string, mas só com fragmentos literais fixos do próprio código (`"email = %s"`, `"titulo = %s"` etc.), escolhidos por `if campo is not None` — nunca a partir de nome de coluna vindo de input externo; os valores em si sempre passam por `%s`. Mesmo padrão em `GET /admin/cache-stats` e `GET /admin/dashboard`. Nenhuma ocorrência de `ORDER BY` no backend é dinâmica — coluna e direção (`ASC`/`DESC`) são sempre literais fixos no código; não existe endpoint que aceite `?order_by=`/`?dir=` do cliente.

A busca da base de conhecimento (por título/conteúdo/categoria/autor, aba Base de Conhecimento) é feita no cliente (`.filter()`/`.includes()` em JS); só a busca de conversas (`Ctrl+K`, `/sessions/search`) e o dashboard são consultas SQL server-side.

## Fora de escopo (roadmap)

Escrita/execução real no NX (NXOpen), log de auditoria de acesso administrativo, `Strict-Transport-Security` (HSTS) quando o app rodar atrás de TLS de verdade, suporte a imagem no chat (a DeepSeek não tem visão), medição isolada do ganho de cada otimização de tokens (concisão de tom, dedup de RAG por sessão, `resumo_rag`) via `AVG(input_tokens)`/`AVG(output_tokens)`/`AVG(cache_read_input_tokens)` em `cache_usage_log`.

**Limitação conhecida — `/auth/login` por IP em rede com NAT.** O rate limit de login (5/min) é por IP porque o usuário ainda não está autenticado nesse ponto — não há `user_id` disponível como chave. Numa rede corporativa onde todo mundo sai pelo mesmo IP externo, o teto de 5 tentativas/min é compartilhado pela empresa toda: numa manhã de pico com vários engenheiros logando ao mesmo tempo, alguém pode levar `429` mesmo digitando a senha certa. Mitigações possíveis: teto mais folgado, um limite combinado por email tentado (em vez de só por IP), ou CAPTCHA.

**Tarifa de pico da DeepSeek não é fixa.** A DeepSeek pode adotar tarifa dobrada (2x) em horário de pico (fuso de Pequim). Horário comercial em Piracicaba cai no fora-de-pico de Pequim, então tende a favorecer — mas o preço não está travado; `PRECO_MISS`/`PRECO_HIT`/`PRECO_OUTPUT` (`app/config.py`) não devem ser tratados como permanentes.
