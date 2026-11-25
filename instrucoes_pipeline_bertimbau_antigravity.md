# Instruções para implementação do pipeline de ABSA com BERTimbau

## 1. Objetivo do projeto

Implemente um pipeline de **Aspect-Based Sentiment Analysis (ABSA)** em português brasileiro usando o modelo pré-treinado `neuralmind/bert-base-portuguese-cased` (BERTimbau Base).

O pipeline deve receber o texto de uma avaliação de pedido e retornar:

1. os aspectos mencionados na avaliação;
2. o sentimento associado a cada aspecto identificado;
3. a entidade de negócio associada a cada aspecto;
4. as probabilidades e os níveis de confiança das previsões;
5. a versão dos modelos utilizados.

O projeto não deve usar LLMs para rotulação, treinamento ou inferência. Os dados de treinamento já serão fornecidos de forma estruturada.

O sistema será futuramente integrado a um mecanismo de recomendação de pedidos e lojas. Portanto, as saídas devem ser determinísticas, estruturadas, versionadas e apropriadas para armazenamento em banco de dados.

---

## 2. Escopo funcional

O MVP deve conter dois modelos baseados em BERTimbau:

1. **Detector multirrótulo de aspectos**
   - recebe o texto completo da avaliação;
   - retorna zero ou mais aspectos;
   - usa uma camada de saída com `sigmoid`;
   - cada aspecto possui uma probabilidade independente.

2. **Classificador de sentimento condicionado ao aspecto**
   - recebe o texto da avaliação e um aspecto detectado;
   - retorna `positivo`, `negativo` ou `neutro`;
   - usa uma camada de saída com `softmax`.

A entidade não precisa de um terceiro modelo no MVP. Ela deve ser determinada por um mapeamento fixo entre aspecto e entidade.

### Fora do escopo do MVP

Não implementar nesta primeira versão:

- LLM para pré-rotulação;
- extração livre de novos aspectos;
- geração textual de explicações;
- recomendação de produtos ou lojas;
- LightGBM ou filtragem colaborativa;
- aplicação mobile;
- classificação de intensidade;
- classe de sentimento `misto` no nível do aspecto;
- análise específica de ironia;
- extração de spans por token;
- treinamento conjunto multitarefa;
- interface gráfica completa.

---

## 3. Taxonomia oficial do MVP

Use exclusivamente os aspectos abaixo. Não permita que o modelo ou a API retornem aspectos fora desta taxonomia.

### 3.1 Aspectos de produto

| Código | Descrição | Exemplos |
|---|---|---|
| `sabor` | Sabor, tempero e palatabilidade | delicioso, sem gosto, salgado, enjoativo |
| `qualidade` | Qualidade geral ou dos ingredientes quando não houver aspecto mais específico | ingredientes frescos, produto estragado, carne de baixa qualidade |
| `quantidade` | Tamanho, volume, recheio ou tamanho da porção | porção pequena, veio bastante, pouco recheio |
| `temperatura` | Temperatura do alimento ou bebida | chegou frio, estava quente, sorvete derretido |
| `aparencia` | Apresentação, montagem e aparência visual | bem montado, veio destruído, aparência ruim |
| `preparo` | Execução e ponto de preparo | carne crua, massa queimada, ponto correto |

### 3.2 Aspectos de loja

| Código | Descrição | Exemplos |
|---|---|---|
| `atendimento` | Comunicação, suporte e tratamento oferecido pela loja | respondeu rápido, foi grosseiro, não respondeu |
| `pedido_correto` | Correção e completude dos itens recebidos | faltou bebida, veio item errado, pedido completo |
| `embalagem` | Proteção, lacre e acondicionamento | embalagem vazando, bem embalado, lacre violado |
| `custo_beneficio` | Relação entre preço e experiência recebida | caro pelo que oferece, vale o preço |

### 3.3 Aspectos de entrega

| Código | Descrição | Exemplos |
|---|---|---|
| `tempo_entrega` | Rapidez, demora ou atraso | chegou rápido, atrasou uma hora |
| `condicao_entrega` | Estado físico do pedido ao chegar | chegou amassado, bebida derramada |

### 3.4 Mapeamento fixo de entidades

