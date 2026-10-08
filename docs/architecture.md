# Architecture

Documento de referência da arquitetura do **Document Correction Agent**. Serve para se orientar: o que o sistema é, como as partes se encaixam e o que está fora do escopo. Atualize sempre que uma decisão mudar.

## 1. Objetivo

Um sistema com interface de chat que:

1. **Consulta** uma base de atos normativos (portarias, decretos, instruções normativas) e responde com citação de fonte.
2. **Analisa** um `.docx` anexado e devolve o arquivo com comentários apontando possíveis problemas, cada um com o lastro (regra ou trecho da fonte) que o sustenta.

O sistema é **apoio à revisão**, não parecer jurídico. A decisão final é sempre humana.

## 2. Escopo da v1

**Dentro**
- Um tipo de ato e um órgão (a definir no M0, candidato: portaria da SEJUS).
- Consulta ao acervo com citação (documento, artigo, página).
- Análise de `.docx` com checklist de regras e comentários nativos do Word.

**Fora (por enquanto)**
- Geração de minutas.
- Reescrita automática com track changes.
- Análise de mérito jurídico (conflito entre normas, competência).
- Outros tipos de ato.
- Verificação automática de vigência (na v1 só se exibe a data da fonte).

## 3. Princípios

1. **Medir antes de ajustar.** Nenhuma mudança de prompt, chunking ou modelo sem rodar o conjunto de avaliação.
2. **O código decide o fluxo e as posições; o LLM classifica e justifica.** O modelo nunca localiza texto no arquivo nem decide se vai ser rigoroso.
3. **Todo achado tem lastro** (regra do checklist ou trecho da fonte). Sem lastro, vira "requer decisão humana".
4. **Nada falha em silêncio.** O que não foi indexado ou ancorado aparece em um relatório.
5. **Cada etapa grava sua saída.** Dá para reprocessar só o que mudou, sem refazer OCR.
6. **O original nunca é sobrescrito.** A saída é sempre uma cópia.

## 4. Visão geral

```
                      ┌────────────────────────────────────┐
  PDFs ──► Ingestão ──►  chunks JSON + embeddings (banco)   │
                      └──────────────┬─────────────────────┘
                                     │
              ┌──────────────────────┴──────────────────────┐
              ▼                                             ▼
          CONSULTA                                      ANÁLISE
   pergunta → busca → resposta                 .docx → parágrafos numerados
   com citação                                 → regras (código) + LLM por seção
                                               → achados JSON → .docx com comentários
                                               + relatório do que não ancorou
```

Três partes independentes: **Ingestão**, **Consulta** e **Análise**. A interface (chat) fica por cima e chama cada uma por ação explícita.

## 5. Módulos

### 5.1 Ingestão
Transforma PDFs em chunks citáveis. Duas etapas separadas, cada uma com sua pasta:

- **Etapa A, extração:** PDF → texto por página, sem interpretar nada. Registra se há camada de texto e a qualidade. É a etapa cara (OCR); roda uma vez.
- **Etapa B, estruturação:** texto bruto → limpeza de ruído → divisão em chunks → metadados. Será ajustada várias vezes, por isso é separada.

Chunking **por artigo** (com parágrafos, incisos e alíneas). Cabeçalho (epígrafe, ementa, preâmbulo) e fecho (vigência, revogação, assinatura) podem ser chunks próprios. Documentos sem "Art." usam fallback por seção/parágrafo e recebem `estrutura: livre`.

### 5.2 Consulta
`buscar(pergunta, filtros)` → chunks mais próximos, com metadados. O LLM responde **somente** com base nos chunks recuperados, cita a fonte e diz "não encontrei" quando a base não sustenta. A resposta mostra a data da fonte ("texto de [data], pode ter sido alterado").

### 5.3 Regras
Checklist por tipo de ato, em arquivo estruturado. Cada regra tem: `id`, `descricao`, `metodo` (`codigo` ou `llm`), `fonte_legal`, `severidade`. Regras objetivas (numeração, cláusula de vigência, "revogam-se as disposições em contrário") rodam em código: barato e repetível. O LLM fica com o texto livre. O checklist é validado por um advogado.

### 5.4 Análise
1. Lê o `.docx` e numera os parágrafos (P1..Pn).
2. Identifica o tipo de ato e carrega o checklist correspondente.
3. Roda as regras de código.
4. Roda o LLM por seção, com um veredito por regra.
5. Valida o lastro e consolida/deduplica os achados.

### 5.5 Entrega
Transforma os achados em **comentários nativos** do Word, ancorados pelo número do parágrafo. Achado que não ancorar vai para um relatório. Se nada puder ser aplicado, devolve cópia intacta com aviso.

