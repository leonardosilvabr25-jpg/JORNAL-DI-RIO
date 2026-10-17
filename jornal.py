#!/usr/bin/env python3
"""Jornal diário: lê feeds RSS por nicho, traduz manchete e resumo e gera jornal.html."""

import argparse
import hashlib
import html
import json
import re
import socket
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from deep_translator import GoogleTranslator

PASTA = Path(__file__).parent
ARQUIVO_FEEDS = PASTA / "feeds.json"
ARQUIVO_CACHE = PASTA / "cache_traducoes.json"

IDIOMAS = {
    "pt": "Português (BR)",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "ru": "Русский",
    "zh-CN": "中文",
    "ja": "日本語",
}

NOMES_NICHO = {
    "mundo": "Mundo",
    "politica": "Política",
    "economia": "Economia",
    "tecnologia": "Tecnologia",
    "ciencia": "Ciência",
    "esportes": "Esportes",
}

CSS = """
:root{--fundo:#f7f5f0;--texto:#1d1d1f;--secundario:#6b6b6b;--destaque:#8a1c1c;--cartao:#ffffff;--borda:#e2ded4}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--fundo:#141414;--texto:#eaeaea;--secundario:#9a9a9a;--destaque:#e07a7a;--cartao:#1e1e1e;--borda:#333}}
:root[data-theme="dark"]{--fundo:#141414;--texto:#eaeaea;--secundario:#9a9a9a;--destaque:#e07a7a;--cartao:#1e1e1e;--borda:#333}
[hidden]{display:none!important}
body{margin:0;background:var(--fundo);color:var(--texto);font-family:Georgia,serif;line-height:1.5}
header{padding:20px 16px 8px;text-align:center;border-bottom:1px solid var(--borda)}
header h1{margin:0;font-size:2rem;color:var(--destaque)}
header p{margin:4px 0 0;color:var(--secundario);font-size:.9rem}
.controles{max-width:820px;margin:0 auto;padding:12px 16px;display:flex;flex-wrap:wrap;gap:8px;justify-content:center}
.controles button{font:inherit;font-size:.85rem;padding:6px 12px;border:1px solid var(--borda);background:var(--cartao);color:var(--texto);border-radius:999px;cursor:pointer}
.controles button.ativo{background:var(--destaque);border-color:var(--destaque);color:#fff}
main{max-width:820px;margin:0 auto;padding:8px 16px 40px}
.card{background:var(--cartao);border:1px solid var(--borda);border-radius:10px;padding:16px 18px;margin:14px 0}
.meta{margin:0;color:var(--secundario);font-size:.8rem;font-family:system-ui,sans-serif}
.card h2{margin:6px 0;font-size:1.2rem;line-height:1.3}
.card h2 a{color:var(--texto);text-decoration:none}
.card h2 a:hover{text-decoration:underline}
.card p{margin:6px 0}
.original{color:var(--secundario);font-size:.85rem;font-style:italic}
.ler a{color:var(--destaque);font-family:system-ui,sans-serif;font-size:.9rem}
.vazio{text-align:center;color:var(--secundario);padding:40px 0}
"""

JS = """
const estado={idioma:"__IDIOMA_INICIAL__",nicho:"todos"};
function atualizar(){
  document.querySelectorAll(".edicao").forEach(s=>{s.hidden=s.dataset.idioma!==estado.idioma;});
  document.querySelectorAll(".card").forEach(c=>{
    const mostra=estado.nicho==="todos"||c.dataset.nicho===estado.nicho;
    c.hidden=!mostra;
  });
  document.querySelectorAll("[data-idioma-botao]").forEach(b=>b.classList.toggle("ativo",b.dataset.idiomaBotao===estado.idioma));
  document.querySelectorAll("[data-nicho-botao]").forEach(b=>b.classList.toggle("ativo",b.dataset.nichoBotao===estado.nicho));
}
document.querySelectorAll("[data-idioma-botao]").forEach(b=>b.addEventListener("click",()=>{estado.idioma=b.dataset.idiomaBotao;atualizar();}));
document.querySelectorAll("[data-nicho-botao]").forEach(b=>b.addEventListener("click",()=>{estado.nicho=b.dataset.nichoBotao;atualizar();}));
atualizar();
"""