```json
{
  "sabor": "produto",
  "qualidade": "produto",
  "quantidade": "produto",
  "temperatura": "produto",
  "aparencia": "produto",
  "preparo": "produto",
  "atendimento": "loja",
  "pedido_correto": "loja",
  "embalagem": "loja",
  "custo_beneficio": "loja",
  "tempo_entrega": "entrega",
  "condicao_entrega": "entrega"
}
```

### 3.5 Classes de sentimento

Use somente:

- `positivo`;
- `negativo`;
- `neutro`.

Não use `neutro` para representar aspecto ausente. Um aspecto ausente deve receber valor `0` no vetor multirrótulo do detector e não deve ser enviado ao classificador de sentimento durante a inferência normal.

---

## 4. Regras de anotação que os dados devem respeitar

As mesmas regras devem ser documentadas e usadas na validação do dataset.

### Regra 1: não inferir aspectos inexistentes

Texto: `Nota 1, não gostei.`

Resultado: nenhum aspecto específico. Não inferir sabor, preço ou entrega.

### Regra 2: preferir o aspecto mais específico

- `Veio frio.` → `temperatura`, não `qualidade`;
- `A carne veio queimada.` → `preparo`;
- `Veio quase sem carne.` → `quantidade`;
- `A carne estava sem gosto.` → `sabor`.

### Regra 3: permitir múltiplos aspectos

Texto: `Gostoso, barato e chegou rápido.`

Rótulos:

- `sabor`: `positivo`;
- `custo_beneficio`: `positivo`;
- `tempo_entrega`: `positivo`.

### Regra 4: não substituir o texto pela nota

Texto: `A comida estava ótima, mas a embalagem vazou.`

Mesmo que a nota geral seja 5, `embalagem` deve ser `negativo`.

### Regra 5: preservar negações

- `Não estava frio.` não deve ser automaticamente negativo;
- `Não demorou nada.` normalmente indica `tempo_entrega` positivo.

### Regra 6: não confundir temperatura com responsabilidade da entrega

Texto: `A comida chegou fria.`

Rótulo: entidade `produto`, aspecto `temperatura`, sentimento `negativo`.

A frase não demonstra que a culpa foi do entregador.

### Regra 7: sentimento conflitante no mesmo aspecto

O dataset normalizado poderá conter mais de uma ocorrência do mesmo aspecto para uma avaliação quando trechos diferentes tiverem polaridades conflitantes. Entretanto, antes do treinamento, essas ocorrências devem ser tratadas por uma política explícita.

Para o MVP, aplique esta política:

1. se houver duas polaridades para o mesmo aspecto na mesma avaliação, marque o registro como `requires_review = true`;
2. exclua esse registro do treinamento automático até revisão humana;
3. não crie a classe `misto`.

---

## 5. Formato dos dados

### 5.1 Formato canônico de entrada

Aceite arquivos `.jsonl` e `.csv`. Internamente, normalize tudo para uma linha por ocorrência de aspecto.

Campos obrigatórios:

| Campo | Tipo | Regra |
|---|---|---|
| `review_id` | string | Identificador único da avaliação |
| `text` | string | Texto original, não vazio |
| `aspect` | string | Um valor da taxonomia oficial |
| `sentiment` | string | `positivo`, `negativo` ou `neutro` |

Campos opcionais:

| Campo | Tipo | Uso |
|---|---|---|
| `rating` | número | Nota original, somente para auditoria e análises auxiliares |
| `user_id` | string | Usado para divisão sem vazamento por usuário |
| `store_id` | string | Auditoria de diversidade entre lojas |
| `order_id` | string | Controle de duplicidade e agrupamento |
| `created_at` | datetime ISO 8601 | Divisão temporal e monitoramento |
| `evidence_text` | string | Trecho que justifica a anotação |
| `start_offset` | inteiro | Início opcional do trecho no texto |
| `end_offset` | inteiro | Final opcional do trecho no texto |
| `requires_review` | booleano | Indica conflito ou problema de anotação |

Exemplo JSONL:

