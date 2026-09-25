# Ditos Lanches: pacote de design

Tier 1, uma cena contínua de 6 segundos. Tudo que está entre aspas aqui vai para o site palavra por palavra.

## 1. A premissa da marca

A palavra é **chapa**. A Ditos faz lanche na chapa em São Mateus desde 2002, e o medo de quem pede delivery é sempre o mesmo: "chegou frio", "demorou", "veio remexido", "veio errado". O site inteiro ensina e vende uma ideia só: o lanche só entra na chapa quando o seu pedido chega, e sai de lá direto para a sua porta, quente. O vídeo desce pela fumaça da chapa até o combo pronto. A faixa de banners mostra o que está saindo da chapa. O cardápio é uma comanda. O momento interativo é selar a carne. O fechamento diz que a chapa já está quente.

## 2. Paleta (direção antes do vídeo; valores finais saem da filmagem aprovada)

```css
:root{
  --canvas:#17110e;        /* carvão defumado, puxado para o marrom da fumaça */
  --panel:#221915;         /* tábua escura, cartões */
  --accent:#e2412b;        /* vermelho de brasa: botão de pedir e foco */
  --accent-hover:#f25a3f;
  --accent-muted:rgba(226,65,43,.28);
  --cheddar:#f2a72e;       /* destaque raro: preços em promoção, brilho do queijo */
  --paper:#f3e9d8;         /* comanda de papel */
  --text-secondary:#c9b7a3;
  --text-primary:#f6ede1;
}
```

Desvio dito em voz alta: fundo escuro com laranja quente é um dos visuais proibidos por padrão. Aqui ele é o próprio mundo do assunto (chapa, brasa, cheddar), então fica, com três cuidados: o acento é vermelho de brasa e não âmbar, não há serifa de alto contraste, e o elemento assinatura é a comanda de papel.

## 3. Trio tipográfico

- Título: **Dela Gothic One** 400 (letreiro grosso de lanchonete)
- Texto: **Figtree** 400, 600, 800
- Etiquetas e preços: **DM Mono** 400, 500 (comanda, número do pedido)

## 4. Mapa de faixas do vídeo (pontos de partida; o teste de rolagem valida)

Herói com 500vh (400vh de rolagem). A ação fica no centro; o texto vive nas laterais.

| Faixa | Intervalo | O que o vídeo mostra | Texto | Entrada |
|---|---|---|---|---|
| 1 | 0.00 a 0.24 | fumaça e brasas subindo, o pão aparece embaixo | "Saiu da chapa agora." / "Ditos Lanches. São Mateus, desde 2002." | sobe como fumaça (subida com desfoque que clareia) |
| 2 | 0.27 a 0.50 | a câmera desce e atravessa o vapor | "Carne selada na hora." / "Pão tostado na manteiga, queijo derretendo de verdade." | desfoque para nítido (o vapor abrindo) |
| 3 | 0.53 a 0.75 | o lanche sobe para o centro, o combo aparece | "Chega quente na sua porta." / "Entrega própria em São Mateus. Você acompanha cada passo do pedido." | palavra batendo com rebote (a chegada) |
| 4 | 0.79 a 1.00 | o combo parado na tábua | "A maior hamburgueria de São Mateus." / "Monte seu pedido em dois minutos. A chapa já está quente." + botões "Pedir agora" e "Ver cardápio" | palavra por palavra subindo e assentando |

## 5. Herói estático (celular e movimento reduzido)

- Título: "Saiu da chapa, chega quente."
- Linha: "Hambúrguer artesanal em São Mateus desde 2002. Peça pelo site e acompanhe seu pedido até a sua porta."
- Botão: "Pedir agora"

## 6. Seções depois do vídeo (todas levam a "Pedir agora")

1. **Faixa de banners rolando para a direita**: vários banners animados, cada um leva a uma parte do cardápio.
2. **Cardápio** (#cardapio): "O cardápio inteiro, a um toque." / "Escolha, ajuste do seu jeito e mande pra chapa." Abas por categoria, adicionais e observação em cada lanche. O carrinho é a comanda de papel.
3. **Como a gente faz** (#chapa): o momento interativo "Segure para selar a carne". Três passos com imagem cada:
   - "O pedido chega e a chapa acende." 
   - "Carne selada, pão tostado, queijo derretendo."
   - "Embalado fechado, direto pro motoboy."
4. **Entrega** (#entrega): "Quente na porta, sem mistério." Bairros e taxas vindos do banco de dados, e a linha do tempo do pedido: "Recebido", "Na chapa", "Saiu pra entrega", "Entregue".
5. **O que dizem** (#avaliacoes): trechos de avaliações públicas: "A comida é sensacional e o preço é justo." / "Bebida sempre gelada." / "Melhor lugar pra ir com a família."
6. **Perguntas** (#duvidas):
   - "Chega quente mesmo?" "Chega. O lanche só entra na chapa quando o pedido é confirmado e sai embalado fechado direto pro motoboy."
   - "Quanto tempo demora?" "Na maioria dos bairros, entre 35 e 50 minutos. Na página do pedido você vê cada etapa."
   - "Quais bairros vocês atendem?" "Os bairros de São Mateus da lista de entrega. A taxa aparece antes de você fechar o pedido."
   - "Como eu pago?" "Pix pelo site, ou cartão e dinheiro na entrega. Se precisar de troco, é só avisar."
   - "Posso tirar ou trocar ingrediente?" "Pode. Cada lanche tem adicionais e um campo de observação."
   - "E se vier algo errado?" "Chama a gente no WhatsApp com o número do pedido e a gente resolve na hora."
7. **Chamada final**: "A chapa já está quente." / botão "Pedir agora".
8. **Rodapé**: endereço, telefone, horário, Instagram @ditoslanches.

Formulário: o checkout grava o pedido no banco de dados do servidor (SQLite) e abre a página de acompanhamento. Se o servidor estiver fora do ar, o pedido vai pronto por WhatsApp. O cliente sempre sabe para onde o pedido foi.

## 7. Camada vetorial

- Linha de calor ondulada (SVG) que se desenha na rolagem entre as seções.
- Brasas finas subindo no fundo fixo da página, bem discretas.
- Borda picotada da comanda (SVG), carimbo "NA CHAPA" nos status do pedido.
- Movimento reduzido: tudo aparece no estado final, sem animação.

## 8. Engenharia

Blob com anel de carregamento, lerp normalizado por dt, seeks com trava, escrita no DOM só quando muda, faixas medidas em rolagem com o teste de flick, sistema de legibilidade em quatro camadas, os cinco portões do herói estático ao vivo, página completa sem vídeo e o piso de qualidade do `scrub-pipeline.md`.

## 9. Revisão de texto

Todo texto acima vai palavra por palavra. A página construída passa pela revisão: zero travessões, zero palavras de propaganda vazia, e a varredura de vícios de texto de IA antes de qualquer pessoa ver.