def filho(elemento, *nomes):
    for item in elemento:
        if item.tag.split("}")[-1] in nomes:
            return item
    return None


def limpar(texto, limite=400):
    if not texto:
        return ""
    sem_tags = re.sub(r"<[^>]+>", " ", texto)
    limpo = re.sub(r"\s+", " ", html.unescape(sem_tags)).strip()
    return limpo[:limite] + ("…" if len(limpo) > limite else "")


def data_da_noticia(texto):
    if not texto:
        return None
    try:
        data = parsedate_to_datetime(texto)
    except (TypeError, ValueError):
        try:
            data = datetime.fromisoformat(texto.replace("Z", "+00:00"))
        except ValueError:
            return None
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return data


def ler_feed(url):
    with urllib.request.urlopen(url, timeout=20) as resposta:
        raiz = ET.fromstring(resposta.read())

    noticias = []
    for el in raiz.iter():
        if el.tag.split("}")[-1] not in ("item", "entry"):
            continue
        titulo = filho(el, "title")
        if titulo is None or not titulo.text:
            continue
        link = filho(el, "link")
        resumo = filho(el, "description", "summary", "content")
        data = filho(el, "pubDate", "published", "updated")
        endereco = ""
        if link is not None:
            endereco = link.get("href") or link.text or ""
        noticias.append({
            "titulo": limpar(titulo.text, 300),
            "resumo": limpar(resumo.text if resumo is not None else "", 400),
            "link": endereco.strip(),
            "data": data_da_noticia(data.text if data is not None else None),
        })
    return noticias


PAUSA_ENTRE_PEDIDOS = 0.3  # o Google aceita cerca de 5 pedidos por segundo
TENTATIVAS = 3
FALHAS_PARA_DESISTIR = 5
SALVAR_A_CADA = 20  # traduções novas antes de gravar o cache no disco
TEMPO_LIMITE = 20  # segundos para uma conexão antes de desistir


class Tradutor:
    # Quando o Google recusa, todas as instâncias param de tentar por um tempo.
    pausa_ate = 0.0

    def __init__(self, destino):
        self.destino = destino
        self.cliente = GoogleTranslator(source="auto", target=destino)
        if ARQUIVO_CACHE.exists():
            self.cache = json.loads(ARQUIVO_CACHE.read_text(encoding="utf-8"))
        else:
            self.cache = {}
        self.novas = 0
        self.falhas_seguidas = 0
        self.desistiu = False

    def traduzir(self, texto, origem):
        if not texto or origem.split("-")[0] == self.destino.split("-")[0]:
            return texto
        chave = hashlib.sha1(f"{self.destino}|{texto}".encode("utf-8")).hexdigest()
        if chave in self.cache:
            return self.cache[chave]
        if self.desistiu or time.time() < Tradutor.pausa_ate:
            return texto

        for tentativa in range(TENTATIVAS):
            time.sleep(PAUSA_ENTRE_PEDIDOS)
            try:
                traducao = self.cliente.translate(texto)
            except Exception:
                time.sleep(2 ** (tentativa + 1))
                continue
            self.cache[chave] = traducao or texto
            self.novas += 1
            self.falhas_seguidas = 0
            if self.novas % SALVAR_A_CADA == 0:
                self.salvar()
            return self.cache[chave]

        self.falhas_seguidas += 1
        if self.falhas_seguidas >= FALHAS_PARA_DESISTIR:
            print("  aviso: o Google Tradutor está recusando pedidos. O restante fica no idioma original.")
            print("  Tente de novo daqui a alguns minutos: o que já foi traduzido fica guardado.")
            self.desistiu = True
            Tradutor.pausa_ate = time.time() + 300
        return texto

    def salvar(self):
        if self.novas:
            ARQUIVO_CACHE.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")


def coletar(nichos, feeds, limite):
    noticias = []
    for nicho in nichos:
        for fonte in feeds.get(nicho, []):
            print(f"Lendo {fonte['nome']} ({nicho})...")
            try:
                itens = ler_feed(fonte["url"])[:limite]
            except Exception as erro:
                print(f"  aviso: falhou ({erro})")
                continue
            for item in itens:
                item.update(nicho=nicho, fonte=fonte["nome"], idioma=fonte["idioma"])
                noticias.append(item)
    return noticias