```json
{"review_id":"101","text":"O hambúrguer estava bom, mas chegou frio.","aspect":"sabor","sentiment":"positivo","rating":3,"user_id":"u42"}
{"review_id":"101","text":"O hambúrguer estava bom, mas chegou frio.","aspect":"temperatura","sentiment":"negativo","rating":3,"user_id":"u42"}
{"review_id":"102","text":"Demorou muito e faltou a bebida.","aspect":"tempo_entrega","sentiment":"negativo","rating":1,"user_id":"u73"}
{"review_id":"102","text":"Demorou muito e faltou a bebida.","aspect":"pedido_correto","sentiment":"negativo","rating":1,"user_id":"u73"}
```

### 5.2 Avaliações sem aspecto

Para treinar corretamente o detector multirrótulo, o dataset deve também conter avaliações sem aspectos específicos.

Use um registro por avaliação em um arquivo agregado com o campo `aspects` vazio:

```json
{"review_id":"103","text":"Não gostei.","aspects":[],"sentiments":{}}
```

Crie o arquivo agregado automaticamente com base no formato normalizado.

---

## 6. Validação e preparação do dataset

Crie um comando de validação que gere um relatório em JSON e Markdown.

O validador deve verificar:

- campos obrigatórios ausentes;
- textos vazios;
- aspectos fora da taxonomia;
- sentimentos inválidos;
- `review_id` associado a textos divergentes;
- duplicatas exatas;
- conflitos de sentimento para o mesmo `review_id` e aspecto;
- offsets inválidos;
- `evidence_text` incompatível com os offsets, quando disponíveis;
- avaliações marcadas com `requires_review`;
- quantidade de exemplos por aspecto;
- distribuição de sentimentos por aspecto;
- usuários, lojas e pedidos distintos;
- possíveis duplicatas de texto entre partições;
- classes com menos de 200 exemplos;
- classes com menos de 500 exemplos, classificadas como risco para produção;
- desequilíbrio superior a 80% em uma única polaridade dentro de um aspecto.

O relatório deve incluir, no mínimo:

- total de avaliações;
- total de ocorrências de aspectos;
- avaliações sem aspecto;
- distribuição por aspecto;
- distribuição de sentimento por aspecto;
- quantidade de conflitos;
- quantidade de duplicatas;
- recomendações de correção;
- status final `approved`, `approved_with_warnings` ou `rejected`.

Não iniciar treinamento quando o status for `rejected`.

---

## 7. Divisão do dataset

A divisão padrão deve ser:

- 70% treinamento;
- 15% validação;
- 15% teste.

Prioridade de agrupamento:

1. dividir por `user_id`, se disponível;
2. caso contrário, dividir por `order_id`;
3. caso contrário, dividir por `review_id`.

Nunca permita que ocorrências do mesmo `review_id` apareçam em partições diferentes.

Se `created_at` estiver disponível, ofereça uma opção de divisão temporal:

- dados mais antigos para treino;
- período seguinte para validação;
- período mais recente para teste.

Use seed configurável, com valor padrão `42`.

Salve um manifesto contendo:

- estratégia de divisão;
- seed;
- quantidade de registros em cada partição;
- distribuição de cada classe;
- hash dos arquivos gerados.

---

## 8. Pré-processamento de texto

Não remova acentos, pontuação ou palavras de negação.

Não aplique stemming ou lematização.

O pré-processamento deve ser mínimo:

- converter valores não textuais para string somente após validação;
- normalizar espaços repetidos;
- remover espaços no início e no fim;
- normalizar quebras de linha;
- preservar emojis;
- preservar caixa, pois o modelo é `cased`;
- preservar erros ortográficos do texto original;
- preservar marcas de negação.

Use o tokenizer correspondente a `neuralmind/bert-base-portuguese-cased`.

Comprimento máximo inicial: `128` tokens.

O pipeline deve calcular a proporção de textos truncados. Se mais de 5% forem truncados, permitir configuração para `256` tokens e registrar o impacto esperado em memória e latência.

---

## 9. Modelo 1: detector multirrótulo de aspectos

### Entrada

Texto completo da avaliação.

### Saída

Vetor de 12 probabilidades, na ordem definida em um arquivo de configuração versionado.

### Arquitetura

- backbone: `neuralmind/bert-base-portuguese-cased`;
- cabeça: classificação de sequência com 12 saídas;
- ativação na inferência: `sigmoid`;
- loss inicial: `BCEWithLogitsLoss`;
- considerar `pos_weight` calculado apenas no conjunto de treino para classes desbalanceadas.

