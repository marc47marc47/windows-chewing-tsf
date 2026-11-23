// Minimal WebView notepad for IME testing: a text area plus a live log of keyboard / composition events.
// Run: node_modules/.bin/bun app.ts      (logs are also written to events.log next to this file)
import { Webview } from "webview-bun";
import { appendFileSync, writeFileSync } from "node:fs";

const LOG = new URL("./events.log", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
writeFileSync(LOG, `# ${new Date().toISOString()} webview notepad started\n`);

const html = `<!doctype html><meta charset="utf-8">
<style>
  body{font:16px "Segoe UI","Microsoft JhengHei",sans-serif;margin:0;display:flex;flex-direction:column;height:100vh}
  #bar{padding:6px 10px;background:#eee;display:flex;gap:12px;align-items:center}
  #state{font-weight:600}
  textarea{flex:2;font:22px "Microsoft JhengHei",sans-serif;padding:8px;border:0;border-bottom:1px solid #ccc;outline:none}
  #log{flex:1;overflow:auto;margin:0;padding:6px 10px;background:#111;color:#9f9;font:12px Consolas,monospace;white-space:pre}
  button{font:inherit}
</style>
<div id="bar"><span>IME 測試記事本 (bun + WebView2)</span><span id="state">idle</span>
  <button onclick="document.getElementById('t').value='';document.getElementById('log').textContent=''">清除</button></div>
<textarea id="t" autofocus placeholder="切到新酷音後在這裡打字：ㄘㄜˋ ㄕˋ ..."></textarea>
<pre id="log"></pre>
<script>
const t = document.getElementById('t'), log = document.getElementById('log'), st = document.getElementById('state');
function add(line){
  const s = new Date().toISOString().slice(11,23) + ' ' + line;
  log.textContent += s + '\\n'; log.scrollTop = log.scrollHeight;
  if (window.saveLog) window.saveLog(s);
}
t.addEventListener('keydown', e => add('keydown key=' + JSON.stringify(e.key) + ' code=' + e.code + ' composing=' + e.isComposing + ' caps=' + e.getModifierState('CapsLock')));
t.addEventListener('compositionstart', () => { st.textContent = 'composing'; add('compositionstart'); });
t.addEventListener('compositionupdate', e => add('compositionupdate data=' + JSON.stringify(e.data)));
t.addEventListener('compositionend', e => { st.textContent = 'idle'; add('compositionend data=' + JSON.stringify(e.data)); });
t.addEventListener('input', e => add('input type=' + e.inputType + ' data=' + JSON.stringify(e.data) + ' value=' + JSON.stringify(t.value)));
window.addEventListener('focus', () => add('window focus'));
window.addEventListener('blur', () => add('window blur'));
add('ready; UA=' + navigator.userAgent.slice(-60));
</script>`;

const webview = new Webview();
webview.title = "IME 測試記事本";
webview.size = { width: 900, height: 640, hint: 0 };
webview.bind("saveLog", (line: string) => {
  appendFileSync(LOG, line + "\n");
});
webview.setHTML(html);
webview.run();
