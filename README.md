# Ditos Lanches: site com pedidos online

Site da Ditos Lanches (São Mateus, ES) com vídeo que anda junto com a rolagem, faixa de banners animados, cardápio completo com adicionais, carrinho em forma de comanda, checkout com entrega por bairro, Pix, acompanhamento do pedido em tempo real e painel da cozinha.

Roda de dois jeitos, com o mesmo código:

- **Na Vercel** (recomendado): site estático + função `api/index.js`, com banco **Postgres (Neon)**.
- **No computador ou num servidor próprio**: `npm start`, com banco **SQLite** embutido no Node 22.5+ (arquivo `data/ditos.db`).

O banco é escolhido sozinho: com `DATABASE_URL` (ou `POSTGRES_URL`) usa Postgres; sem, usa SQLite. Na primeira vez, as tabelas são criadas e o cardápio de `data/seed.json` é carregado.

## Publicar na Vercel

1. Entre em **vercel.com** com a sua conta do GitHub.
2. **Add New → Project** e importe o repositório `osmzinpro-hash/a`. Framework: **Other**. Não precisa mudar mais nada, o `vercel.json` cuida do resto.
3. No projeto, aba **Storage → Create Database → Neon (Postgres)** e conecte ao projeto. Isso cria a variável `DATABASE_URL` sozinho.
4. Aba **Settings → Environment Variables**: crie `ADMIN_PASSWORD` com a senha do painel (e, se quiser, `SESSION_SECRET` com um texto longo qualquer).
5. Aba **Deployments → Redeploy**, para o site subir já com o banco e a senha.
6. Pronto: o endereço aparece no topo do projeto (algo como `ditos-lanches.vercel.app`). Para usar um domínio próprio: **Settings → Domains**.

Depois disso, todo `git push` na branch principal publica o site sozinho. Para conferir o banco: `https://SEU-ENDERECO/api/health` mostra `{"ok":true,"db":"pg"}`.

## Rodar no computador

```bash
npm install
ADMIN_PASSWORD="troque-esta-senha" npm start
```

- Site: http://localhost:3000
- Painel da cozinha: http://localhost:3000/admin
- Acompanhamento de um pedido: http://localhost:3000/pedido/CODIGO

Sem `ADMIN_PASSWORD` a senha do painel é `ditos2002`. **Troque antes de publicar.**

| Variável | Para que serve | Padrão |
|---|---|---|
| `PORT` | porta do servidor | `3000` |
| `ADMIN_PASSWORD` | senha do painel da cozinha | `ditos2002` |
| `DATABASE_URL` | Postgres (na Vercel, criado pela integração Neon) | vazio: usa SQLite |
| `DB_PATH` | arquivo do SQLite | `data/ditos.db` |
| `SESSION_SECRET` | assinatura das sessões do painel | derivada da senha |

## Primeiros passos no painel (aba Loja)

1. **WhatsApp** da loja, com DDD. Aparece no rodapé, na página do pedido e no botão de falar com o cliente.
2. **Chave Pix**, nome e cidade do recebedor. Com a chave salva, o checkout passa a oferecer "Pix pelo site", com QR Code e copia e cola. A cozinha marca "pago" quando o dinheiro cair.
3. Confira **horário**, **pedido mínimo** e **tempo de entrega**.
4. Na aba **Cardápio**, confira os preços. Na aba **Bairros**, as taxas.

## O que já vem pronto

- **Cardápio real**: 12 categorias e 56 lanches importados da página da Ditos na Brendi, com fotos, preços, adicionais, tamanhos e sabores (`tools/brendi-import.py` gera `data/seed.json`).
- **56 bairros** de São Mateus com taxa e tempo de entrega.
- **Pagamentos**: Pix pelo site, crédito, débito, dinheiro (com troco) e vale-refeição na entrega.
- **Entrega ou retirada** no balcão.
- **Preços sempre recalculados no servidor.** O navegador nunca define o valor do pedido.
- **Painel da cozinha**: pedidos chegam sozinhos (com som opcional), botões de status (na chapa, saiu pra entrega, entregue), marcar pago, imprimir comanda, WhatsApp do cliente, vendas do dia, editar preços, tirar lanche do ar, bairros e horários.
- **Acompanhamento do pedido**: o cliente vê cada etapa ao vivo e paga o Pix na mesma página.
- **Plano B sem servidor**: se a API cair, o site usa a cópia `public/assets/data/menu.json` e manda o pedido pronto pelo WhatsApp. No modo local essa cópia se atualiza sozinha; na Vercel ela é a do repositório.

## Estrutura

```
server.js                 servidor local (site + API)
api/index.js              a API na Vercel
lib/app.js                lógica da loja: cardápio, pedidos, Pix, painel
lib/db.js                 banco: Postgres (DATABASE_URL) ou SQLite
vercel.json               rotas e configuração da Vercel
data/seed.json            cardápio inicial (usado só quando o banco está vazio)
public/index.html         o site
public/pedido.html        acompanhamento do pedido
public/admin.html         painel da cozinha
public/assets/            css, js, fontes, imagens, vídeos e banners
media/                    mídia original gerada no Higgsfield e capturas de referência (não vai pro ar)
docs/design-package.md    decisões de design e textos do site
```

No modo local o banco fica em `data/ditos.db` (**faça cópia desse arquivo**). Na Vercel os pedidos ficam no Postgres da Neon.

## Mídia

Imagens e vídeos foram gerados no Higgsfield. Como a rede de desenvolvimento bloqueia o CDN, o workflow `.github/workflows/media-sync.yml` baixa os arquivos listados em `media/manifest.json` para `media/raw/`. Os arquivos otimizados para o site ficam em `public/assets/` (vídeo principal em WebM e MP4, banners em loop sem emenda).

## Outro servidor

Qualquer hospedagem que rode **Node.js 22.5+** também serve: `npm install && npm start` com `ADMIN_PASSWORD` definida, e a pasta `data/` mantida entre atualizações (ou um `DATABASE_URL` de Postgres).