### Thresholds

Não fixe obrigatoriamente `0.5` para todas as classes.

Durante a validação:

1. encontre um threshold por aspecto;
2. otimize F1 para cada aspecto;
3. limite a busca entre `0.10` e `0.90`;
4. salve os thresholds junto ao artefato do modelo;
5. compare com um threshold global para auditoria.

### Caso sem aspecto

Se nenhuma probabilidade ultrapassar o threshold correspondente, retorne `aspects: []`.

---

## 10. Modelo 2: sentimento condicionado ao aspecto

### Entrada lógica

Concatene avaliação e aspecto usando o tokenizer do BERT:

```text
[CLS] texto da avaliação [SEP] nome do aspecto [SEP]
```

Use o recurso de pares de sentenças do tokenizer, em vez de montar tokens especiais manualmente.

Exemplo conceitual:

```python
 tokenizer(
     text="O hambúrguer estava bom, mas chegou frio.",
     text_pair="temperatura",
     truncation=True,
     max_length=128
 )
```

### Saída

Uma de três classes:

- `positivo`;
- `negativo`;
- `neutro`.

### Arquitetura

- backbone: `neuralmind/bert-base-portuguese-cased`;
- cabeça: classificação de sequência com 3 saídas;
- ativação na inferência: `softmax`;
- loss inicial: `CrossEntropyLoss`;
- permitir pesos por classe calculados somente no conjunto de treino.

### Regra de execução

Na inferência normal, execute o classificador de sentimento apenas para aspectos detectados pelo Modelo 1.

Ofereça também um endpoint de diagnóstico que receba texto e aspecto explicitamente, permitindo testar o Modelo 2 isoladamente.

---

## 11. Treinamento

Use Python, PyTorch, Hugging Face Transformers, Datasets, Evaluate e scikit-learn.

Parâmetros iniciais configuráveis:

```yaml
base_model: neuralmind/bert-base-portuguese-cased
max_length: 128
batch_size: 16
learning_rate: 2.0e-5
weight_decay: 0.01
epochs: 5
warmup_ratio: 0.1
gradient_accumulation_steps: 1
seed: 42
early_stopping_patience: 2
mixed_precision: true
```

Requisitos:

- detectar automaticamente se CUDA está disponível;
- permitir treinamento em CPU, deixando claro que será mais lento;
- usar mixed precision somente quando suportada;
- salvar o melhor modelo conforme métrica principal de validação;
- aplicar early stopping;
- registrar parâmetros, métricas e hashes dos dados;
- salvar checkpoints de forma configurável;
- permitir retomada a partir de checkpoint;
- não usar dados de teste para escolher hiperparâmetros ou thresholds.

### Métricas principais

Detector de aspectos:

- métrica principal: `macro F1`;
- `micro F1`;
- precision e recall macro;
- F1 por aspecto;
- exact match ratio;
- Hamming loss;
- precision@k e recall@k opcionais;
- curva precision-recall por aspecto;
- matriz de coocorrência de aspectos.

Sentimento por aspecto:

- métrica principal: `macro F1`;
- accuracy;
- precision, recall e F1 por classe;
- matriz de confusão geral;
- macro F1 para cada aspecto;
- matriz de confusão por aspecto quando houver volume suficiente.

---

## 12. Avaliação integrada do pipeline

Além de avaliar os modelos separadamente, avalie o fluxo completo:

1. detectar os aspectos;
2. classificar o sentimento dos aspectos detectados;
3. comparar os pares `(aspecto, sentimento)` previstos com os pares verdadeiros.

Calcule:

- precision, recall e F1 de pares exatos;
- taxa de avaliações totalmente corretas;
- falsos positivos por aspecto;
- falsos negativos por aspecto;
- erro de sentimento quando o aspecto foi corretamente detectado;
- latência média por avaliação;
- latência p50, p95 e p99;
- quantidade média de aspectos detectados por avaliação.

O relatório final deve diferenciar claramente:

- erro de detecção de aspecto;
- erro de sentimento;
- erro propagado pelo pipeline.

---

## 13. API de inferência

Implemente uma API REST com FastAPI.

### Endpoint de saúde

`GET /health`

Resposta:

