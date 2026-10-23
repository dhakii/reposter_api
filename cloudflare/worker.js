/**
 * Cloudflare Worker: VK API & Photo Upload Proxy
 *
 * Назначение:
 * 1. Полностью скрывает реальный IP-адрес вашего сервера от российских дата-центров (VK).
 * 2. Обходит сетевые блокировки/таймауты зарубежных VPS при обращении к pu.vk.ru / pu.vk.com.
 *
 * Бесплатный тариф Cloudflare Workers: 100 000 запросов в день (более чем достаточно).
 */

export default {
  async fetch(request, env, ctx) {
    // 1. CORS Preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
          "Access-Control-Allow-Headers": "*",
        },
      });
    }

    const incomingUrl = new URL(request.url);

    // 2. Health check при открытии в браузере или curl
    if (incomingUrl.pathname === "/" && !request.headers.get("X-Target-URL") && !incomingUrl.search) {
      return new Response(
        JSON.stringify({
          status: "ok",
          service: "vk-proxy-worker",
          message: "VK Proxy is operational and protecting your origin IP.",
        }, null, 2),
        {
          status: 200,
          headers: { "Content-Type": "application/json; charset=utf-8" },
        }
      );
    }

    try {
      // 3. Определение целевого URL
      const targetUrlHeader = request.headers.get("X-Target-URL");
      let targetUrl;

      if (targetUrlHeader) {
        targetUrl = new URL(targetUrlHeader);
      } else {
        const targetHost =
          request.headers.get("X-VK-Host") ||
          (incomingUrl.pathname.includes("upload") ? "pu.vk.ru" : "api.vk.ru");
        targetUrl = new URL(incomingUrl.pathname + incomingUrl.search, `https://${targetHost}`);
      }

      // Всегда HTTPS для VK
      if (targetUrl.protocol !== "https:") {
        targetUrl.protocol = "https:";
      }

      // 4. Очистка и подготовка заголовков:
      // Удаляем заголовки прокси и все клиентские IP-заголовки Cloudflare
      const newHeaders = new Headers(request.headers);
      newHeaders.delete("Host");
      newHeaders.delete("X-Target-URL");
      newHeaders.delete("X-VK-Host");
      newHeaders.delete("cf-connecting-ip");
      newHeaders.delete("cf-ipcountry");
      newHeaders.delete("cf-ray");
      newHeaders.delete("cf-visitor");
      newHeaders.delete("x-forwarded-for");
      newHeaders.delete("x-real-ip");

      const method = request.method.toUpperCase();
      const hasBody = !["GET", "HEAD"].includes(method);

      const fetchOptions = {
        method: method,
        headers: newHeaders,
        redirect: "follow",
      };

      if (hasBody) {
        fetchOptions.body = request.body;
        // Обязательно для потоковой передачи тела запроса (фотографий multipart/form-data)
        fetchOptions.duplex = "half";
      }

      // 5. Запрос к VK от имени Cloudflare
      const response = await fetch(targetUrl.toString(), fetchOptions);

      // 6. Возврат ответа вызывающей стороне
      return response;
    } catch (err) {
      return new Response(
        JSON.stringify(
          {
            error: "Cloudflare VK Proxy Error",
            message: err.message || String(err),
          },
          null,
          2
        ),
        {
          status: 502,
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
          },
        }
      );
    }
  },
};
