"""Builds data/seed.json from the captured Brendi page (media/reference/brendi-centro/page.html).

The seed is the starting menu of the order database: categories, products, option groups
(sizes, flavors, add-ons), delivery neighborhoods with fees, hours and store settings.
It also lists every product photo in media/manifest.json so the media-sync workflow can
download them.

Run: python3 tools/brendi-import.py
"""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / 'media/reference/brendi-centro/page.html'
IMAGE_BASE = 'https://pedido.brendi.com.br/api/imagesV2/'

html = PAGE.read_text(encoding='utf-8')
raw = json.loads(re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S).group(1))


def resolve(i, depth=0):
    """Expands Nuxt's devalue payload (values referenced by index)."""
    v = raw[i]
    if depth > 80:
        return None
    if isinstance(v, list):
        if v and isinstance(v[0], str) and v[0] in ('Reactive', 'ShallowReactive', 'Ref', 'ShallowRef', 'EmptyRef', 'Set', 'Map', 'Date', 'NuxtError'):
            if v[0] == 'Set':
                return [resolve(x, depth + 1) for x in v[1:]]
            if v[0] == 'Date':
                return v[1]
            return resolve(v[1], depth + 1) if len(v) > 1 else None
        return [resolve(x, depth + 1) if isinstance(x, int) else x for x in v]
    if isinstance(v, dict):
        return {k: (resolve(x, depth + 1) if isinstance(x, int) else x) for k, x in v.items()}
    return v


menu = resolve(0)['data']['menu-ditos-lanches-centro']
store = menu['store']


def slugify(text):
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def tidy(text):
    text = re.sub(r'\s+', ' ', (text or '').replace(' ', ' ')).strip()
    text = re.sub(r'\s+([,.])', r'\1', text)
    text = re.sub(r',(?=[^\s\d])', ', ', text)
    return text


FIXES = {
    'Cheedar': 'Cheddar', 'Fitas Cheddar': 'Fritas cheddar', 'goumert': 'gourmet', 'Combox': 'Combo',
    'Agua': 'Água', 'Guarana': 'Guaraná', 'Aneis': 'Anéis', 'Classico': 'Clássico', 'Magnifico': 'Magnífico',
    'Autentico': 'Autêntico', 'Burguer': 'Burger', 'burguers': 'burgers', 'Xis File': 'Xis Filé', 'File de Frango': 'Filé de Frango',
    'Xis costela': 'Xis Costela', 'mussarela': 'muçarela', 'Mussarela': 'Muçarela', 'Muçarela Empanada': 'Muçarela empanada',
    'Coca cola': 'Coca-Cola', 'Coca Cola': 'Coca-Cola', 'Pequena ': 'Pequena', 'Hamburguer': 'Hambúrguer',
    'Maionese De': 'Maionese de', 'zero': 'Zero'
}


def fix(text):
    for a, b in FIXES.items():
        text = text.replace(a, b)
    return text


CATEGORIES = [
    ('Combos Para Compartilhar', 'combos', 'Combos pra dividir', 'Pra mesa inteira, ou pra quem está com muita fome.'),
    ('Linha Xis ( Podrão, Tradicional)', 'xis', 'Linha Xis', 'O podrão tradicional, no pão de hambúrguer, com ovo e maionese verde.'),
    ('Entradas', 'entradas', 'Entradas e porções', 'Batata, coxinha, anéis de cebola. Pra começar ou pra acompanhar.'),
    ('Burgers', 'burgers', 'Burgers artesanais', 'Pão brioche, blend da casa e a chapa bem quente.'),
    ('Clássicos Ditos', 'classicos', 'Clássicos Ditos', 'Os de sempre, do jeito que São Mateus conhece.'),
    ('Burgers de frango', 'frango', 'Burgers de frango', ''),
    ('Vegetariano', 'vegetariano', 'Vegetariano', ''),
    ('Fit', 'fit', 'Fit', 'No pão árabe, mais leve.'),
    ('Infantil', 'infantil', 'Infantil', ''),
    ('Churros', 'churros', 'Churros', 'Pra fechar com doce.'),
    ('Molhos', 'molhos', 'Molhos da casa', 'Bisnaga pra levar o molho pra casa.'),
    ('Bebidas', 'bebidas', 'Bebidas', 'Sempre gelada.'),
]

cats_by_name = {c['name'].strip(): c for c in menu['categories']}
groups = {}          # signature -> group
seed_categories = []
manifest_images = []
used_slugs = set()


def group_for(custom):
    choices = [ch for ch in custom.get('choices') or [] if ch.get('active') is not False]
    ctype = custom.get('type')
    title = fix(tidy(custom.get('title') or 'Opções'))
    options = [{'title': fix(tidy(ch.get('title')))[:1].upper() + fix(tidy(ch.get('title')))[1:], 'price': round((ch.get('extraPrice') or 0) / 100, 2),
                'max': ch.get('maxChoices') or (custom.get('maxChoices') or 1)} for ch in choices]
    if ctype == 'unique':
        kind, mn, mx = 'one', 1 if custom.get('required') else 0, 1
    elif ctype == 'check':
        kind, mn, mx = 'many', custom.get('minChoices') or 0, custom.get('maxChoices') or len(options)
    else:
        kind, mn, mx = 'qty', custom.get('minChoices') or 0, custom.get('maxChoices') or 8
    signature = json.dumps([title, kind, mn, mx, options], ensure_ascii=False)
    if signature not in groups:
        base = slugify(title) or 'opcoes'
        gid, n = base, 2
        while any(g['id'] == gid for g in groups.values()):
            gid, n = f'{base}-{n}', n + 1
        groups[signature] = {'id': gid, 'title': title, 'type': kind, 'min': mn, 'max': mx, 'options': options}
    return groups[signature]['id']