```json
{
  "status": "ok",
  "aspectModelLoaded": true,
  "sentimentModelLoaded": true
}
```

### Endpoint de análise

`POST /api/v1/reviews/analyze`

Entrada:

```json
{
  "reviewId": "101",
  "text": "O hambúrguer estava muito bom, mas chegou frio e com bastante atraso."
}
```

Saída:

```json
{
  "reviewId": "101",
  "text": "O hambúrguer estava muito bom, mas chegou frio e com bastante atraso.",
  "aspects": [
    {
      "entity": "produto",
      "aspect": "sabor",
      "aspectProbability": 0.96,
      "sentiment": "positivo",
      "sentimentProbability": 0.94
    },
    {
      "entity": "produto",
      "aspect": "temperatura",
      "aspectProbability": 0.92,
      "sentiment": "negativo",
      "sentimentProbability": 0.97
    },
    {
      "entity": "entrega",
      "aspect": "tempo_entrega",
      "aspectProbability": 0.93,
      "sentiment": "negativo",
      "sentimentProbability": 0.95
    }
  ],
  "modelVersions": {
    "aspectDetector": "bertimbau-aspects-v1",
    "sentimentClassifier": "bertimbau-aspect-sentiment-v1",
    "taxonomy": "food-reviews-taxonomy-v1"
  },
  "processingTimeMs": 74
}
```

### Endpoint de diagnóstico do sentimento

`POST /api/v1/reviews/classify-sentiment`

Entrada:

```json
{
  "text": "O hambúrguer estava bom, mas chegou frio.",
  "aspect": "temperatura"
}
```

O endpoint deve rejeitar aspectos fora da taxonomia com HTTP 422.

### Requisitos de API

- schemas Pydantic;
- documentação OpenAPI automática;
- limite configurável para tamanho do texto;
- validação de texto vazio;
- logs estruturados sem registrar texto completo por padrão;
- ID de correlação por requisição;
- tratamento consistente de erros;
- carregamento dos modelos uma única vez no startup;
- inferência dentro de `torch.no_grad()` ou `torch.inference_mode()`;
- suporte a lote em endpoint separado;
- tamanho máximo de lote configurável;
- retorno HTTP 503 quando os modelos não estiverem disponíveis.

---

## 14. Versionamento dos artefatos

Cada modelo exportado deve conter:

- pesos do modelo;
- tokenizer;
- `config.json`;
- mapa de classes;
- taxonomia;
- thresholds por aspecto;
- configuração de treinamento;
- métricas de validação e teste;
- hash do dataset ou manifesto utilizado;
- data e hora do treinamento;
- versão do código, preferencialmente commit Git;
- versão das bibliotecas principais.

Estrutura sugerida:

```text
artifacts/
  aspect-detector/
    bertimbau-aspects-v1/
      model/
      tokenizer/
      labels.json
      thresholds.json
      taxonomy.json
      training_config.yaml
      metrics.json
      dataset_manifest.json
      metadata.json
  sentiment-classifier/
    bertimbau-aspect-sentiment-v1/
      model/
      tokenizer/
      labels.json
      taxonomy.json
      training_config.yaml
      metrics.json
      dataset_manifest.json
      metadata.json
```

---

## 15. Estrutura sugerida do repositório

```text
bertimbau-absa/
  README.md
  pyproject.toml
  requirements.txt
  Dockerfile
  docker-compose.yml
  .env.example
  .gitignore
  configs/
    taxonomy.yaml
    train_aspects.yaml
    train_sentiment.yaml
    api.yaml
  data/
    raw/
    processed/
    splits/
  artifacts/
  reports/
  scripts/
    validate_dataset.py
    prepare_dataset.py
    split_dataset.py
    train_aspect_detector.py
    train_sentiment_classifier.py
    evaluate_pipeline.py
    export_models.py
  src/
    absa/
      __init__.py
      config.py
      taxonomy.py
      preprocessing.py
      datasets.py
      metrics.py
      inference.py
      logging_config.py
      models/
        aspect_detector.py
        sentiment_classifier.py
      api/
        main.py
        dependencies.py
        schemas.py
        routes.py
  tests/
    unit/
    integration/
    fixtures/
```

---

## 16. CLI esperada

Disponibilize comandos equivalentes a:

