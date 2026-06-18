# OLX CLI

CLI para buscar e consultar anúncios da **OLX Brasil**. Suporta dois backends de scraping:

- **🦎 Crawl4AI** (default) — via browser headless, contorna Cloudflare
- **🔥 Firecrawl** — alternativa, configurável via `OLX_BACKEND`

Extrai dados estruturados do HTML renderizado (Next.js SSR / Schema.org JSON-LD).

## ⚡ Quick Start

```bash
# 1. Configure o backend
cp .env.example .env
# Edite .env com sua URL do Crawl4AI ou Firecrawl

# 2. Busque anúncios
olx-pp-cli crawl buscar-anuncios --q "notebook" --categoria "informatica/notebooks" --localizacao "estado-sp" --agent

# 3. Ou use o wrapper amigável
olx buscar notebook --categoria "informatica/notebooks"
```

## 🔧 Backends de Scraping

O CLI suporta dois motores de scraping, selecionáveis via variável de ambiente:

### 🦎 Crawl4AI (default)

```env
OLX_BACKEND=crawl4ai
OLX_BASE_URL=https://seu-crawl4ai:8000
```

**Endpoint:** `POST /crawl`
**Body:**
```json
{"urls": ["https://www.olx.com.br/..."], "priority": 10}
```
**Resposta:** Retorna HTML + Markdown com `__NEXT_DATA__` embedado.

