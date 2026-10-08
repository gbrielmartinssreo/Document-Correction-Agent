# Implements

Guia prático de implementação, na ordem. Cada milestone tem um objetivo, passos pequenos e um critério de "pronto". Não pule etapas e não comece o próximo sem fechar o anterior. Detalhes da arquitetura estão em `architecture.md`.

## Regras de trabalho

- Cada issue cabe em uma sessão de **2 a 4 horas**. Se não cabe, quebre.
- Olhe o dado real **a olho nu** a cada etapa antes de seguir.
- Sem LangChain no começo. Chamadas diretas à API são mais fáceis de depurar.
- Cada etapa grava sua saída em disco; reprocessar nunca deve exigir refazer a etapa anterior.
- Nenhuma mudança de prompt, chunking ou modelo sem rodar a avaliação (a partir do M3).

---

## M-1: Decisões (meio dia)

**Objetivo:** fechar o que evita retrabalho.

- [ ] Escolher o tipo de ato e o órgão do primeiro recorte
- [ ] Definir se os documentos podem ir para API externa ou exigem modelo local
- [ ] Escolher o modelo de LLM e o de embeddings (pode ser provisório)
- [ ] Identificar o advogado/revisor e combinar horas por semana
- [ ] Registrar tudo em `architecture.md`, seção 8

**Pronto quando:** as decisões 1 a 4 da seção 8 estão preenchidas.

---

## M0: Dados legíveis

**Objetivo:** saber o que realmente existe nos PDFs.

### Passos
1. **Inventário.** Listar os PDFs: nome, nº de páginas, tipo de ato (pode ser pelo nome do arquivo no começo).
2. **Script de extração (etapa A).** Para cada PDF, extrair o texto por página e salvar `dados/bruto/<doc>.json`:
   ```json
   {
     "arquivo": "portaria_123_2024.pdf",
     "tem_camada_texto": true,
     "paginas": [{"pagina": 1, "texto": "...", "n_caracteres": 1830}]
   }
   ```
3. **Triagem.** Gerar uma planilha/CSV com uma linha por PDF: tem texto? caracteres por página? contém "Art. 1º"? nota (`ok` / `duvidoso` / `precisa_ocr`).
4. **Conferência manual.** Abrir 10 JSONs variados e verificar: texto limpo? ordem certa? cabeçalho/rodapé misturado? tabelas quebradas?

### Ferramentas
- Python + `uv`
- `PyMuPDF` (`fitz`) para extração de texto
- OCR só depois, no lote que precisar (por exemplo `ocrmypdf` ou Tesseract)

### Pronto quando
Você sabe quantos PDFs são utilizáveis sem OCR, quantos precisam de OCR e quantos têm estrutura articulada.

---

## M1: Chunks por artigo

**Objetivo:** transformar texto bruto em pedaços citáveis.

### Passos
1. **Limpeza.** Remover cabeçalho, rodapé e numeração de página que se repetem (detectar linhas repetidas entre páginas).
2. **Metadados do documento.** Extrair tipo, número, data e órgão da epígrafe (primeira página). Pode ser regex; usar o LLM só se a regex falhar. Validar em 20 documentos.
3. **Divisão em chunks (etapa B).** Regex em `Art. Nº` (variações: `Art. 1º`, `Art. 10.`, `Artigo 5`). Cada artigo leva seus parágrafos e incisos.
4. **Cabeçalho e fecho.** Um chunk `cabecalho` (epígrafe + ementa + preâmbulo) e um `fecho` (vigência, revogação, assinatura). Refinar em mais tipos só se as regras pedirem.
5. **Fallback.** Documentos sem "Art." recebem `estrutura: livre` e são divididos por seção/parágrafo.
6. **Relatório de exceções.** Lista dos documentos que não deram para dividir e o motivo. Nada some em silêncio.
7. Salvar em `dados/chunks/<doc>.json` (lista de chunks, formato na seção 6 de `architecture.md`).

### Pronto quando
Em 10 documentos conferidos a olho, os artigos saíram inteiros, na ordem, sem pedaços de rodapé no meio.

---

## M2: Consulta com fonte