```bash
python scripts/validate_dataset.py --input data/raw/reviews.jsonl --output reports/validation
python scripts/prepare_dataset.py --input data/raw/reviews.jsonl --output data/processed
python scripts/split_dataset.py --input data/processed/reviews.jsonl --output data/splits --seed 42
python scripts/train_aspect_detector.py --config configs/train_aspects.yaml
python scripts/train_sentiment_classifier.py --config configs/train_sentiment.yaml
python scripts/evaluate_pipeline.py --input data/splits/test.jsonl --output reports/final
uvicorn src.absa.api.main:app --host 0.0.0.0 --port 8000
```

Todos os comandos devem:

- retornar código de saída diferente de zero em caso de falha;
- produzir logs claros;
- aceitar caminhos configuráveis;
- não depender de caminhos absolutos;
- ser executáveis em Linux;
- oferecer `--help`.

---

## 17. Testes obrigatórios

Use `pytest`.

### Testes unitários

- validação da taxonomia;
- mapeamento de aspectos para entidades;
- normalização mínima de texto;
- conversão do dataset normalizado para multirrótulo;
- identificação de conflitos;
- cálculo de thresholds;
- serialização da resposta da API;
- cálculo das métricas;
- rejeição de rótulos inválidos.

### Testes de integração

- treinamento mínimo com fixture pequena;
- exportação e recarga dos modelos;
- chamada ao endpoint de análise;
- chamada ao endpoint em lote;
- comportamento com nenhum aspecto detectado;
- comportamento com texto vazio;
- comportamento com aspecto inválido;
- inicialização sem GPU;
- reprodutibilidade básica com seed fixa.

### Casos linguísticos mínimos

Inclua testes para:

- `Gostei muito do sabor.`;
- `A comida chegou fria.`;
- `Não estava frio.`;
- `Não demorou nada.`;
- `Veio rápido, mas a embalagem estava aberta.`;
- `A carne estava crua e sem tempero.`;
- `Faltou a bebida.`;
- `Nota 1, não gostei.`;
- `Gostoso, barato e chegou rápido.`;
- avaliação vazia;
- avaliação apenas com emoji;
- avaliação com erros ortográficos.

---

## 18. Segurança, privacidade e observabilidade

- Não registrar o texto completo das avaliações em logs de produção por padrão.
- Permitir mascaramento ou remoção de e-mail, telefone e outros possíveis dados pessoais antes do armazenamento de logs.
- Registrar apenas `review_id`, versão do modelo, latência, quantidade de aspectos e status da requisição.
- Não incluir segredos no repositório.
- Usar variáveis de ambiente para configurações sensíveis.
- Adicionar limites de payload e lote.
- Documentar que textos e identificadores podem constituir dados pessoais e devem seguir as políticas de retenção e acesso do projeto.

Métricas operacionais mínimas:

- requisições por minuto;
- taxa de erro;
- latência p50, p95 e p99;
- quantidade média de aspectos por avaliação;
- distribuição dos aspectos previstos;
- distribuição dos sentimentos previstos;
- proporção de avaliações sem aspecto;
- versão ativa dos modelos.

Crie alertas conceituais para mudanças acentuadas na distribuição das previsões, pois isso pode indicar drift de dados.

---

## 19. Docker e execução

Crie um `Dockerfile` para inferência com:

- Python 3.11;
- instalação reproduzível das dependências;
- usuário não root;
- endpoint de health check;
- modelos montados ou copiados de caminho configurável;
- porta padrão 8000;
- sem ferramentas de treinamento desnecessárias na imagem final, se possível.

Crie `docker-compose.yml` para desenvolvimento local.

Não baixar o modelo da internet a cada inicialização em produção. A imagem ou o volume de implantação deve conter os artefatos já exportados.

---

## 20. README obrigatório

O README deve conter:

1. objetivo do projeto;
2. arquitetura dos dois modelos;
3. taxonomia completa;
4. requisitos de ambiente;
5. instalação local;
6. formato dos dados;
7. validação e preparação;
8. treinamento;
9. avaliação;
10. execução da API;
11. exemplos de requisição e resposta;
12. execução com Docker;
13. execução dos testes;
14. estrutura dos artefatos;
15. limitações conhecidas;
16. critérios para adicionar um novo aspecto.

