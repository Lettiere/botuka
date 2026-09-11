# Sincronização semanal de empresas

O projeto usa `TIME_ZONE = 'America/Sao_Paulo'` e `USE_TZ = True`. O timer declara
explicitamente a mesma zona e dispara toda segunda-feira às `00:00:01`.

Revise `User`, `Group`, `WorkingDirectory`, `EnvironmentFile` e o caminho do Python
no service antes da instalação. O arquivo de ambiente deve conter as mesmas
variáveis usadas pela aplicação web, inclusive credenciais do executor do banco.

Instalação futura (não executar durante a implementação):

```bash
sudo install -m 0644 ops/systemd/botuka-empresas-sync.service /etc/systemd/system/
sudo install -m 0644 ops/systemd/botuka-empresas-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now botuka-empresas-sync.timer
systemctl list-timers botuka-empresas-sync.timer
```

Para validar sem habilitar o timer:

```bash
systemd-analyze verify ops/systemd/botuka-empresas-sync.service ops/systemd/botuka-empresas-sync.timer
systemctl cat botuka-empresas-sync.timer
```

Cada disparo normal cria uma execução nova com cursor vazio. Uma falha tratada
fica em `ERRO` e pode ser retomada com
`python manage.py sincronizar_empresas_botucatu --retomar ID`. Uma queda abrupta
deixa `EXECUTANDO`; apó 2 horas sem heartbeat (`EMPRESA_IMPORTACAO_LOCK_TIMEOUT`,
em segundos), a próxima tentativa retoma automaticamente a mesma execução.