### 5.6 Interface
Chat com anexo e **botões de ação explícitos** (Consultar, Analisar, Baixar `.docx`). Sem roteamento por interpretação do texto do usuário. Aviso fixo: "apoio à revisão, não substitui parecer jurídico".

## 6. Formatos de dados

### Chunk (versão mínima)
```json
{
  "chunk_id": "portaria_123_2024#art5",
  "arquivo": "portaria_123_2024.pdf",
  "tipo_ato": "portaria",
  "numero": "123",
  "data": "2024-03-05",
  "orgao": "SEJUS",
  "tipo_trecho": "artigo",
  "artigo": "5",
  "pagina_inicio": 2,
  "pagina_fim": 2,
  "estrutura": "articulada",
  "texto": "Art. 5º O Grupo de Trabalho será composto por: ..."
}
```
Só `texto` vai para o embedding; o resto é metadado para filtro e citação. Campos extras (`capitulo`, `referencias_normas`, `remissoes_internas`, `signatario`) entram quando fizerem falta.

### Achado (saída da análise)
```json
{
  "id": "A-0007",
  "paragrafo": "P14",
  "regra": "R-REV-01",
  "veredito": "divergente",
  "trecho": "Revogam-se as disposições em contrário.",
  "problema": "Revogação genérica; a LC 95/1998 exige enumeração expressa.",
  "sugestao": "Indicar expressamente as normas revogadas.",
  "lastro": "LC 95/1998, art. 9º",
  "requer_decisao_humana": false,
  "status": "ancorado"
}
```
`veredito`: `conforme` | `divergente` | `nao_aplicavel` | `sem_referencia`.
`status`: `ancorado` | `no_relatorio` | `descartado`.

### Gabarito (avaliação)
Lista de `{documento, paragrafo, regra, correcao_esperada}` validada por advogado. Mede recall e precisão a cada mudança.

## 7. Estrutura de pastas sugerida

```
projeto/
  docs/
    architecture.md
    implements.md
  dados/
    pdf/          # PDFs de origem (não versionar se forem sensíveis)
    bruto/        # saída da etapa A (texto por página)
    chunks/       # saída da etapa B (chunks por documento)
  regras/         # checklists por tipo de ato
  avaliacao/      # gabarito e resultados por execução
  src/
    ingestao/     # extracao.py, estruturacao.py, indexacao.py
    consulta/     # busca.py, resposta.py
    analise/      # leitor_docx.py, regras.py, llm.py, achados.py
    entrega/      # comentarios_docx.py, relatorio.py
    web/          # interface
  tests/
```

## 8. Decisões em aberto

| # | Decisão | Impacto |
|---|---|---|
| 1 | Tipo de ato e órgão do primeiro recorte | Define regras e fontes |
| 2 | Quem é o advogado/revisor e quanto tempo tem | Bloqueia o checklist e o gabarito |
| 3 | Modelo de LLM (custo, qualidade) | A profundidade da análise limita o resultado |
| 4 | Os documentos podem sair da rede (API externa) ou exigem modelo local? | Define o provedor de LLM e embeddings |
| 5 | Banco vetorial (Qdrant, Chroma, pgvector) | Baixo impacto no MVP; qualquer um serve |
| 6 | Quem usa e como (equipe interna?) | Autenticação e tom da interface |

Registre cada decisão tomada em uma linha com data e motivo.

## 9. Riscos

- **Gabarito sem validação de quem entende**: maior risco; sem ele não há como saber se o sistema acerta.
- **Muitos PDFs escaneados**: aumentam custo e erro (um "Art. 12" lido como "Art. 72" estraga a citação).
- **Base desatualizada**: norma revogada gera achado errado; sempre exibir a data da fonte.
- **Correção errada com aparência de certa**: mitigado por lastro obrigatório e por tratar tudo como sugestão.
- **Escopo crescendo**: o projeto anterior acumulou funções demais; manter o escopo da seção 2.

## 10. Lições do projeto anterior

**Manter:** lastro obrigatório; cobertura conferida pelo código, não pela declaração do modelo; entrega nunca vazia; análise versionada por hash do documento; original nunca sobrescrito; comentários nativos do Word.

**Evitar:** conversão PDF → markdown no meio da ingestão; chunking por tamanho fixo; âncora por texto (usar número de parágrafo); cadeia análise em prosa → extração → patch (a análise já nasce em JSON); roteamento por intenção do texto; modelo pequeno com documento inteiro de uma vez; testes que só cobrem mecânica e não qualidade; geração de minutas com dados plausíveis inventados.
