# Ditos Lanches: site com pedidos online

Site da Ditos Lanches (São Mateus, ES) com vídeo que anda junto com a rolagem, faixa de banners animados, cardápio completo com adicionais, carrinho em forma de comanda, checkout com entrega por bairro, Pix, acompanhamento do pedido em tempo real e painel da cozinha.

Tudo roda com **Node.js 22.5 ou mais novo, sem nenhuma dependência para instalar**. O banco de dados é SQLite, embutido no próprio Node.

## Rodar

```bash
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
| `DB_PATH` | arquivo do banco de dados | `data/ditos.db` |
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
- **Plano B sem servidor**: se a API cair, o site usa a cópia `public/assets/data/menu.json` (o servidor atualiza sozinho) e manda o pedido pronto pelo WhatsApp.

## Estrutura

```
server.js                 servidor, API e banco (SQLite)
data/seed.json            cardápio inicial (usado só quando o banco está vazio)
public/index.html         o site
public/pedido.html        acompanhamento do pedido
public/admin.html         painel da cozinha
public/assets/            css, js, fontes, imagens, vídeos e banners
media/                    mídia original gerada no Higgsfield e capturas de referência (não vai pro ar)
docs/design-package.md    decisões de design e textos do site
```

O banco fica em `data/ditos.db`. **Faça cópia desse arquivo** para guardar os pedidos.

## Mídia

Imagens e vídeos foram gerados no Higgsfield. Como a rede de desenvolvimento bloqueia o CDN, o workflow `.github/workflows/media-sync.yml` baixa os arquivos listados em `media/manifest.json` para `media/raw/`. Os arquivos otimizados para o site ficam em `public/assets/` (vídeo principal em WebM e MP4, banners em loop sem emenda).

## Publicar

Precisa de uma hospedagem que rode **Node.js 22.5+** (por exemplo, planos da Hostinger com suporte a aplicações Node.js). Rode `npm start` com `ADMIN_PASSWORD` definida e mantenha a pasta `data/` persistente entre atualizações.
