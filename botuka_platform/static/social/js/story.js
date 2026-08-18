(function(){'use strict';function csrf(){return document.querySelector('meta[name="csrf-token"]')?.content||''}async function post(url,data){var response=await fetch(url,{method:'POST',headers:{'X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest','Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(data||{})});if(!response.ok)throw new Error('Falha na interação');return response.json()}document.querySelectorAll('[data-story-like-url]').forEach(function(button){button.addEventListener('click',async function(){button.disabled=true;try{var result=await post(button.dataset.storyLikeUrl);button.setAttribute('aria-pressed',String(result.liked));button.setAttribute('aria-label',result.liked?'Descurtir Story':'Curtir Story');button.querySelector('i').className='bi bi-heart'+(result.liked?'-fill':'');button.querySelector('[data-story-like-count]').textContent=result.count}catch(e){}finally{button.disabled=false}})});document.querySelectorAll('[data-story-reaction-url]').forEach(function(button){button.addEventListener('click',async function(){try{await post(button.dataset.storyReactionUrl,{reaction:button.dataset.reaction});button.closest('details')?.removeAttribute('open')}catch(e){}})});})();

/* BOTUKA_STORY_MULTILINE_START */
(function () {
    "use strict";

    const SELECTOR = "[data-story-reply-textarea]";
    const MAX_LINES = 20;

    function getMetrics(textarea) {
        const styles = window.getComputedStyle(textarea);

        let lineHeight = parseFloat(styles.lineHeight);

        if (!Number.isFinite(lineHeight)) {
            const fontSize = parseFloat(styles.fontSize) || 16;
            lineHeight = fontSize * 1.35;
        }

        const paddingTop =
            parseFloat(styles.paddingTop) || 0;

        const paddingBottom =
            parseFloat(styles.paddingBottom) || 0;

        const borderTop =
            parseFloat(styles.borderTopWidth) || 0;

        const borderBottom =
            parseFloat(styles.borderBottomWidth) || 0;

        return {
            lineHeight,
            extra:
                paddingTop
                + paddingBottom
                + borderTop
                + borderBottom,
        };
    }

    function getMaxHeight(textarea) {
        const metrics = getMetrics(textarea);

        return (
            metrics.lineHeight * MAX_LINES
            + metrics.extra
        );
    }

    function resizeTextarea(textarea) {
        if (!textarea) {
            return;
        }

        textarea.style.height = "auto";

        const maxHeight =
            getMaxHeight(textarea);

        const desiredHeight =
            Math.min(
                textarea.scrollHeight,
                maxHeight
            );

        textarea.style.height =
            `${desiredHeight}px`;

        textarea.style.overflowY =
            textarea.scrollHeight > maxHeight
                ? "auto"
                : "hidden";

        const container =
            textarea.closest(
                ".social-story-interactions"
            );

        if (container) {
            container.classList.toggle(
                "has-expanded-reply",
                desiredHeight > 64
            );
        }
    }

    function initializeTextarea(textarea) {
        if (
            textarea.dataset.storyMultilineReady
            === "true"
        ) {
            return;
        }

        textarea.dataset.storyMultilineReady =
            "true";

        resizeTextarea(textarea);

        textarea.addEventListener(
            "input",
            function () {
                resizeTextarea(textarea);
            }
        );

        textarea.addEventListener(
            "change",
            function () {
                resizeTextarea(textarea);
            }
        );

        window.addEventListener(
            "resize",
            function () {
                resizeTextarea(textarea);
            },
            {
                passive: true,
            }
        );

        textarea.addEventListener(
            "keydown",
            function (event) {
                /*
                 * Enter = nova linha.
                 * Ctrl+Enter / Cmd+Enter = enviar.
                 */
                if (
                    event.key === "Enter"
                    && (
                        event.ctrlKey
                        || event.metaKey
                    )
                ) {
                    event.preventDefault();

                    const form =
                        textarea.closest("form");

                    if (
                        form
                        && textarea.value.trim()
                    ) {
                        if (
                            typeof form.requestSubmit
                            === "function"
                        ) {
                            form.requestSubmit();
                        } else {
                            form.submit();
                        }
                    }
                }
            }
        );
    }

    function initializeAll() {
        document
            .querySelectorAll(SELECTOR)
            .forEach(initializeTextarea);
    }

    if (
        document.readyState === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            initializeAll
        );
    } else {
        initializeAll();
    }
})();
/* BOTUKA_STORY_MULTILINE_END */
