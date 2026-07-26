(function () {
  "use strict";

  const imageInput = document.getElementById("id_imagem_principal");
  const imagePreview = document.querySelector("[data-local-cover-preview]");
  if (imageInput && imagePreview) {
    imageInput.addEventListener("change", function () {
      const file = imageInput.files && imageInput.files[0];
      if (!file || !file.type.startsWith("image/")) return;
      const url = URL.createObjectURL(file);
      imagePreview.replaceChildren();
      const image = document.createElement("img");
      image.src = url;
      image.alt = "Pré-visualização da imagem principal";
      image.addEventListener("load", function () { URL.revokeObjectURL(url); }, {once: true});
      imagePreview.appendChild(image);
    });
  }

  const videoInput = document.getElementById("id_url_youtube");
  if (videoInput) {
    const preview = document.createElement("div");
    preview.className = "video-shell";
    videoInput.parentElement.appendChild(preview);
    videoInput.addEventListener("input", function () {
      const value = videoInput.value.trim();
      const match = value.match(/(?:youtube\.com\/(?:watch\?v=|shorts\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/);
      preview.replaceChildren();
      if (!match) return;
      const frame = document.createElement("iframe");
      frame.src = "https://www.youtube-nocookie.com/embed/" + match[1];
      frame.title = "Pré-visualização do vídeo";
      frame.loading = "lazy";
      frame.allowFullscreen = true;
      preview.appendChild(frame);
    });
  }

  function selectedBoolean(name) {
    const checked = document.querySelector('input[name="' + name + '"]:checked');
    return checked ? checked.value === "true" : null;
  }

  function toggleFields(controller, names, visibleWhen) {
    const update = function () {
      const visible = selectedBoolean(controller) === visibleWhen;
      names.forEach(function (name) {
        const shell = document.querySelector('[data-field="' + name + '"]');
        if (shell) shell.hidden = !visible;
      });
    };
    document.querySelectorAll('input[name="' + controller + '"]').forEach(function (input) {
      input.addEventListener("change", update);
    });
    update();
  }

  toggleFields("gratuito", [
    "valor_inteiro", "valor_meia", "valor_infantil", "valor_informativo", "link_compra"
  ], false);
  toggleFields("agendamento_necessario", [
    "agendamento_telefone", "agendamento_whatsapp", "agendamento_site",
    "agendamento_link", "agendamento_instrucoes", "agendamento_antecedencia_horas"
  ], true);

  const mapShell = document.querySelector("[data-local-map]");
  if (mapShell) {
    const latitude = document.getElementById("id_latitude");
    const longitude = document.getElementById("id_longitude");
    const message = mapShell.querySelector("[data-location-message]");
    const locateButton = mapShell.querySelector("[data-use-geolocation]");
    const searchButton = mapShell.querySelector("[data-search-address]");
    let map = null;
    let marker = null;

    const setMessage = function (text, error) {
      message.textContent = text;
      message.classList.toggle("is-error", Boolean(error));
    };
    const validPoint = function (lat, lng) {
      return Number.isFinite(lat) && Number.isFinite(lng) &&
        lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
    };
    const setPoint = function (lat, lng, center) {
      if (!validPoint(lat, lng)) return;
      latitude.value = lat.toFixed(6);
      longitude.value = lng.toFixed(6);
      if (map && marker) {
        marker.setLatLng([lat, lng]);
        if (center) map.setView([lat, lng], 16);
      }
    };

    if (window.L) {
      const initialLat = Number.parseFloat(latitude.value);
      const initialLng = Number.parseFloat(longitude.value);
      const hasInitial = validPoint(initialLat, initialLng);
      const center = hasInitial ? [initialLat, initialLng] : [-22.8858, -48.4450];
      map = window.L.map(mapShell.querySelector("[data-map-canvas]")).setView(center, hasInitial ? 16 : 12);
      window.L.tileLayer(mapShell.dataset.tiles, {
        attribution: mapShell.dataset.attribution,
        maxZoom: 19
      }).addTo(map);
      marker = window.L.marker(center, {draggable: true}).addTo(map);
      marker.on("dragend", function () {
        const point = marker.getLatLng();
        setPoint(point.lat, point.lng, false);
      });
      map.on("click", function (event) {
        setPoint(event.latlng.lat, event.latlng.lng, false);
      });
    } else {
      setMessage("O mapa não pôde ser carregado. Use a digitação manual ou sua localização.", true);
    }

    locateButton.addEventListener("click", function () {
      if (!navigator.geolocation) {
        setMessage("Este navegador não oferece suporte à localização.", true);
        return;
      }
      setMessage("Obtendo sua localização…", false);
      navigator.geolocation.getCurrentPosition(function (position) {
        setPoint(position.coords.latitude, position.coords.longitude, true);
        setMessage("Localização capturada com sucesso. Confirme antes de salvar.", false);
      }, function () {
        setMessage("Não foi possível obter sua localização. Verifique a permissão do navegador.", true);
      }, {enableHighAccuracy: true, timeout: 10000, maximumAge: 60000});
    });

    searchButton.addEventListener("click", async function () {
      const fields = ["logradouro", "numero", "bairro", "cidade", "estado", "cep"];
      const address = fields.map(function (name) {
        const input = document.getElementById("id_" + name);
        return input ? input.value.trim() : "";
      }).filter(Boolean).join(", ");
      if (address.length < 5) {
        setMessage("Preencha o endereço antes de pesquisar.", true);
        return;
      }
      setMessage("Procurando o endereço…", false);
      try {
        const response = await fetch(mapShell.dataset.geocodeUrl + "?endereco=" + encodeURIComponent(address), {
          headers: {"X-Requested-With": "XMLHttpRequest"}
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.erro || "Endereço não encontrado.");
        setPoint(Number(data.latitude), Number(data.longitude), true);
        setMessage("Endereço localizado. Ajuste o marcador se necessário.", false);
      } catch (error) {
        setMessage(error.message || "Não foi possível localizar o endereço.", true);
      }
    });
  }
})();
