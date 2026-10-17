#!/usr/bin/env python3
"""Painel do Jornal Diário: busca notícias por nicho e idioma e mostra num painel no navegador."""

import json
import socket
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import jornal

PORTA = 8765
VALIDADE_CACHE = 15 * 60  # segundos que as notícias de um nicho ficam guardadas
LIMITE_RESULTADOS = 30

_cache = {}
_travas_nicho = {}
_trava_travas = threading.Lock()
_trava_traducao = threading.Lock()


def feeds_configurados():
    return json.loads(jornal.ARQUIVO_FEEDS.read_text(encoding="utf-8"))["nichos"]


def _trava_do_nicho(nicho):
    with _trava_travas:
        return _travas_nicho.setdefault(nicho, threading.Lock())


def noticias_do_nicho(nicho):
    # Uma trava por nicho: buscas simultâneas esperam a primeira terminar
    # em vez de baixar os mesmos feeds de novo.
    with _trava_do_nicho(nicho):
        guardado = _cache.get(nicho)
        if guardado and time.time() - guardado[0] < VALIDADE_CACHE:
            return guardado[1]
        noticias = jornal.coletar([nicho], feeds_configurados(), limite=15)
        _cache[nicho] = (time.time(), noticias)
        return noticias


def buscar(nicho, termo, idioma):
    feeds = feeds_configurados()
    nichos = list(feeds) if nicho == "todos" else [nicho]
    with ThreadPoolExecutor(max_workers=len(nichos)) as pool:
        listas = list(pool.map(noticias_do_nicho, nichos))
    noticias = [item for lista in listas for item in lista]

    if termo:
        procurado = termo.lower()
        noticias = [n for n in noticias if procurado in f"{n['titulo']} {n['resumo']}".lower()]

    noticias.sort(key=lambda n: n["data"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    noticias = noticias[:LIMITE_RESULTADOS]

    mesmo_idioma = lambda original: original.split("-")[0] == idioma.split("-")[0]
    with _trava_traducao:
        tradutor = jornal.Tradutor(idioma)
        resultado = []
        for n in noticias:
            origem = n["idioma"]
            resultado.append({
                "titulo": tradutor.traduzir(n["titulo"], origem),
                "resumo": tradutor.traduzir(n["resumo"], origem),
                "tituloOriginal": "" if mesmo_idioma(origem) else n["titulo"],
                "fonte": n["fonte"],
                "nicho": n["nicho"],
                "link": n["link"],
                "data": n["data"].astimezone().strftime("%d/%m/%Y %H:%M") if n["data"] else "",
            })
        tradutor.salvar()
    return resultado


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)

        if url.path == "/":
            self._enviar(200, "text/html; charset=utf-8", (jornal.PASTA / "index.html").read_bytes())

        elif url.path == "/api/config":
            nichos = {chave: jornal.NOMES_NICHO.get(chave, chave) for chave in feeds_configurados()}
            self._json({"nichos": nichos, "idiomas": jornal.IDIOMAS})

        elif url.path == "/api/noticias":
            consulta = {chave: valor[0] for chave, valor in parse_qs(url.query).items()}
            nicho = consulta.get("nicho", "todos")
            idioma = consulta.get("idioma", "pt")
            if nicho != "todos" and nicho not in feeds_configurados():
                return self._json({"erro": "Nicho desconhecido."}, 400)
            if idioma not in jornal.IDIOMAS:
                return self._json({"erro": "Idioma desconhecido."}, 400)
            try:
                self._json(buscar(nicho, consulta.get("busca", "").strip(), idioma))
            except Exception as erro:
                self._json({"erro": f"Falha na busca: {erro}"}, 500)

        else:
            self._enviar(404, "text/plain; charset=utf-8", "Não encontrado".encode("utf-8"))

    def _json(self, dados, status=200):
        self._enviar(status, "application/json; charset=utf-8", json.dumps(dados, ensure_ascii=False).encode("utf-8"))

    def _enviar(self, status, tipo, corpo):
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, formato, *args):
        pass


def main():
    socket.setdefaulttimeout(20)
    endereco = f"http://localhost:{PORTA}"
    servidor = ThreadingHTTPServer(("127.0.0.1", PORTA), Handler)
    print(f"Painel aberto em {endereco}. Feche esta janela para encerrar.")
    threading.Timer(1.5, webbrowser.open, args=[endereco]).start()
    servidor.serve_forever()


if __name__ == "__main__":
    main()
