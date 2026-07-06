import { readConfig } from "./config";
import { readCatalog } from "./catalog";
import { attachEventCapture } from "./events";
import { mountWidget } from "./widget";

function init(): void {
  const config = readConfig(document.currentScript);
  const catalog = readCatalog();
  console.info(`[memora] loaded for store ${config.storeId}, ${catalog.length} products found`);

  attachEventCapture(config);
  mountWidget(config);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
