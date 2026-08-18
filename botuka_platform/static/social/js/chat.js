(function () {
    'use strict';

    var section = document.querySelector('.social-conversation');
    var form = document.querySelector('[data-chat-form]');
    var list = document.querySelector('[data-message-list]');

    if (!section || !form || !list) {
        return;
    }

    var input = form.querySelector('input[name="texto"]');
    var conversation = section.dataset.conversation;
    var currentUser = String(section.dataset.currentUser || '');

    var socket = null;
    var reconnectTimer = null;
    var reconnectDelay = 1000;
    var destroyed = false;
    var syncing = false;

    function scrollToLast() {
        requestAnimationFrame(function () {
            list.scrollTop = list.scrollHeight;
        });
    }

    function messageExists(id) {
        if (!id) {
            return false;
        }

        return !!list.querySelector(
            '[data-message-id="' + CSS.escape(String(id)) + '"]'
        );
    }

    function statusLabel(status) {
        if (status === 'read') {
            return 'Lida';
        }

        if (status === 'delivered') {
            return 'Entregue';
        }

        return 'Enviada';
    }

    function appendMessage(message) {
        if (!message || !message.id || messageExists(message.id)) {
            return false;
        }

        var article = document.createElement('article');
        article.dataset.messageId = message.id;

        var own = String(message.sender_id) === currentUser;

        if (own) {
            article.classList.add('is-own');
        }

        var strong = document.createElement('strong');

        strong.textContent = own
            ? 'Você'
            : (message.sender_name || 'Usuário');

        article.appendChild(strong);

        if (message.text) {
            var paragraph = document.createElement('p');
            paragraph.textContent = message.text;
            article.appendChild(paragraph);
        }

        var small = document.createElement('small');
        small.textContent = statusLabel(message.status);

        article.appendChild(small);

        list.appendChild(article);

        scrollToLast();

        return true;
    }

    function websocketUrl() {
        var protocol =
            location.protocol === 'https:'
                ? 'wss://'
                : 'ws://';

        return (
            protocol +
            location.host +
            '/ws/social/mensagens/' +
            conversation +
            '/'
        );
    }

    function connect() {
        if (
            destroyed ||
            !conversation ||
            (
                socket &&
                (
                    socket.readyState === WebSocket.OPEN ||
                    socket.readyState === WebSocket.CONNECTING
                )
            )
        ) {
            return;
        }

        socket = new WebSocket(websocketUrl());

        socket.addEventListener('open', function () {
            reconnectDelay = 1000;
            console.log('BOTUKA CHAT: WebSocket conectado.');
        });

        socket.addEventListener('message', function (event) {
            var data;

            try {
                data = JSON.parse(event.data);
            } catch (error) {
                return;
            }

            if (data.event === 'message.created') {
                appendMessage(data.message);
            }
        });

        socket.addEventListener('close', function () {
            if (destroyed) {
                return;
            }

            clearTimeout(reconnectTimer);

            reconnectTimer = setTimeout(
                connect,
                reconnectDelay
            );

            reconnectDelay = Math.min(
                reconnectDelay * 2,
                15000
            );
        });

        socket.addEventListener('error', function () {
            try {
                socket.close();
            } catch (error) {
                // reconexao sera feita no close
            }
        });
    }

    async function syncMessages() {
        if (destroyed || syncing || document.hidden) {
            return;
        }

        syncing = true;

        try {
            var response = await fetch(
                location.href,
                {
                    headers: {
                        'X-Requested-With':
                            'BOTUKA-CHAT-SYNC'
                    },
                    cache: 'no-store'
                }
            );

            if (!response.ok) {
                return;
            }

            var html = await response.text();

            var parser = new DOMParser();
            var doc = parser.parseFromString(
                html,
                'text/html'
            );

            var remoteMessages = doc.querySelectorAll(
                '[data-message-list] [data-message-id]'
            );

            remoteMessages.forEach(function (remote) {
                var id = remote.dataset.messageId;

                if (!id || messageExists(id)) {
                    return;
                }

                list.appendChild(
                    document.importNode(
                        remote,
                        true
                    )
                );
            });

            scrollToLast();

        } catch (error) {
            console.debug(
                'BOTUKA CHAT: sync indisponivel.',
                error
            );

        } finally {
            syncing = false;
        }
    }

    form.addEventListener(
        'submit',
        async function (event) {
            event.preventDefault();

            var text = input.value.trim();

            if (!text) {
                return;
            }

            var csrf = form.querySelector(
                '[name="csrfmiddlewaretoken"]'
            ).value;

            input.disabled = true;

            try {
                var response = await fetch(
                    location.href,
                    {
                        method: 'POST',

                        headers: {
                            'X-CSRFToken': csrf,
                            'X-Requested-With':
                                'XMLHttpRequest',
                            'Content-Type':
                                'application/x-www-form-urlencoded'
                        },

                        body: new URLSearchParams({
                            texto: text
                        })
                    }
                );

                if (!response.ok) {
                    throw new Error(
                        'Falha ao enviar mensagem.'
                    );
                }

                var data = await response.json();

                appendMessage({
                    id: data.id,
                    sender_id: currentUser,
                    sender_name: 'Você',
                    text: data.text,
                    created_at: data.created_at,
                    status:
                        data.status || 'delivered'
                });

                input.value = '';
                input.focus();

            } catch (error) {
                console.error(
                    'BOTUKA Social: erro ao enviar mensagem.',
                    error
                );

            } finally {
                input.disabled = false;
            }
        }
    );

    document.addEventListener(
        'visibilitychange',
        function () {
            if (!document.hidden) {
                syncMessages();
                scrollToLast();
            }
        }
    );

    window.addEventListener(
        'beforeunload',
        function () {
            destroyed = true;

            clearTimeout(reconnectTimer);

            if (socket) {
                try {
                    socket.close();
                } catch (error) {
                    // nada
                }
            }
        }
    );

    /*
     * Ao abrir conversa:
     * sempre mostrar a mensagem mais recente.
     */
    scrollToLast();

    /*
     * WebSocket continua sendo o transporte principal.
     */
    connect();

    /*
     * Fallback temporario:
     * sincroniza sem F5.
     */
    setInterval(
        syncMessages,
        1200
    );

})();