for source_name, cid, name, blurb in CATEGORIES:
    cat = cats_by_name.get(source_name)
    if not cat:
        raise SystemExit(f'Categoria não encontrada: {source_name}')
    products = []
    for p in menu['productsByCategory'].get(cat['id'], []):
        if p.get('active') is False:
            continue
        pname = fix(tidy(p['name']))
        slug = slugify(pname)
        twin = next((q for q in menu['productsByCategory'].get(cat['id'], []) if q is not p and q.get('active') is not False
                     and slugify(fix(tidy(q['name']))) == slug), None)
        if twin and len(twin.get('customs') or []) > len(p.get('customs') or []):
            continue
        if slug in used_slugs:
            continue
        used_slugs.add(slug)
        image = ''
        if p.get('picture'):
            image = f'assets/menu/{slug}.webp'
            manifest_images.append({
                'url': IMAGE_BASE + p['picture'].replace('/', '%2F') + '?w=720&h=720&q=86&fit=cover&format=webp',
                'path': f'media/raw/menu/{slug}.webp'
            })
        products.append({
            'slug': slug,
            'name': pname,
            'description': fix(tidy(p.get('description'))),
            'price': round((p.get('price') or 0) / 100, 2),
            'image': image,
            'groups': [group_for(c) for c in p.get('customs') or [] if c.get('active') is not False]
        })
    seed_categories.append({'id': cid, 'name': name, 'blurb': blurb, 'products': products})

# Pequenos acertos de texto do cardápio original.
for c in seed_categories:
    for p in c['products']:
        p['description'] = p['description'].replace('Fitas', 'Fritas').replace('Cheedar', 'Cheddar')

neighborhoods = []
for city in store['deliveryRegions']:
    for r in city['regions']:
        neighborhoods.append({'name': tidy(r['name']).replace('Boa vista', 'Boa Vista').replace('Parque das brisas', 'Parque das Brisas').replace('Lago do Cisnes', 'Lago dos Cisnes').replace('Pedra Dágua', "Pedra D'Água"),
                              'fee': r['price'] / 100, 'eta': f"{r['minTime']} a {r['maxTime']} min"})
neighborhoods.sort(key=lambda n: slugify(n['name']))

addr = store['address']
days = {'sun': 0, 'mon': 1, 'tue': 2, 'wed': 3, 'thu': 4, 'fri': 5, 'sat': 6}
open_days = sorted(days[d] for d, spans in store['workingHours'].items() if spans)
span = next(spans[0] for spans in store['workingHours'].values() if spans)
hhmm = lambda m: f'{m // 60:02d}:{m % 60:02d}'

seed = {
    'source': 'Cardápio importado de pedido.brendi.com.br/ditos-lanches-centro',
    'settings': {
        'store_name': 'Ditos Lanches',
        'address': f"{addr['street'].replace('Avenida Doutor', 'Av. Dr.')}, {addr['number']}, {addr['neighborhood']}, {addr['city']} - {addr['state']}",
        'address_2': '',
        'phone': '',
        'whatsapp': '',
        'instagram': 'ditoslanches',
        'hours_label': 'Terça a domingo, das 18h às 23h',
        'open_days': ','.join(map(str, open_days)),
        'open_time': hhmm(span['start']),
        'close_time': hhmm(span['end']),
        'store_mode': 'auto',
        'closed_message': 'A chapa está desligada agora. Abrimos de terça a domingo, às 18h.',
        'min_order': store['minimumOrder'] / 100,
        'delivery_enabled': '1',
        'pickup_enabled': '1',
        'pickup_eta': '15 a 25 min',
        'pix_enabled': '1',
        'pix_key': '',
        'pix_name': 'Ditos Lanches',
        'pix_city': 'Sao Mateus',
        'avg_prep': '20 a 35 min'
    },
    'groups': list(groups.values()),
    'categories': seed_categories,
    'neighborhoods': neighborhoods
}

(ROOT / 'data').mkdir(exist_ok=True)
(ROOT / 'data/seed.json').write_text(json.dumps(seed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

manifest_path = ROOT / 'media/manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
manifest_images += [
    {'url': IMAGE_BASE + store['logo'].replace('/', '%2F') + '?w=600&h=600&q=90&fit=contain&format=png', 'path': 'media/raw/brand/logo-brendi.png'},
    {'url': IMAGE_BASE + store['banner'].replace('/', '%2F') + '?w=1600&h=600&q=90&fit=cover&format=webp', 'path': 'media/raw/brand/banner-brendi.webp'},
]
known = {f['path'] for f in manifest['files']}
manifest['files'] += [m for m in manifest_images if m['path'] not in known]
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

total = sum(len(c['products']) for c in seed_categories)
print(f'{len(seed_categories)} categorias, {total} produtos, {len(groups)} grupos de opções, {len(neighborhoods)} bairros, {len(manifest_images)} fotos')