---

## 21. Critérios para inclusão futura de novos aspectos

Não adicionar um aspecto apenas porque surgiu em poucos exemplos.

Um novo aspecto deve:

- representar informação útil ao recomendador ou à operação;
- ter definição que não se sobreponha significativamente às classes existentes;
- possuir instruções de anotação claras;
- possuir preferencialmente pelo menos 200 exemplos para experimento;
- possuir preferencialmente 500 exemplos para uma primeira versão utilizável;
- conter exemplos positivos, negativos e, quando aplicável, neutros;
- ser validado em um conjunto de teste separado;
- aumentar a utilidade sem reduzir excessivamente o desempenho das classes atuais.

Aspectos candidatos para versões futuras:

- `higiene`;
- `entregador`;
- `correspondencia_descricao`;
- `confiabilidade_loja`;
- `pagamento`;
- `usabilidade_app`;
- `informacao_app`;
- `promocao`;
- `disponibilidade`.

---

## 22. Critérios de aceite do MVP

O MVP será considerado concluído quando:

- o dataset puder ser validado e dividido sem vazamento por `review_id`;
- os dois modelos puderem ser treinados por comandos independentes;
- os artefatos puderem ser salvos, versionados e recarregados;
- os thresholds do detector forem calibrados no conjunto de validação;
- o pipeline integrado puder ser avaliado no conjunto de teste;
- a API FastAPI retornar a estrutura definida;
- avaliações sem aspecto retornarem lista vazia;
- a entidade for preenchida pelo mapeamento fixo;
- as métricas forem exportadas em JSON e Markdown;
- os testes automatizados passarem;
- a aplicação puder ser executada com Docker;
- o README permitir que outra pessoa configure e execute o projeto.

Não defina um valor arbitrário de F1 como garantia de sucesso antes de conhecer a qualidade e a distribuição do dataset. O relatório deve apresentar resultados por classe e destacar classes insuficientes ou instáveis.

---

## 23. Ordem de implementação para o Antigravity

Implemente na seguinte ordem:

1. criar a estrutura do repositório;
2. criar a taxonomia centralizada e versionada;
3. implementar schemas e validação do dataset;
4. implementar relatório de qualidade;
5. implementar preparação e divisão dos dados;
6. implementar o detector multirrótulo de aspectos;
7. implementar calibração de thresholds;
8. implementar o classificador de sentimento condicionado ao aspecto;
9. implementar avaliação separada dos modelos;
10. implementar avaliação integrada;
11. implementar exportação e recarga dos artefatos;
12. implementar a API FastAPI;
13. implementar testes;
14. criar Dockerfile e Docker Compose;
15. finalizar README e exemplos.

Em cada etapa:

- gere código funcional, não apenas pseudocódigo;
- mantenha tipos e docstrings;
- evite duplicação;
- mantenha taxonomia e mapas em arquivos centrais;
- escreva testes junto com a funcionalidade;
- não avance deixando imports quebrados ou funções vazias;
- execute os testes disponíveis antes de prosseguir;
- documente decisões que alterem este escopo.

---

## 24. Resultado esperado

Ao final, o repositório deve permitir o seguinte fluxo completo:

```text
Dataset estruturado
        ↓
Validação e relatório de qualidade
        ↓
Normalização e divisão sem vazamento
        ↓
Treinamento do detector de aspectos
        ↓
Calibração de thresholds
        ↓
Treinamento do sentimento por aspecto
        ↓
Avaliação integrada no conjunto de teste
        ↓
Exportação dos artefatos versionados
        ↓
API FastAPI para inferência
```

Exemplo final:

Entrada:

```json
{
  "reviewId": "9001",
  "text": "A pizza estava deliciosa, mas chegou fria e a embalagem vazou."
}
```

Saída esperada:

```json
{
  "reviewId": "9001",
  "aspects": [
    {
      "entity": "produto",
      "aspect": "sabor",
      "sentiment": "positivo"
    },
    {
      "entity": "produto",
      "aspect": "temperatura",
      "sentiment": "negativo"
    },
    {
      "entity": "loja",
      "aspect": "embalagem",
      "sentiment": "negativo"
    }
  ]
}
```

Implemente o projeto respeitando este documento como especificação funcional e técnica do MVP.
