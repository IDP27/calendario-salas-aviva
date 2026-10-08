# Calendário provisório de salas

Agenda de eventos de Costa do Sauípe e Rio Quente para 2026–2028, desenvolvida em **Python + Flask + PostgreSQL**, com interface HTML/CSS/JavaScript.

O piloto local está em `painel/`. Com o PostgreSQL já preparado e ativo:

```sh
cd painel
.venv/bin/python serve.py
```

Abra **http://127.0.0.1:4174** e crie sua primeira conta individual. Não há usuário ou senha de demonstração no calendário.

[Execução, administração e recuperação](painel/README.md) · [Entrega e validação](painel/docs/IMPLEMENTACAO.md)

A versão anterior foi preservada em `painel/legacy/`. Os dados antigos do navegador não foram convertidos em reservas.
