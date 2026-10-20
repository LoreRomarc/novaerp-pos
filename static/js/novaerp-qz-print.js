/* global qz */
/*
 * Puente de impresión NovaERP ↔ QZ Tray.
 * QZ Tray es un programa de Windows instalado una sola vez por computador;
 * se inicia con la sesión y permite que una web desplegada use el driver local
 * sin abrir el cuadro de impresión del navegador.
 */
window.NovaERPPrint = (() => {
  // Sin un certificado comercial QZ mostrará una única confirmación de
  // confianza por sitio/usuario. La configuración firmada puede añadirse más
  // adelante sin cambiar el flujo del POS.
  let seguridadConfigurada = false;

  function csrfToken() {
    return document.cookie.split(";").map((valor) => valor.trim())
      .find((valor) => valor.startsWith("csrftoken="))
      ?.split("=").slice(1).join("=") || "";
  }

  async function conectar() {
    if (!window.qz) {
      throw new Error("QZ Tray no está disponible en este navegador.");
    }
    if (!seguridadConfigurada) {
      const certificado = await fetch("/ventas/impresion/qz/certificado/", {
        credentials: "same-origin", cache: "no-store",
      });
      if (certificado.ok) {
        const contenido = await certificado.text();
        qz.security.setCertificatePromise((resolve) => resolve(contenido));
        qz.security.setSignatureAlgorithm("SHA512");
        qz.security.setSignaturePromise((solicitud) => (resolve, reject) => {
          fetch("/ventas/impresion/qz/firmar/", {
            method: "POST", credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
            body: JSON.stringify({ request: solicitud }),
          }).then(async (respuesta) => {
            const texto = await respuesta.text();
            respuesta.ok ? resolve(texto) : reject(new Error(texto));
          }).catch(reject);
        });
      } else {
        // Desarrollo sin certificado: QZ mostrará su advertencia de seguridad.
        qz.security.setCertificatePromise((resolve) => resolve());
      }
      seguridadConfigurada = true;
    }
    if (!qz.websocket.isActive()) {
      await qz.websocket.connect({ retries: 2, delay: 0.5 });
    }
  }

  async function listarImpresoras() {
    await conectar();
    const impresoras = await qz.printers.find();
    return Array.isArray(impresoras) ? impresoras.sort((a, b) => a.localeCompare(b, "es")) : [];
  }

  async function imprimir(payload) {
    if (!payload?.impresora) {
      throw new Error("Seleccione una impresora y guarde la configuración.");
    }
    await conectar();
    const configuracion = qz.configs.create(payload.impresora, {
      jobName: payload.titulo || "NovaERP - comprobante",
      margins: 0,
      scaleContent: true,
      colorType: "blackwhite",
    });
    const datos = payload.tipo === "raw-zpl"
      ? [{ type: "raw", format: "command", flavor: "plain", data: payload.datos }]
      : [{ type: "pixel", format: "html", flavor: "plain", data: payload.html }];
    return qz.print(configuracion, datos);
  }

  return { conectar, listarImpresoras, imprimir };
})();
