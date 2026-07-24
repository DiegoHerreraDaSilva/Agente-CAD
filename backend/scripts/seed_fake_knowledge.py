"""Popula a base de conhecimento com ~40 entradas FICTÍCIAS de NX/CAD para
testar a qualidade da recuperação (RAG) localmente.

Idempotente: apaga e recria as entradas marcadas com criado_por='seed_ficticio'
a cada execução, então não duplica. Depois de inserir, gera o embedding de cada
uma (precisa de VOYAGE_API_KEY no .env; se faltar, as entradas entram sem
embedding e você pode rodar scripts/reindex_knowledge.py depois).

Rodar a partir de backend/:
    python scripts/seed_fake_knowledge.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg  # noqa: E402

from app.db import _pg_conninfo  # noqa: E402
from app.repositories.knowledge import reindexar_aprovadas  # noqa: E402

MARCADOR = "seed_ficticio"

# (titulo, categoria, conteudo) — temas distintos de propósito, para as perguntas
# de teste conseguirem mapear cada uma a uma entrada específica.
ENTRADAS = [
    ("Extrude: opção Until Extended", "Modelagem",
     "Na feature Extrude do NX, a opção de limite 'Until Extended' estende o corpo até a superfície selecionada mesmo que a face-alvo não cubra toda a seção — o NX prolonga a face imaginariamente. Útil quando a face de parada é menor que o perfil extrudado."),
    ("Blend/Edge Blend com raio variável", "Modelagem",
     "O Edge Blend aceita raio variável ao longo da aresta: adicione pontos com raios distintos para transições suaves. Para cantos onde três arestas se encontram, prefira definir o blend de setback para evitar geometria degenerada."),
    ("Pattern Feature circular", "Modelagem",
     "Para replicar furos ao redor de um eixo, use Pattern Feature no modo Circular, definindo o vetor de rotação e a contagem. Ative 'Create Instance Points' se precisar referenciar os centros depois. Padrões grandes pesam no recálculo."),
    ("Draft (ângulo de saída) para injeção", "Modelagem",
     "Peças de plástico injetado exigem ângulo de saída (draft) nas paredes para desmoldar. Aplique Draft de 1° a 3° a partir de uma face neutra ou linha de partição. Faltando draft, a peça agarra no molde e arranha."),
    ("Shell (parede fina)", "Modelagem",
     "O comando Shell esvazia um sólido deixando parede de espessura constante; selecione as faces a remover. Para espessuras diferentes por face, use a opção de Alternate Thickness. Cantos internos vivos viram concentradores de tensão."),
    ("Boolean Subtract para cavidades", "Modelagem",
     "Para criar uma cavidade, modele o corpo da cavidade e use Boolean Subtract do corpo-alvo. Mantenha o corpo-ferramenta como referência (não consumido) se precisar editar depois, marcando 'Keep Tool'."),
    ("Sketch: restrição de simetria", "Modelagem",
     "No sketch, a restrição de simetria amarra duas entidades em relação a uma linha de centro, garantindo que editar um lado atualize o outro. Prefira simetria a duas cotas iguais quando a intenção for espelhamento."),
    ("Datum CSYS e origem de peça", "Modelagem",
     "Defina um Datum Coordinate System explícito na origem da peça para ancorar sketches e features. Modelar 'flutuando' longe da origem dificulta montagem e importação/exportação, além de confundir a orientação de vistas."),

    ("Constraints de montagem: Touch/Align", "Assembly",
     "No Assembly Constraints, 'Touch Align' encosta faces (Touch = normais opostas, Align = mesma direção). Combine com 'Distance' e 'Angle' para posicionar componentes. Excesso de constraints redundantes gera conflito de solução."),
    ("Arrange de componentes com Pattern Component", "Assembly",
     "Pattern Component replica um componente já montado seguindo um padrão linear/circular, mantendo os constraints. Ideal para parafusos repetidos. Editar o padrão propaga para todas as instâncias."),
    ("Interference Check em assembly", "Assembly",
     "O Interference Check (Clearance Analysis) detecta colisões e folgas insuficientes entre componentes. Rode antes de liberar o assembly; configure um set de folga mínima para flagrar componentes perto demais, não só sobrepostos."),
    ("Exploded View para documentação", "Assembly",
     "Exploded Views afastam os componentes ao longo de vetores para ilustrar a sequência de montagem em desenhos. As posições explodidas são associativas: mudanças no assembly atualizam a explosão. Use trace lines para indicar o caminho."),
    ("Component Groups e carga parcial", "Assembly",
     "Em assemblies grandes, use Component Groups e a opção de carga parcial (partial load) para abrir só o subconjunto de interesse, reduzindo memória e tempo de abertura. Reference Sets 'Empty' ajudam no mesmo objetivo."),

    ("Drafting: escala de vista independente", "Documentação técnica",
     "Cada vista no Drafting pode ter escala própria, independente da folha. Vistas de detalhe (Detail View) tipicamente usam escala maior que a vista principal. Registre a escala na legenda de cada detalhe para não confundir na leitura."),
    ("Section View alinhada vs. desalinhada", "Documentação técnica",
     "Section Views podem ser simples, alinhadas (aligned, giram o corte para o plano) ou offset (corte escalonado). A alinhada é útil em peças radiais; deixar claro o tipo de corte evita interpretação errada de dimensões."),
    ("Auto-dimension vs. cotagem manual", "Documentação técnica",
     "O NX oferece cotagem automática, mas ela raramente segue a intenção funcional. Prefira cotar manualmente a partir de datums funcionais e cadeias de cotas que reflitam como a peça é fabricada e inspecionada."),
    ("Tabela de furos (Hole Table)", "Documentação técnica",
     "Hole Table lista coordenadas e especificação de múltiplos furos referenciados a uma origem, limpando o desenho de dezenas de cotas repetidas. Muito usado em placas e flanges com muitos furos."),

    ("Sheet Metal: flange e bend radius", "Chapa metálica",
     "Ao criar uma Flange no Sheet Metal, o raio de dobra (bend radius) deve respeitar o mínimo do material/processo — raio pequeno demais trinca a dobra. O NX usa os parâmetros globais de Sheet Metal Preferences como default."),
    ("Sheet Metal: alívio de dobra (relief)", "Chapa metálica",
     "Dobras que terminam no meio de uma aresta precisam de alívio (corner/bend relief) para não rasgar o material. O NX oferece relief retangular ou obround; dimensione conforme espessura e processo de dobra."),
    ("Flat Pattern e exportação DXF", "Chapa metálica",
     "O Flat Pattern gera a planificação para corte a laser/puncionadeira; exporte em DXF para a máquina. Confira se linhas de dobra e marcações estão em camadas separadas para o CAM não confundir com contorno de corte."),
    ("Louver e Dimple (conformações)", "Chapa metálica",
     "Recursos de conformação como Louver (venezianas de ventilação) e Dimple (rebaixo) são features de Sheet Metal que não se planificam como dobra simples; o fornecedor precisa do ferramental certo. Confirme viabilidade antes de especificar."),

    ("GD&T: tolerância de posição (position)", "GD&T",
     "A tolerância de posição controla a localização de um furo em relação a datums, tipicamente com modificador MMC (máximo material) que libera bônus de tolerância conforme o furo se afasta do pior caso. É a base do gauging funcional."),
    ("GD&T: perpendicularidade e paralelismo", "GD&T",
     "Perpendicularidade e paralelismo são tolerâncias de orientação relativas a um datum. Não controlam localização — só a inclinação. Um furo pode estar perpendicular e ainda assim fora de posição."),
    ("GD&T: planeza (flatness)", "GD&T",
     "Planeza é uma tolerância de forma que não referencia datum: controla o quão plana uma superfície é entre dois planos paralelos. Usada em faces de vedação e assentamento onde o contato uniforme importa."),
    ("GD&T: circularidade e cilindricidade", "GD&T",
     "Circularidade controla a seção transversal de um cilindro; cilindricidade controla a superfície inteira (forma + retilineidade do eixo). Cilindricidade é mais restritiva e mais cara de inspecionar — use só onde a função exige."),

    ("Nastran: análise modal (frequências)", "Simulação",
     "A análise modal calcula as frequências naturais e modos de vibração da peça, sem carga aplicada. Serve para evitar ressonância com excitações do uso (motores, vibração). Malha grosseira desloca as frequências previstas."),
    ("Simulação térmica: condução e convecção", "Simulação",
     "Numa análise térmica, defina condução no material e convecção nas superfícies expostas (coeficiente h e temperatura ambiente). Erro comum é esquecer a convecção e superestimar a temperatura interna da peça."),
    ("Contato em simulação estrutural", "Simulação",
     "Contatos (bonded, sliding, no-penetration) definem como componentes interagem sob carga. Bonded 'cola' tudo e é otimista; no-penetration é mais realista mas custa convergência. Escolha conforme a montagem real."),
    ("Convergência de malha (mesh convergence)", "Simulação",
     "Para confiar num resultado, refine a malha e verifique se a tensão de pico estabiliza (converge). Se a tensão continua subindo ao refinar, há uma singularidade (canto vivo) — arredonde o canto ou avalie a região de forma diferente."),

    ("STEP AP242 com PMI", "Interoperabilidade",
     "O STEP AP242 carrega, além da geometria, a PMI semântica (tolerâncias legíveis por máquina), viabilizando inspeção e CAM sem desenho 2D. Confirme que o sistema de destino lê AP242, senão a PMI vira só anotação gráfica."),
    ("Parasolid vs. STEP na troca", "Interoperabilidade",
     "Parasolid (.x_t) é o kernel nativo do NX e preserva geometria com máxima fidelidade entre sistemas que usam Parasolid (NX, SolidWorks). STEP é mais universal mas pode introduzir pequenos gaps na conversão de superfícies complexas."),
    ("Importar malha (STL) e reconstruir", "Interoperabilidade",
     "STL traz só malha triangular (sem features nem precisão de superfície), típico de scan 3D ou impressão. Para editar, use ferramentas de Reverse Engineering/Convergent Modeling; não espere um sólido paramétrico limpo direto do STL."),
    ("Teamcenter: check-in/check-out", "Interoperabilidade",
     "No PLM Teamcenter, check-out trava o item para edição exclusiva; check-in devolve e versiona. Esquecer de fazer check-in deixa o item travado para os colegas. Datasets JT são gerados no check-in para visualização leve."),

    ("Layers vs. Reference Sets", "Boas práticas",
     "Layers organizam a visibilidade de objetos dentro de uma peça; Reference Sets controlam o que aparece quando a peça é usada num assembly. São mecanismos diferentes — não use layer para tentar simplificar a peça no assembly."),
    ("Expressões: unidades e conversão", "Boas práticas",
     "Expressões carregam unidade; misturar mm e polegada sem conversão explícita gera erro silencioso de escala. Padronize a unidade da peça no início e evite constantes 'mágicas' que embutem conversão."),
    ("Reutilização com User Defined Features (UDF)", "Boas práticas",
     "UDFs empacotam um conjunto de features parametrizadas (ex.: um rasgo de chaveta padrão) para reutilizar em várias peças. Centraliza a intenção de projeto e reduz retrabalho, mas exige manutenção quando o padrão muda."),
    ("Part Families (famílias de peças)", "Boas práticas",
     "Part Families geram variações dimensionais de uma peça-mestre a partir de uma planilha (ex.: parafusos M6/M8/M10). Cada membro é derivado, não copiado — mudança no mestre propaga. Ótimo para itens de catálogo."),
    ("Naming: prefixo por tipo de feature", "Boas práticas",
     "Adotar prefixos consistentes (DATUM_, SK_ para sketch, EXT_ para extrude, HOLE_) na árvore facilita busca e revisão por terceiros. Combine com feature groups para agrupar por função."),

    ("CAM: escolha de estratégia de desbaste", "Manufatura",
     "No Manufacturing, o desbaste (roughing) remove o grosso do material; estratégias como Cavity Mill seguem níveis Z. Deixe sobremetal (stock) para a operação de acabamento. Passo lateral e profundidade dependem da ferramenta e do material."),
    ("CAM: simulação de percurso e colisão", "Manufatura",
     "Antes de postar o G-code, rode a verificação de percurso (Verify/ISV) para checar colisão de haste/suporte e gouge na peça. Um percurso que 'parece certo' na tela pode colidir com o fixador — simule com o setup completo."),
    ("Tolerância de usinabilidade vs. projeto", "Manufatura",
     "Nem toda tolerância apertada é fabricável de forma econômica. Antes de fechar o desenho, valide com a manufatura se o processo (fresa, torno, EDM) atinge a tolerância; senão o custo dispara ou a peça é rejeitada em inspeção."),
]


def main() -> None:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge_entries WHERE criado_por = %s", (MARCADOR,))
            apagadas = cur.rowcount
            ids = []
            for titulo, categoria, conteudo in ENTRADAS:
                cur.execute(
                    "INSERT INTO knowledge_entries (titulo, conteudo, categoria, criado_por, status) "
                    "VALUES (%s, %s, %s, %s, 'aprovado') RETURNING id",
                    (titulo, conteudo, categoria, MARCADOR),
                )
                ids.append(cur.fetchone()[0])
        conn.commit()
    print(f"[seed] {apagadas} entradas fictícias antigas removidas; {len(ids)} inseridas.")

    print("[seed] gerando embeddings em lote...")
    processadas, falhas = reindexar_aprovadas()
    print(f"[seed] concluído: {processadas} embeddadas, {falhas} falhas.")


if __name__ == "__main__":
    main()