def cartao(noticia, codigo):
    original = ""
    if noticia["idioma"].split("-")[0] != codigo.split("-")[0]:
        original = f'<p class="original">Título original: {html.escape(noticia["titulo"])}</p>'
    data = noticia["data"].astimezone().strftime("%d/%m/%Y %H:%M") if noticia["data"] else ""
    nicho = NOMES_NICHO.get(noticia["nicho"], noticia["nicho"])
    link = html.escape(noticia["link"] or "#")
    return f"""<article class="card" data-nicho="{noticia['nicho']}">
  <p class="meta">{html.escape(nicho)} · {html.escape(noticia['fonte'])} · {data}</p>
  <h2><a href="{link}" target="_blank" rel="noopener">{html.escape(noticia['titulo_traduzido'])}</a></h2>
  <p>{html.escape(noticia['resumo_traduzido'])}</p>
  {original}
  <p class="ler"><a href="{link}" target="_blank" rel="noopener">Ler matéria completa</a></p>
</article>
"""


def pagina(edicoes, nichos, gerado_em):
    botoes_idioma = "".join(
        f'<button type="button" data-idioma-botao="{codigo}">{IDIOMAS[codigo]}</button>'
        for codigo in edicoes
    )
    botoes_nicho = '<button type="button" data-nicho-botao="todos">Todos</button>' + "".join(
        f'<button type="button" data-nicho-botao="{nicho}">{NOMES_NICHO.get(nicho, nicho)}</button>'
        for nicho in nichos
    )
    secoes = ""
    for codigo, lista in edicoes.items():
        corpo = "".join(cartao(noticia, codigo) for noticia in lista)
        if not lista:
            corpo = '<p class="vazio">Nenhuma notícia encontrada.</p>'
        secoes += f'<section class="edicao" data-idioma="{codigo}" hidden>\n{corpo}</section>\n'

    js = JS.replace("__IDIOMA_INICIAL__", next(iter(edicoes)))
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jornal Diário</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>Jornal Diário</h1>
  <p>Gerado em {gerado_em}</p>
</header>
<div class="controles">{botoes_idioma}</div>
<div class="controles">{botoes_nicho}</div>
<main>
{secoes}</main>
<script>{js}</script>
</body>
</html>
"""


def main():
    socket.setdefaulttimeout(TEMPO_LIMITE)
    feeds = json.loads(ARQUIVO_FEEDS.read_text(encoding="utf-8"))["nichos"]

    parser = argparse.ArgumentParser(description="Gera um jornal diário a partir de feeds RSS.")
    parser.add_argument("--nicho", default="todos", help=f"todos ou um de: {', '.join(feeds)}")
    parser.add_argument("--busca", default="", help="filtra as notícias por palavra ou expressão (idioma original)")
    parser.add_argument("--idioma", nargs="+", default=["pt"], choices=list(IDIOMAS),
                        help="um ou mais idiomas do jornal")
    parser.add_argument("--limite", type=int, default=10, help="notícias por fonte")
    parser.add_argument("--saida", default=str(PASTA / "jornal.html"))
    args = parser.parse_args()

    if args.nicho != "todos" and args.nicho not in feeds:
        parser.error(f"nicho desconhecido: {args.nicho}")
    nichos = list(feeds) if args.nicho == "todos" else [args.nicho]

    noticias = coletar(nichos, feeds, args.limite)
    if args.busca:
        termo = args.busca.lower()
        noticias = [n for n in noticias if termo in f"{n['titulo']} {n['resumo']}".lower()]
    noticias.sort(key=lambda n: n["data"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    edicoes = {}
    for codigo in args.idioma:
        print(f"Traduzindo para {IDIOMAS[codigo]}...")
        tradutor = Tradutor(codigo)
        edicoes[codigo] = [
            {
                **noticia,
                "titulo_traduzido": tradutor.traduzir(noticia["titulo"], noticia["idioma"]),
                "resumo_traduzido": tradutor.traduzir(noticia["resumo"], noticia["idioma"]),
            }
            for noticia in noticias
        ]
        tradutor.salvar()

    gerado_em = datetime.now().strftime("%d/%m/%Y %H:%M")
    Path(args.saida).write_text(pagina(edicoes, nichos, gerado_em), encoding="utf-8")
    print(f"Pronto: {len(noticias)} notícias em {args.saida}")


if __name__ == "__main__":
    main()
