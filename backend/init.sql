-- Base de conhecimento compartilhada (POC)
-- Executado automaticamente pelo Postgres na primeira subida do container.

-- Extensão de vetores (RAG) — requer a imagem pgvector/pgvector:pg16.
CREATE EXTENSION IF NOT EXISTS vector;

-- Usuários do sistema (autenticação por email/senha).
-- Também é criada no startup do app (idempotente), para volumes já existentes.
CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,
    email      TEXT UNIQUE NOT NULL,
    senha_hash TEXT NOT NULL,
    nivel      TEXT NOT NULL CHECK (nivel IN ('estagiario', 'junior', 'pleno', 'senior')),
    role       TEXT NOT NULL DEFAULT 'engineer',
    memoria    TEXT NOT NULL DEFAULT '',
    must_change_senha BOOLEAN NOT NULL DEFAULT false,
    criado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Sessões de chat e suas mensagens (memória de curto prazo, por usuário).
-- Também criadas no startup do app (idempotente).
CREATE TABLE IF NOT EXISTS chat_sessions (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    titulo        TEXT NOT NULL DEFAULT 'Nova sessão',
    resumo        TEXT NOT NULL DEFAULT '',
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    papel      TEXT NOT NULL CHECK (papel IN ('user', 'assistant')),
    conteudo   TEXT NOT NULL,
    criado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages (session_id, id);

-- Log de uso de prompt caching por resposta do chat (para medir economia real).
CREATE TABLE IF NOT EXISTS cache_usage_log (
    id                          SERIAL PRIMARY KEY,
    session_id                  INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id                     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    input_tokens                INTEGER NOT NULL,
    cache_creation_input_tokens INTEGER NOT NULL,
    cache_read_input_tokens     INTEGER NOT NULL,
    output_tokens               INTEGER NOT NULL,
    criado_em                   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- status: 'pendente' (aguardando aprovação de admin, ex.: resumos de /compact),
-- 'aprovado' (entra no prompt do chat) ou 'rejeitado'.
CREATE TABLE IF NOT EXISTS knowledge_entries (
    id         SERIAL PRIMARY KEY,
    titulo     TEXT        NOT NULL,
    conteudo   TEXT        NOT NULL,
    categoria  TEXT        NOT NULL,
    criado_por TEXT        NOT NULL,
    status     TEXT        NOT NULL DEFAULT 'aprovado'
               CHECK (status IN ('pendente', 'aprovado', 'rejeitado')),
    embedding  vector(1024),
    criado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índice de similaridade por cosseno (RAG). HNSW não exige calibração de lists.
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding
    ON knowledge_entries USING hnsw (embedding vector_cosine_ops);

INSERT INTO knowledge_entries (titulo, conteudo, categoria, criado_por) VALUES
(
    'Associatividade em espelhamento de assembly',
    'Ao espelhar componentes em um assembly no NX, prefira o comando Mirror Assembly com a opção de manter associatividade. Assim, alterações no componente original propagam para o espelhado. Evite espelhar geometria "morta" quando a intenção é manter o vínculo paramétrico.',
    'Assembly',
    'equipe_engenharia'
),
(
    'Paramétrica vs. Synchronous Modeling',
    'Use modelagem paramétrica (feature-based) quando o histórico e a intenção de projeto precisam ser preservados e editados. Use Synchronous Modeling para edições rápidas em geometria importada ou sem histórico, onde recriar a árvore de features não compensa.',
    'Modelagem',
    'equipe_engenharia'
),
(
    'Boas práticas de nomenclatura de features',
    'Nomeie features e datums de forma descritiva (ex.: DATUM_FURACAO_A, EXTRUDE_FLANGE) em vez dos nomes automáticos. Isso reduz erros em revisões e facilita a manutenção de assemblies grandes por outros engenheiros.',
    'Boas práticas',
    'equipe_engenharia'
),
(
    'WAVE Geometry Linker e projeto top-down',
    'O WAVE Geometry Linker permite trazer geometria de referência (curvas, faces, corpos, datums) de uma peça para outra dentro de um assembly, mantendo associatividade. É a base do projeto top-down: você modela um "control structure" ou peça de referência com a intenção de projeto (envelope, interfaces, pontos de montagem) e as peças filhas linkam essa geometria em vez de recriá-la. Vantagem: uma mudança no controle propaga automaticamente. Risco: cada link do WAVE cria uma dependência inter-peças; em projetos grandes, isso pode gerar cadeias de dependência difíceis de rastrear e travamentos de update lentos. Boas práticas: linkar o mínimo necessário (não o corpo inteiro se só uma face importa), documentar de onde vêm os links, e evitar links circulares entre peças do mesmo assembly.',
    'Assembly',
    'equipe_engenharia'
),
(
    'Expressions e parametrização robusta',
    'Expressions são a espinha dorsal da modelagem paramétrica no NX: qualquer valor numérico de uma feature pode virar uma expressão nomeada, referenciada por outras expressões. Boas práticas: nomear expressões de forma descritiva (ex.: "largura_flange" em vez de "p21"), agrupar por finalidade usando prefixos, e evitar números mágicos direto nas features. Para peças que participam de famílias (family of parts) ou que têm variações dimensionais frequentes, concentrar as expressões-chave no topo da lista facilita auditoria. Cuidado com expressões interpart (que referenciam expressões de outra peça via WAVE): elas criam a mesma dependência de atualização que o WAVE Geometry Linker, e devem ser usadas com moderação em assemblies grandes por causa do tempo de recálculo.',
    'Modelagem',
    'equipe_engenharia'
),
(
    'Sketches totalmente restringidos (fully constrained)',
    'Um sketch bem construído deve estar totalmente restringido (fully constrained), indicado no NX pela cor das curvas (tipicamente ficam em uma cor diferente, ex. verde/preto conforme o tema, quando 100% restringidas). Sketches subrestringidos permitem que a geometria se mova de forma imprevisível quando expressões ou features upstream mudam, e são a causa mais comum de "geometria voando" após uma edição. Regra prática: usar cotas (dimensões) e restrições geométricas (coincidência, tangência, paralelismo, simetria) até não sobrar nenhum grau de liberdade, e preferir restrições geométricas explícitas a cotas quando a intenção for de posicionamento relativo (ex.: usar simetria em vez de duas cotas iguais).',
    'Modelagem',
    'equipe_engenharia'
),
(
    'Reference Sets em assembly',
    'Reference Sets controlam quanta geometria de uma peça é exibida quando ela é referenciada em um assembly maior — por exemplo, um Reference Set "simplified" pode mostrar só o envelope externo de um componente complexo, acelerando a navegação em assemblies grandes. Isso é diferente de simplesmente ocultar camadas: o Reference Set é salvo com a peça e pode ser trocado por componente dentro do assembly sem afetar o modelo mestre. Boas práticas: definir pelo menos um Reference Set "Model" (completo) e um "Empty" ou "Simplified" para peças-padrão (parafusos, buchas) que aparecem centenas de vezes e não precisam de detalhe visual no assembly geral.',
    'Assembly',
    'equipe_engenharia'
),
(
    'Chapa metálica: bend allowance e fator K',
    'Ao modelar peças de chapa metálica (Sheet Metal) no NX, o comprimento da peça planificada (flat pattern) depende de como o software calcula o material que "estica" na dobra. O método mais usado é o Bend Allowance, baseado no fator K (K-factor): a razão entre a posição da linha neutra da chapa (onde não há tração nem compressão) e a espessura do material. Fator K típico varia entre 0.33 e 0.5 dependendo do material e do raio de dobra relativo à espessura. Usar o fator K errado para o material real (aço, alumínio, inox) gera peças planificadas com dimensões incorretas, que só aparecem como erro depois de cortadas. Sempre validar o fator K com o fornecedor/máquina de dobra antes de liberar desenhos para produção.',
    'Chapa metálica',
    'equipe_engenharia'
),
(
    'GD&T: referências datum (Datum Reference Frame)',
    'Um Datum Reference Frame (DRF) bem definido é a base de qualquer tolerância geométrica (GD&T) funcional. A ordem dos datums na anotação de tolerância (primário, secundário, terciário) define a sequência de restrição de graus de liberdade: o datum primário normalmente restringe 3 graus (um plano), o secundário mais 2, e o terciário o último grau de liberdade rotacional. Erros comuns: escolher como datum uma superfície que não é acessível ou repetível na inspeção real, ou inverter a ordem dos datums sem entender o impacto na medição. Datums devem corresponder a superfícies de localização/fixação reais do processo de fabricação e montagem — não apenas à geometria mais "óbvia" do desenho.',
    'GD&T',
    'equipe_engenharia'
),
(
    'PMI e Model-Based Definition (MBD)',
    'Product Manufacturing Information (PMI) é o conjunto de anotações (cotas, tolerâncias GD&T, notas, acabamento superficial) aplicado diretamente ao modelo 3D, em vez de (ou além de) um desenho 2D tradicional. Isso viabiliza o Model-Based Definition (MBD): o modelo 3D anotado passa a ser o documento de engenharia oficial, consumido diretamente por CAM, metrologia (CMM) e inspeção. Vantagem: elimina a duplicação e o risco de divergência entre modelo 3D e desenho 2D. Desafio prático: PMI bem-feito exige disciplina de associatividade (as anotações precisam se mover corretamente quando a geometria muda) e um plano de views/cenas organizado, senão a leitura do modelo anotado fica mais confusa que um desenho tradicional.',
    'Documentação técnica',
    'equipe_engenharia'
),
(
    'View Dependent Edit vs edição no modelo',
    'No módulo de Drafting do NX, é possível fazer pequenos ajustes visuais numa view (ex.: esconder uma linha de aresta, mover um texto) via View Dependent Edit, que afeta só aquela view do desenho, sem tocar no modelo 3D. Isso é diferente de editar a feature no modelo, que propaga para todas as views e para o próprio sólido. Erro comum de quem está começando: tentar "consertar" um desenho incorreto usando View Dependent Edit quando o problema real está na geometria do modelo — isso mascara o erro no desenho sem corrigir a causa, e a próxima atualização do modelo pode reintroduzir o problema ou criar inconsistência entre views.',
    'Documentação técnica',
    'equipe_engenharia'
),
(
    'Synchronous Modeling: quando usar Move Face e Recognize Features',
    'Synchronous Modeling permite editar geometria diretamente (mover uma face, mudar um raio) sem depender da árvore de histórico, o que é útil para geometria importada (STEP, IGES) que chega sem features paramétricas. O comando Recognize Features tenta identificar automaticamente furos, rebaixos e boleados na geometria importada e convertê-los em features editáveis. Use Synchronous quando: a peça vem de fornecedor externo sem histórico, ou quando uma edição pontual não justifica recriar a árvore de features inteira. Evite depender só de Synchronous em peças de projeto próprio com muita intenção de projeto (padrões, arrays, relações complexas) — nesses casos a modelagem paramétrica tradicional captura melhor a intenção e facilita mudanças futuras maiores.',
    'Modelagem',
    'equipe_engenharia'
),
(
    'Check-Mate: verificação automática de qualidade de modelo',
    'Check-Mate é a ferramenta do NX para checagens automáticas de qualidade de modelo e conformidade com padrões da empresa — por exemplo, unidades corretas, ausência de geometria "solta" (sheet bodies órfãos), nomenclatura de features conforme convenção, e verificação de propriedades de massa/material preenchidas. Rodar Check-Mate antes de liberar uma peça para o assembly ou para manufatura evita que problemas estruturais do modelo (não geométricos, mas de "higiene" do arquivo) só apareçam tarde, quando já foram propagados para desenhos e listas de material. Times maduros configuram um conjunto de checks obrigatório (custom check) alinhado às convenções internas de nomenclatura e organização de features.',
    'Boas práticas',
    'equipe_engenharia'
),
(
    'Simulação estrutural básica: malha e condições de contorno',
    'Em uma análise estrutural com NX Nastran (ou solver equivalente), a qualidade do resultado depende diretamente da malha (mesh) e das condições de contorno aplicadas, não só da geometria. Elementos de malha muito grandes em regiões de concentração de tensão (furos, filetes pequenos, cantos vivos) subestimam a tensão real; refinar a malha localmente nessas regiões é mais eficiente que refinar o modelo inteiro. Condições de contorno (restrições e cargas) devem representar fisicamente como a peça é fixada e carregada no uso real — engastar uma face inteira quando na prática só um parafuso pontual fixa a peça é um erro comum que superestima a rigidez e mascara falhas reais. Sempre validar resultados de simulação com um caso de teste conhecido (mão-cheia ou ensaio físico) antes de confiar cegamente no resultado numérico.',
    'Simulação',
    'equipe_engenharia'
),
(
    'Interoperabilidade: exportação STEP e JT',
    'STEP (AP203/AP214/AP242) é o formato neutro mais usado para troca de geometria sólida entre sistemas CAD diferentes (ex.: enviar peça para fornecedor que não usa NX); AP242 inclusive suporta PMI. JT (Jupiter Tessellation) é mais leve e usado principalmente para visualização, revisão de projeto e integração com PLM (ex.: Teamcenter), mas não é indicado para reabrir e editar geometria com a mesma precisão de um STEP. Ao exportar STEP para fornecedores externos, vale simplificar Reference Sets e remover dados sensíveis de PMI/anotações internas que não devem ser compartilhados. Erros de tolerância de exportação (muito permissivos) podem gerar geometria com pequenas falhas (gaps, faces não coincidentes) que gera problemas ao reimportar em outro sistema.',
    'Interoperabilidade',
    'equipe_engenharia'
),
(
    'Ajustes ISO e tolerâncias dimensionais em encaixes',
    'Para encaixes entre eixo e furo (ex.: rolamento em um alojamento, pino em um furo), o sistema ISO de ajustes (ISO 286) define tolerâncias padronizadas por letra e número (ex.: H7/g6 para um ajuste deslizante com folga pequena, H7/p6 para um ajuste com interferência leve). Especificar tolerâncias "no olho" (ex.: ±0.05 mm genérico em tudo) sem considerar a função do encaixe gera ou peças que não encaixam (tolerância apertada demais para o processo de fabricação disponível) ou folgas excessivas que comprometem a precisão de montagem. Regra prática: identificar a função do encaixe (deslizante, com guia, fixo com interferência) antes de escolher a classe de tolerância, e verificar se o processo de fabricação (usinagem, chapa, impressão 3D) consegue atingir a tolerância especificada de forma economicamente viável.',
    'GD&T',
    'equipe_engenharia'
),
(
    'Boas práticas de árvore de features (feature tree)',
    'A ordem das features na árvore (feature tree) importa tanto quanto a geometria final: features de reforço estrutural devem geralmente vir antes de furos e rebaixos decorativos, para que edições futuras nesses elementos secundários não quebrem a lógica de features anteriores. Agrupar features relacionadas (ex.: todos os furos de fixação de um mesmo padrão) usando pastas (feature groups) facilita a leitura da árvore por outro engenheiro. Evitar features "quebradas" (marcadas com erro, mas suprimidas ou ignoradas) que ficam acumulando na árvore — cada feature com erro não resolvido é um risco de comportamento inesperado na próxima atualização do modelo ou do assembly.',
    'Boas práticas',
    'equipe_engenharia'
);
