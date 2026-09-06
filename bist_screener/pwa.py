"""
PWA destegi.

Streamlit'in <head> bolumune erisim vermez. Bu yuzden manifest ve mobil meta
etiketlerini, bir iframe icinde calisan kucuk bir script uzerinden ana sayfanin
head'ine ekliyoruz (window.parent.document).

Manifest ve simgeler bist_screener/static/ altindadir ve config.toml'daki
enableStaticServing sayesinde /app/static/... yolundan sunulur.
"""

from __future__ import annotations

import streamlit.components.v1 as components

_HEAD = """
<script>
(function () {
  try {
    var doc = window.parent.document;
    if (doc.getElementById("bist-pwa")) return;

    function ekle(tag, attrs) {
      var el = doc.createElement(tag);
      for (var k in attrs) el.setAttribute(k, attrs[k]);
      doc.head.appendChild(el);
      return el;
    }

    var m = ekle("link", { id: "bist-pwa", rel: "manifest",
                           href: "/app/static/manifest.json" });

    ekle("meta", { name: "theme-color", content: "%(tema)s" });
    ekle("meta", { name: "mobile-web-app-capable", content: "yes" });
    ekle("meta", { name: "application-name", content: "BIST Long" });

    // iOS Safari kendi etiketlerini ister
    ekle("meta", { name: "apple-mobile-web-app-capable", content: "yes" });
    ekle("meta", { name: "apple-mobile-web-app-title", content: "BIST Long" });
    ekle("meta", { name: "apple-mobile-web-app-status-bar-style",
                   content: "black-translucent" });
    ekle("link", { rel: "apple-touch-icon", href: "/app/static/icon-192.png" });

    // Telefonda cift dokunusla yakinlastirmayi kapat, tablo kaymasin
    var vp = doc.querySelector("meta[name=viewport]");
    if (vp) vp.setAttribute(
      "content",
      "width=device-width, initial-scale=1, viewport-fit=cover");

    if (m) { /* manifest eklendi */ }
  } catch (e) { /* iframe erisimi engellenirse sessizce gec */ }
})();
</script>
"""


def enable(tema_rengi: str = "#111A24") -> None:
    """Sayfanin head'ine PWA etiketlerini ekler. Gorunur bir sey cizmez."""
    components.html(_HEAD % {"tema": tema_rengi}, height=0, width=0)
