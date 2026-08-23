(function (globalObject) {
  const root = globalObject || globalThis;

  function normalize(value) {
    return (value == null ? "" : String(value)).replace(/\s+/g, " ").trim();
  }

  function hashBytes(bytes) {
    if (!bytes || typeof bytes.length !== "number") return null;
    let hash = 2166136261;
    for (let index = 0; index < bytes.length; index += 1) {
      hash ^= Number(bytes[index]) & 255;
      hash = Math.imul(hash, 16777619);
    }
    return `fnv1a:${(hash >>> 0).toString(16).padStart(8, "0")}`;
  }

  function emptyWebGL() {
    return {
      vendor: null,
      renderer: null,
      version: null,
      shading_language_version: null,
      supported_extensions: [],
      read_pixels_hash: null,
    };
  }

  function collectWebGL() {
    try {
      const canvas = document.createElement("canvas");
      const gl =
        canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
      if (!gl) return emptyWebGL();
      const extension = gl.getExtension("WEBGL_debug_renderer_info");
      const pixels = new Uint8Array(16);
      try {
        gl.clearColor(0.25, 0.5, 0.75, 1);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.readPixels(0, 0, 2, 2, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
      } catch (_pixelError) {}
      return {
        vendor: extension
          ? gl.getParameter(extension.UNMASKED_VENDOR_WEBGL)
          : gl.getParameter(gl.VENDOR),
        renderer: extension
          ? gl.getParameter(extension.UNMASKED_RENDERER_WEBGL)
          : gl.getParameter(gl.RENDERER),
        version: gl.getParameter(gl.VERSION),
        shading_language_version: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
        supported_extensions: gl.getSupportedExtensions() || [],
        read_pixels_hash: hashBytes(pixels),
      };
    } catch (_error) {
      return emptyWebGL();
    }
  }

  async function collectWebRTCIps(timeoutMs) {
    const discovered = new Set();
    const AnyPeer =
      window.RTCPeerConnection ||
      window.webkitRTCPeerConnection ||
      window.mozRTCPeerConnection;
    if (!AnyPeer) return [];
    let peer;
    try {
      peer = new AnyPeer({ iceServers: [] });
      peer.createDataChannel("probe");
      peer.onicecandidate = (event) => {
        const candidate = event && event.candidate && event.candidate.candidate;
        if (!candidate) return;
        const matches = candidate.match(/(\d{1,3}(?:\.\d{1,3}){3})/g) || [];
        for (const match of matches) discovered.add(match);
      };
      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);
      await new Promise((resolve) => setTimeout(resolve, timeoutMs));
    } catch (_error) {
      return Array.from(discovered);
    } finally {
      if (peer) {
        try {
          peer.close();
        } catch (_error) {}
      }
    }
    return Array.from(discovered);
  }

  function collectCanvas() {
    try {
      const canvas = document.createElement("canvas");
      canvas.width = 200;
      canvas.height = 50;
      const ctx = canvas.getContext("2d");
      if (!ctx) return { fingerprint: null, text_measure: null };
      ctx.textBaseline = "top";
      ctx.font = "14px Arial";
      ctx.fillStyle = "#f60";
      ctx.fillRect(0, 0, 200, 50);
      ctx.fillStyle = "#069";
      ctx.fillText("Browser fingerprint probe", 2, 15);
      ctx.fillStyle = "rgba(102, 204, 0, 0.7)";
      ctx.fillText("Browser fingerprint probe", 4, 17);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL();
      return {
        fingerprint: dataUrl.slice(0, 200),
        image_data_hash: hashBytes(imageData && imageData.data),
        data_url_prefix: dataUrl.slice(0, 64),
        text_measure: ctx.measureText("Browser fingerprint probe").width,
      };
    } catch (_error) {
      return {
        fingerprint: null,
        image_data_hash: null,
        data_url_prefix: null,
        text_measure: null,
        error: _error.message,
      };
    }
  }

  function collectFonts(fontTestStrings) {
    const testStrings = Array.isArray(fontTestStrings) ? fontTestStrings : [];
    const baseFonts = ["monospace", "sans-serif", "serif"];
    const detected = [];
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) return [];
    const getWidth = (font) => {
      ctx.font = `72px ${font}, monospace`;
      return ctx.measureText("mmmmmmmmmmlli").width;
    };
    for (const testFont of testStrings) {
      const baseWidths = baseFonts.map(getWidth);
      if (!baseWidths.includes(getWidth(testFont))) detected.push(testFont);
    }
    return detected.slice(0, 50);
  }

  function collectAudio() {
    let ctx;
    let osc;
    try {
      const AudioCtor = window.AudioContext || window.webkitAudioContext;
      ctx = new AudioCtor();
      osc = ctx.createOscillator();
      const analyser = ctx.createAnalyser();
      const gain = ctx.createGain();
      gain.gain.value = 0;
      osc.connect(analyser);
      analyser.connect(gain);
      gain.connect(ctx.destination);
      osc.start(0);
      const buffer = new Float32Array(analyser.frequencyBinCount);
      analyser.getFloatFrequencyData(buffer);
      const sum = buffer.reduce((left, right) => left + right, 0);
      return {
        fingerprint: sum.toFixed(2),
        sample_rate: ctx.sampleRate,
        channel_count: ctx.destination.channelCount,
      };
    } catch (_error) {
      return {
        fingerprint: null,
        sample_rate: null,
        channel_count: null,
        error: _error.message,
      };
    } finally {
      try {
        if (osc) osc.stop(0);
      } catch (_stopError) {}
      try {
        if (ctx && typeof ctx.close === "function") ctx.close();
      } catch (_closeError) {}
    }
  }

  async function collectPermissions() {
    const results = {};
    if (!navigator.permissions || !navigator.permissions.query) return results;
    for (const name of [
      "notifications",
      "camera",
      "microphone",
      "geolocation",
    ]) {
      try {
        const status = await navigator.permissions.query({ name });
        results[name] = status.state;
      } catch (_error) {
        results[name] = `error:${_error.name}`;
      }
    }
    return results;
  }

  function collectIframeLeak() {
    try {
      const iframe = document.createElement("iframe");
      document.body.appendChild(iframe);
      const cw = iframe.contentWindow;
      const leak = cw[0] === null && cw.length === 0;
      document.body.removeChild(iframe);
      return { content_window_array_leak: leak };
    } catch (_error) {
      return { content_window_array_leak: null, error: _error.message };
    }
  }

  function collectAutomationGlobals() {
    const markers = [];
    const globalMarkers = [
      ["playwright", "window.playwright"],
      ["__pw_scripts", "window.__pw_scripts"],
      ["__pw_init", "window.__pw_init"],
      ["cdc_adoQpoasnfa76pfcZLmcfl_Array", "cdc_array"],
      ["cdc_adoQpoasnfa76pfcZLmcfl_Promise", "cdc_promise"],
    ];
    for (const [property, marker] of globalMarkers) {
      if (typeof window[property] !== "undefined") markers.push(marker);
    }
    if (
      document.documentElement &&
      document.documentElement.getAttribute("__playwright_testid_attribute__")
    ) {
      markers.push("__playwright_testid_attribute__");
    }
    const chromeRoot =
      typeof window.chrome !== "undefined" ? window.chrome : undefined;
    const chromeRuntime = chromeRoot ? chromeRoot.runtime : undefined;
    if (typeof chromeRuntime !== "object") {
      markers.push(`chrome.runtime.typeof=${typeof chromeRuntime}`);
    }
    return markers;
  }

  function collectConnection() {
    const connection =
      navigator.connection ||
      navigator.mozConnection ||
      navigator.webkitConnection;
    if (!connection) return null;
    return {
      effective_type: connection.effectiveType || null,
      downlink: connection.downlink || null,
      rtt: connection.rtt || null,
      save_data: connection.saveData || false,
    };
  }

  function collectScreenOrientation() {
    const orientation = window.screen.orientation;
    return orientation
      ? { angle: orientation.angle, type: orientation.type }
      : null;
  }

  function collectTimingJitter() {
    const deltas = [];
    let last = performance.now();
    for (let index = 0; index < 10; index += 1) {
      const now = performance.now();
      deltas.push(parseFloat((now - last).toFixed(4)));
      last = now;
    }
    return deltas;
  }

  async function collectUserAgentData(highEntropyHints) {
    if (!navigator.userAgentData) return null;
    const hints = Array.isArray(highEntropyHints) ? highEntropyHints : [];
    return navigator.userAgentData
      .getHighEntropyValues(hints)
      .catch(() => null);
  }

  function normalizedLanguages() {
    if (!Array.isArray(navigator.languages)) return [];
    return navigator.languages.map((value) => normalize(value)).filter(Boolean);
  }

  function normalizedPluginNames() {
    if (!navigator.plugins) return [];
    return Array.from(navigator.plugins)
      .map((plugin) => normalize(plugin && plugin.name))
      .filter(Boolean)
      .slice(0, 10);
  }

  function screenPayload() {
    return {
      width: window.screen.width,
      height: window.screen.height,
      avail_width: window.screen.availWidth,
      avail_height: window.screen.availHeight,
      color_depth: window.screen.colorDepth,
      pixel_depth: window.screen.pixelDepth,
      device_pixel_ratio: window.devicePixelRatio || 1,
    };
  }

  function viewportPayload() {
    return {
      width: window.innerWidth,
      height: window.innerHeight,
      outer_width: window.outerWidth,
      outer_height: window.outerHeight,
    };
  }

  function behavioralPayload(value) {
    return value && typeof value === "object" ? value : null;
  }

  async function crawlerProbeCollectBaseline(input) {
    const payload = input && typeof input === "object" ? input : {};
    return {
      user_agent: normalize(navigator.userAgent),
      user_agent_data: await collectUserAgentData(payload.highEntropyHints),
      webdriver: navigator.webdriver === true,
      locale: normalize(navigator.language),
      languages: normalizedLanguages(),
      timezone: normalize(Intl.DateTimeFormat().resolvedOptions().timeZone),
      platform: normalize(navigator.platform),
      vendor: normalize(navigator.vendor),
      plugins_count: navigator.plugins ? navigator.plugins.length : 0,
      plugin_names: normalizedPluginNames(),
      hardware_concurrency: navigator.hardwareConcurrency || null,
      device_memory: navigator.deviceMemory ?? null,
      screen: screenPayload(),
      viewport: viewportPayload(),
      webgl: collectWebGL(),
      canvas: collectCanvas(),
      audio: collectAudio(),
      fonts: collectFonts(payload.fontTestStrings),
      connection: collectConnection(),
      screen_orientation: collectScreenOrientation(),
      max_touch_points: navigator.maxTouchPoints ?? null,
      pdf_viewer_enabled: navigator.pdfViewerEnabled ?? null,
      cookie_enabled: navigator.cookieEnabled ?? null,
      do_not_track: navigator.doNotTrack ?? null,
      automation_globals: collectAutomationGlobals(),
      timing_jitter: collectTimingJitter(),
      iframe_leak: collectIframeLeak(),
      permissions: await collectPermissions(),
      behavioral_smoke: behavioralPayload(payload.behavioralSmoke),
      webrtc_ips: await collectWebRTCIps(payload.webrtcTimeoutMs),
      timestamp: new Date().toISOString(),
    };
  }

  root.__crawlerProbeCollectBaseline = crawlerProbeCollectBaseline;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { crawlerProbeCollectBaseline };
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
