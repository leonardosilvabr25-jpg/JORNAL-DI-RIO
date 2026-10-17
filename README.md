# Jornal Diário

Gera um jornal online com notícias de sites do mundo inteiro, organizado por nicho e idioma. Ele lê feeds RSS, traduz a manchete e o resumo e cria um arquivo `jornal.html` que você abre no navegador.

As matérias completas não são republicadas: o jornal mostra manchete, resumo e o link para a matéria original.

## Instalação (uma vez)

1. Instale o Python 3.10 ou mais novo: https://www.python.org/downloads/
2. Abra o terminal na pasta do projeto e rode:

```
pip install -r requirements.txt
```

## Uso

Gerar o jornal de tecnologia, em português e inglês:

```
python jornal.py --nicho tecnologia --idioma pt en
```

Todos os nichos, em português:

```
python jornal.py --nicho todos --idioma pt
```

Filtrar por palavra-chave (procura no idioma original da matéria):

```
python jornal.py --nicho politica --busca "eleição" --idioma pt
```

Idiomas disponíveis: `pt` (Português BR), `en`, `es`, `fr`, `de`, `ru`, `zh-CN` (Chinês), `ja` (Japonês).

Depois de gerar, abra o arquivo `jornal.html` no navegador. Nele você troca de idioma e de nicho pelos botões.

## Nichos e fontes

As fontes ficam em `feeds.json`. Para adicionar um site, inclua um item no nicho desejado com o nome, o idioma original e o endereço do feed RSS. Os endereços foram escolhidos a partir dos feeds públicos conhecidos, mas podem mudar: se uma fonte aparecer com "falhou", confira o endereço dela.

## Observações

- **Tradução:** usa o Google Tradutor sem chave. É gratuito, mas não é oficial, e pode parar de funcionar sem aviso. As traduções ficam guardadas em `cache_traducoes.json`, então rodar de novo não traduz o mesmo texto outra vez.
- **Busca:** só nos feeds cadastrados. Para pesquisar em todo o mundo por qualquer tema, seria preciso uma API de notícias com chave.
- **Direitos:** o jornal mostra só resumos traduzidos e links. Use as matérias completas pelo site original.
- **Arquivos gerados:** `jornal.html` e `cache_traducoes.json` são criados no seu PC e não vão para o GitHub (estão no `.gitignore`).