**Objetivo:** primeiro chatbot útil, ainda sem agente e sem correção.

### Passos
1. **Embeddings e banco.** Gerar embeddings do campo `texto` de cada chunk e gravar no banco vetorial (Qdrant ou Chroma) com todos os metadados.
2. **Função `buscar(pergunta, filtros=None)`.** Retorna os top-k chunks com metadados. Filtros por `tipo_ato`, ano, órgão.
3. **Resposta com citação.** Prompt: "responda apenas com base nos trechos abaixo; cite documento, artigo e página; se não houver base, diga que não encontrou".
4. **Aviso de data.** Incluir a data da fonte na resposta.
5. **Perguntas de teste.** Montar 15 a 20 perguntas com resposta conhecida (e 3 a 5 sem resposta na base) em `avaliacao/consulta.json`.
6. **Script de avaliação da consulta.** Para cada pergunta: o chunk certo apareceu no top-k? A resposta citou a fonte certa? Disse "não encontrei" quando devia?

### Pronto quando
A maioria das perguntas de teste volta com o trecho e a fonte corretos, e as perguntas sem resposta não geram resposta inventada.

---

## M3: Regras e avaliação

**Objetivo:** preparar o terreno da correção, a parte arriscada.

### Passos
1. **Schema do checklist.** Arquivo por tipo de ato em `regras/portaria.yaml`:
   ```yaml
   - id: R-REV-01
     descricao: A cláusula de revogação deve enumerar expressamente as normas revogadas.
     metodo: codigo
     fonte_legal: "LC 95/1998, art. 9º"
     severidade: alta
   ```
2. **Rascunho das regras** a partir da LC 95/1998, do Decreto 9.191/2017 e do Manual de Redação da Presidência (ou equivalentes estaduais/municipais). Cada regra com sua fonte.
3. **Validação com o advogado.** Levar a lista; ele marca o que está certo, errado e o que falta. Registrar as correções.
4. **Gabarito.** 10 a 15 documentos com erros conhecidos, em `avaliacao/gabarito.json`, anotados com o advogado (documento, parágrafo, regra violada, correção esperada).
5. **Regras em código.** Implementar primeiro as objetivas: epígrafe presente, numeração de artigos (ordinal até 9, cardinal depois), cláusula de vigência, "revogam-se as disposições em contrário", remissões a artigos inexistentes.
6. **Script de avaliação.** Calcula recall, precisão e lista de falsos positivos contra o gabarito. Salvar o resultado de cada execução em `avaliacao/resultados/`.

### Pronto quando
As regras de código pegam erros reais do gabarito, sem falsos positivos grosseiros, e você tem um número de base para comparar o que vem depois.

---

## Depois do M3 (detalhar só quando chegar)

Não abra issues destes itens agora: o que você aprender nos milestones anteriores vai mudar o desenho.

- **Análise com LLM:** leitor de `.docx` com parágrafos numerados, classificador do tipo de ato, schema de achados, análise por seção com o checklist, validação de lastro, deduplicação. Comparar 2 ou 3 modelos no mesmo gabarito.
- **Entrega:** comentários nativos no `.docx` ancorados por parágrafo, relatório de achados não ancorados, cobertura conferida pelo código, cópia intacta quando nada se aplica.
- **Interface:** chat com anexo e botões de ação explícitos.
- **Transversais:** logs estruturados por etapa, avaliação rodando no CI, um registro curto por decisão relevante.

---

## Ordem e dependências

```
M-1 ─► M0 ─► M1 ─► M2
              └──► M3 (regras e gabarito)  ──► Análise ──► Entrega ──► Interface
```

- M2 e M3 podem andar em paralelo depois do M1.
- **Abra já a conversa com o advogado** (issue do M-1): o M3 depende dele e leva tempo para agendar.

## Convenções

- **Labels sugeridas:** `ingestão`, `consulta`, `regras`, `análise`, `entrega`, `interface`, `avaliação`, `decisão`, `bloqueado-por-advogado`.
- **Milestones:** um por seção deste documento.
- **Cada issue** tem descrição curta e um critério de aceite verificável (ex.: "10 documentos conferidos, artigos íntegros").
