/**
 * Cloudflare Worker: VK API & Photo Upload Proxy
 *
 * Безопасность:
 * 1. Проверка IP клиента (CF-Connecting-IP): доступ разрешён ТОЛЬКО с указанного IP сервера.
 * 2. Дополнительная проверка секретного ключа X-Proxy-Secret (если задан PROXY_SECRET).
 * 3. Полная очистка IP-заголовков (cf-connecting-ip, x-forwarded-for, x-real-ip) перед запросом к VK — VK видит только Cloudflare Edge.
 */

// Разрешённые IP-адреса серверов (IPv4 и IPv6 вашего VPS)
const DEFAULT_ALLOWED_IPS = [
  "64.188.106.134",
  "2a12:bec4:1bb0:e3b::2",
];

export default {
  async fetch(request, env, ctx) {
    const clientIp = request.headers.get("cf-connecting-ip");

    // Список разрешённых IP (из переменных окружения или дефолтный)
    const allowedIps = (env.ALLOWED_IPS ? env.ALLOWED_IPS.split(",") : DEFAULT_ALLOWED_IPS)
      .map((ip) => ip.trim())
      .filter(Boolean);

    const proxySecret = env.PROXY_SECRET || "";
    const clientSecret = request.headers.get("X-Proxy-Secret");

    const isIpAllowed = allowedIps.length === 0 || (clientIp && allowedIps.includes(clientIp));
    const isSecretValid = !proxySecret || clientSecret === proxySecret;

    const incomingUrl = new URL(request.url);

    // Healthcheck на корне / для проверки статуса
    if (incomingUrl.pathname === "/" && !request.headers.get("X-Target-URL") && !incomingUrl.search) {
      return new Response(
        JSON.stringify(
          {
            status: "ok",
            service: "vk-proxy-worker",
            your_ip: clientIp,
            ip_authorized: isIpAllowed,
            security: {
              ip_whitelist_active: allowedIps.length > 0,
              allowed_ips: allowedIps,
              secret_check_active: Boolean(proxySecret),
            },
            message: isIpAllowed
              ? "Access granted for your IP."
              : `Access denied. Your IP (${clientIp}) is not in the whitelist. Only authorized bot servers (64.188.106.134) can proxy through this worker.`,
          },
          null,
          2
        ),
        {
          status: isIpAllowed ? 200 : 403,
          headers: { "Content-Type": "application/json; charset=utf-8" },
        }
      );
    }

    // Блокируем доступ посторонним IP
    if (!isIpAllowed || !isSecretValid) {
      return new Response(
        JSON.stringify(
          {
            error: "Forbidden",
            message: `Access denied for IP ${clientIp}. Only authorized bot servers can use this proxy.`,
          },
          null,
          2
        ),
        {
          status: 403,
          headers: { "Content-Type": "application/json; charset=utf-8" },
        }
      );
    }

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

    try {
      // 2. Определение целевого URL
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

      // 3. Очистка заголовков — удаляем любые упоминания IP сервера
      const newHeaders = new Headers(request.headers);
      newHeaders.delete("Host");
      newHeaders.delete("X-Target-URL");
      newHeaders.delete("X-VK-Host");
      newHeaders.delete("X-Proxy-Secret");
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
        // Обязательно для потоковой передачи multipart файлов (фотографий)
        fetchOptions.duplex = "half";
      }

      // 4. Запрос к VK от имени Cloudflare
      return await fetch(targetUrl.toString(), fetchOptions);
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