Requer [Crawl4AI](https://github.com/unclecode/crawl4ai) rodando (Docker, Coolify, etc). É o backend padrão e o mais testado.

### 🔥 Firecrawl

```env
OLX_BACKEND=firecrawl
OLX_BASE_URL=http://localhost:3002
```

**Endpoint:** `POST /v1/scrape`
**Body:**
```json
{"url": "https://www.olx.com.br/...", "formats": ["markdown", "html"]}
```
**Resposta:** Normalizada automaticamente para o mesmo formato do Crawl4AI.

Requer [Firecrawl](https://github.com/nickli/Firecrawl) rodando. A resposta é convertida internamente para o formato Crawl4AI, então toda a pipeline de extração funciona sem alterações.

### Alternativa: `CRAWL4AI_URL`

A variável `CRAWL4AI_URL` funciona como fallback para `OLX_BASE_URL`:

```env
CRAWL4AI_URL=https://meu-crawler:8000
```

## 📦 Instalação

### Via Printing Press Library (recomendado)

```bash
npx -y @mvanhorn/printing-press-library install olx
```

### Build manual

```bash
go build -o build/stage/bin/olx-pp-cli ./cmd/olx-pp-cli/
go build -o build/stage/bin/olx-pp-mcp  ./cmd/olx-pp-mcp/
```

### Wrapper amigável (`olx`)

O repositório inclui um wrapper Bash que auto-carrega o `.env`:

```bash
cp .env.example .env
# Edite as URLs
./olx buscar notebook
```

## 🚀 Comandos

### Buscar anúncios

```bash
olx-pp-cli crawl buscar-anuncios --q "<termo>" [flags]
# ou
olx buscar "<termo>" [flags]
```

**Flags:**
| Flag | Descrição | Exemplo |
|------|-----------|---------|
| `--q` | Termo de busca | `"notebook"`, `"crossfox 2016"` |
| `--categoria` | Caminho da categoria | `informatica/notebooks`, `celulares`, `autos-e-pecas/carros-vans-e-utilitarios` |
| `--localizacao` | Path completo de localização | `estado-sp`, `estado-rj/niteroi`, `estado-rj/rio-de-janeiro-e-regiao/niteroi/centro` |
| `--pagina` | Número da página (default: 1) | `2` |
| `--sort` | Ordenação | `date`, `price_asc`, `price_desc` |
| `--min-preco` | Preço mínimo | `500` |
| `--max-preco` | Preço máximo | `5000` |

**Exemplos:**

```bash
# Busca simples
olx buscar notebook

# Com categoria e localização
olx buscar iphone --categoria "celulares" --localizacao "estado-sp"

# CrossFox 2016 em Niterói
olx buscar "crossfox 2016" --categoria "autos-e-pecas/carros-vans-e-utilitarios" --localizacao "estado-rj/rio-de-janeiro-e-regiao/niteroi"

# Com filtro de preço e ordenação
olx buscar geladeira --min-preco 500 --max-preco 2000 --sort price_asc
```

### Detalhes de um anúncio

```bash
olx-pp-cli crawl detalhes-anuncio --id <listId>
# ou
olx detalhes <listId>
```

### Listar categorias

```bash
olx-pp-cli crawl listar-categorias
# ou
olx categorias
```

### Descobrir localizações

```bash
olx locais           # Lista estados disponíveis
olx locais rj        # Mostra regiões e cidades do RJ
olx locais sp        # Mostra cidades de SP
```

## 🗺️ Localizações (formato)

A localização segue a hierarquia da OLX:

```
/<categoria>/<estado>/<regiao>/<cidade>/<bairro>
```

O slug é o nome em **minúsculo, sem acentos, com espaços → hífens**:

| Nome real | Slug |
|-----------|------|
| Rio de Janeiro | `rio-de-janeiro` |
| São Paulo | `sao-paulo` |
| Belo Horizonte | `belo-horizonte` |
| Grande Goiânia e Anápolis | `grande-goiania-e-anapolis` |

**Exemplos de path completo:**

| Localização | `--localizacao` |
|-------------|-----------------|
| Todo o estado de SP | `estado-sp` |
| Niterói - RJ | `estado-rj/rio-de-janeiro-e-regiao/niteroi` |
| Centro de Niterói | `estado-rj/rio-de-janeiro-e-regiao/niteroi/centro` |
| Petrópolis - RJ | `estado-rj/serra-angra-dos-reis-e-regiao/petropolis` |

## 📋 Categorias comuns

| Categoria | Path |
|-----------|------|
| Carros | `autos-e-pecas/carros-vans-e-utilitarios` |
| Celulares | `celulares` |
| Notebooks | `informatica/notebooks` |
| Imóveis - Venda | `imoveis/venda` |
| Imóveis - Aluguel | `imoveis/aluguel` |
| Games | `games` |
| TVs | `tvs-e-video` |

Use `olx categorias` para listar todas.

## 🔐 Configuração

### Variáveis de ambiente

| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `OLX_BASE_URL` | ✅ | URL do servidor de scraping |
| `OLX_BACKEND` | ❌ | `crawl4ai` (default) ou `firecrawl` |
| `CRAWL4AI_URL` | ❌ | Fallback para `OLX_BASE_URL` |

### Arquivo `.env`

O wrapper `olx` e o CLI lêem as variáveis de ambiente. Crie um `.env`:

```bash
cp .env.example .env
```

Exemplo para Crawl4AI:
```env
OLX_BACKEND=crawl4ai
OLX_BASE_URL=https://crawl4ai:8000
```

Exemplo para Firecrawl:
```env
OLX_BACKEND=firecrawl
OLX_BASE_URL=http://localhost:3002
```

### Arquivo de configuração TOML

Path: `~/.config/olx-pp-cli/config.toml`

```toml
base_url = "https://crawl4ai:8000"
backend = "crawl4ai"
```

## 🤖 MCP Server

O CLI inclui um servidor MCP (Model Context Protocol) para integração com IDEs e agentes:

```bash
# Modo stdio (default)
olx-pp-mcp

# Modo HTTP
olx-pp-mcp -transport http -addr :7777
```

**13 tools MCP disponíveis**, incluindo:
- `crawl_buscar-anuncios` — Buscar anúncios com filtros
- `crawl_detalhes-anuncio` — Detalhes de um anúncio
- `crawl_listar-categorias` — Listar categorias
- `sql` — Consultar dados sincronizados localmente
- `sync` — Sincronizar dados para SQLite local

## 🏗️ Arquitetura

```
olx (wrapper bash) — carrega .env + chama CLI
  └── olx-pp-cli (Go)
        └── backend.Scrape() — Crawl4AI ou Firecrawl
              └── browser headless → OLX → HTML
                    └── extract_olx_data.py (extração JSON)
```

O backend escolhido acessa a OLX via browser headless, contornando Cloudflare. Os dados são extraídos do `__NEXT_DATA__` (Next.js SSR) ou Schema.org JSON-LD.

## 📄 Licença

Apache-2.0 — Gerado por [CLI Printing Press](https://github.com/mvanhorn/cli-printing-press)
